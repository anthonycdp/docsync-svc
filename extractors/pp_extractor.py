import os, re, pdfplumber, sys, csv
from pathlib import Path
from typing import Optional, Dict

if str(Path(__file__).parent.parent) not in sys.path: 
    sys.path.insert(0, str(Path(__file__).parent.parent))


try:
    from ..data import ClientData, VehicleData, DocumentData, PaymentData, NewVehicleData, ThirdPartyData, ExtractedData
    from ..utils import LoggerMixin, PDFExtractionError, ValidationError
    from .cnh_extractor import CNHExtractor
except (ImportError, ValueError):
    from data import ClientData, VehicleData, DocumentData, PaymentData, NewVehicleData, ThirdPartyData, ExtractedData
    from utils import LoggerMixin, PDFExtractionError, ValidationError
    from extractors.cnh_extractor import CNHExtractor

class ProposalExtractor(LoggerMixin):
    
    def __init__(self):
        super().__init__()
        self.patterns = self._setup_regex_patterns()
        self.model_to_brand = self._load_brand_model_dictionary()
    
    def _setup_regex_patterns(self) -> Dict[str, re.Pattern]:
        return {
            'cpf': re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}'),
            'rg': re.compile(r'Ident/Inscrição:\s*(\d+)'),
            'cep': re.compile(r'\b\d{5}-?\d{3}\b'),
            'plate': re.compile(r'\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b'),
            'chassis': re.compile(r'\b[A-Z0-9]{17}\b'),
            'year_model': re.compile(r'\b((?:19|20)\d{2})\s*/\s*((?:19|20)\d{2})\b(?![A-Z0-9])'),
            'proposal_number': re.compile(r'NR\.\s*(\d+)'),
            'date': re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
        }
    
    def _load_brand_model_dictionary(self) -> Dict[str, str]:
        """Carrega dicionário marca-modelo do CSV para matching automático"""
        model_to_brand = {}
        
        try:
            csv_path = Path(__file__).parent.parent / 'shared' / 'assets' / 'dic' / 'tabela_id_marca_modelo.csv'
            
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        marca = row.get('MARCA', '').strip()
                        modelo = row.get('MODELO', '').strip()
                        
                        if marca and modelo:
                            model_to_brand[modelo.upper()] = marca.upper()
                
                self.log_operation("_load_brand_model_dictionary", total_models=len(model_to_brand))
            else:
                self.log_warning("Dicionário marca-modelo não encontrado", csv_path=str(csv_path))
                
        except Exception as e:
            self.log_error(e, "_load_brand_model_dictionary")
        
        return model_to_brand
    
    def extract_data(self, pdf_path: str) -> ExtractedData:
        """Método principal - extrai todos os dados relevantes do PDF com fallback OCR inteligente"""
        pdf_file = Path(pdf_path)
        if not pdf_file.exists(): 
            raise PDFExtractionError(f"Arquivo PDF não encontrado: {pdf_path}", pdf_path=pdf_path)
        if pdf_file.suffix.lower() != '.pdf': 
            raise ValidationError(f"Arquivo deve ser PDF, recebido: {pdf_file.suffix}", field_name="file_extension", field_value=pdf_file.suffix, validation_type="file_type")
        
        self.log_operation("extract_data", pdf_path=pdf_path)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += (page.extract_text() or "") + "\n"
                
                if len(full_text.strip()) < 100:
                    raise PDFExtractionError("Texto extraído insuficiente para análise", pdf_path=pdf_path)
                
                extracted_data = self.extract_proposal_data(full_text, pdf_path)
                return extracted_data
                
        except Exception as e:
            self.log_error(e, "extract_data", pdf_path=pdf_path)
            raise PDFExtractionError(f"Erro ao extrair dados do PDF: {e}", pdf_path=pdf_path)
    
    
    def _is_extraction_sufficient(self, extracted_data: ExtractedData) -> bool:
        client_ok = bool(extracted_data.client.name.strip() and extracted_data.client.cpf.strip())
        vehicle_ok = bool(extracted_data.vehicle.model.strip())
        return client_ok and vehicle_ok
    
    def extract_proposal_data(self, text: str, pdf_path: str = None) -> ExtractedData:
        """Método especializado para extrair dados de proposta de veículo"""
        client = self._extract_client_data(text)
        vehicle = self._extract_vehicle_data(text, pdf_path)
        document = self._extract_document_data(text)
        new_vehicle = self._extract_new_vehicle_data(text)
        
        # CKDEV-NOTE: Removed incorrect fallback that was copying new vehicle color to used vehicle
        
        return ExtractedData(client=client, vehicle=vehicle, document=document, new_vehicle=new_vehicle, payment=None, third_party=None)
    
    def _extract_client_data(self, text: str) -> ClientData:
        client = ClientData()
        
        name_patterns = [
            r'Cliente:\s*\n?\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]+?)(?:\s*Código:|\s*Endereço:|\s*CNPJ/CPF:|\n)',
            r'IDENTIFICAÇÃO DO PROPONENTE\s*\n[^\n]*\n\s*Cliente:\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]+?)(?:\s*Código:|\s*Endereço:)',
            r'^([A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,})',
            r'([A-Z]{2,}\s+[A-Z]{2,}\s+(?:DE|DA|DO|DOS|DAS)\s+[A-Z]{2,})',
            r'([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]{10,50})\s+(?:CNPJ|CPF|RG|Endereço)',
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip()
                if not any(word in name.upper() for word in ['TELEFONICA', 'BRASIL', 'S.A.', 'LTDA', 'ENGENHEIRO', 'AVENIDA', 'RUA', 'CODIGO', 'ENDERECO']):
                    client.name = name
                    break
        
        cpf_matches = self.patterns['cpf'].findall(text)
        if cpf_matches: client.cpf = cpf_matches[0]
        
        rg_patterns = [r'Ident/Inscrição:\s*([0-9]{1,2}\.?[0-9]{3}\.?[0-9]{3})', r'Ident/Inscrição:\s*([0-9]+(?:\.[0-9]+)*)', r'RG[:\s]*([0-9]{1,2}\.?[0-9]{3}\.?[0-9]{3})', r'Identidade[:\s]*([0-9]{1,2}\.?[0-9]{3}\.?[0-9]{3})']
        
        for pattern in rg_patterns:
            rg_match = re.search(pattern, text, re.IGNORECASE)
            if rg_match:
                rg_number = rg_match.group(1)
                if '.' not in rg_number and len(rg_number) >= 7:
                    rg_number = f"{rg_number[:2]}.{rg_number[2:5]}.{rg_number[5:]}" if len(rg_number) in [8,9] else rg_number
                client.rg = rg_number; break
        
        street_info = {'logradouro': '', 'numero': '', 'bairro': ''}
        
        endereco_patterns = [
            r'Endereço:\s*\n?\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s\d,.\-]+?)(?:\s*Bairro:|\s*Cidade:|\s*Estado:|\n)',
            r'Cliente:\s*[A-Z\s]+\s*\n?\s*Endereço:\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s\d,.\-]+?)(?:\s*Bairro:|$)',
            r'([A-Z\s]+)\n(Rua\s*-\s*[A-Za-z\s]+)\s+(\d+)\n([A-Z\s]+?)\s*(?:\d[^\n]*)\n(\d{5}-\d{3})\s+([A-Z\s]+)\s*-\s*SP'
        ]
        
        endereco_match = None
        for pattern in endereco_patterns:
            endereco_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if endereco_match:
                if len(endereco_match.groups()) == 6:
                    street_info['logradouro'] = endereco_match.group(2).replace('-', '').strip().upper()
                    street_info['numero'] = endereco_match.group(3).strip()
                    bairro_raw = endereco_match.group(4).strip().upper()
                    street_info['bairro'] = re.sub(r'\s*\d[^\w]*\s*VIA.*', '', bairro_raw, flags=re.IGNORECASE).strip()
                else:
                    endereco_text = endereco_match.group(1).strip()
                    street_pattern = r'((?:RUA|AVENIDA|AV\.|R\.)\s+[^,\d]+)\s*,?\s*(\d+)(?:,?\s*(.+))?'
                    street_match = re.search(street_pattern, endereco_text, re.IGNORECASE)
                    if street_match:
                        street_info['logradouro'] = street_match.group(1).strip().upper()
                        street_info['numero'] = street_match.group(2).strip()
                        if street_match.group(3):
                            street_info['bairro'] = street_match.group(3).strip().upper()
                break
        
        if not endereco_match:
            address_patterns = [
                r'Endereço:\s*\n?\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s\d,.-]+?)(?:\s*Cidade:)',
                r'((?:RUA|AVENIDA|AV\.|R\.)\s+[A-Z\s]+ \d+)(?:\s*\n?\s*([A-Z\s]+?))?'
            ]
            
            for pattern_idx, pattern in enumerate(address_patterns):
                address_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if address_match:
                    if pattern_idx == 0:
                        address_text = re.sub(r'\s+', ' ', address_match.group(1).strip())
                        street_pattern = r'((?:RUA|AVENIDA|AV\.|R\.)\s+[^,\d]+)\s*,?\s*(\d+)(?:,?\s*(.+))?'
                        street_match = re.search(street_pattern, address_text, re.IGNORECASE)
                        if street_match:
                            street_info['logradouro'] = street_match.group(1).strip().upper()
                            street_info['numero'] = street_match.group(2).strip()
                            if street_match.group(3):
                                street_info['bairro'] = street_match.group(3).strip().upper()
                    elif pattern_idx == 1:
                        full_address = address_match.group(1).strip()
                        addr_pattern = r'((?:RUA|AVENIDA|AV\.|R\.)\s+[A-Z\s]+)\s+(\d+)'
                        addr_match = re.search(addr_pattern, full_address, re.IGNORECASE)
                        if addr_match:
                            street_info['logradouro'] = addr_match.group(1).strip().upper()
                            street_info['numero'] = addr_match.group(2).strip()
                        if len(address_match.groups()) > 1 and address_match.group(2):
                            street_info['bairro'] = address_match.group(2).strip().upper()
                    
                    if street_info['bairro']:
                        street_info['bairro'] = re.sub(r'\b(?:CEP|CIDADE|SP|SÃO PAULO|SAO PAULO)\b.*', '', street_info['bairro'], flags=re.IGNORECASE).strip()
                        street_info['bairro'] = re.sub(r'\d{5}-?\d{3}.*', '', street_info['bairro']).strip()
                    
                    break
        
        if endereco_match and len(endereco_match.groups()) == 6:
            client.city = endereco_match.group(6).strip().upper()
            client.cep = endereco_match.group(5)
        else:
            city_patterns = [
                r'Cidade:\s*\n?\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]+?)(?:\s*Estado:|\s*CEP:|\n)',
                r'CEP:\s*(\d{5}-?\d{3})\s+([A-Z\s]+)\s*-?\s*SP',
                r'\d{5}-?\d{3}\s+([A-Z\s]+)\s*-\s*SP',
                r'([A-Z\s]{5,30})\s*-\s*SP\b',
                r'JD\s+[A-Z\s]+\s+(\d+)\s+SP\s+(\d{5}-?\d{3})\s+([A-Z\s]+)',
            ]
            
            for pattern in city_patterns:
                city_match = re.search(pattern, text, re.IGNORECASE)
                if city_match:
                    if len(city_match.groups()) == 3:
                        client.cep = city_match.group(2)
                        city = city_match.group(3).strip().upper()
                    elif len(city_match.groups()) == 2:
                        client.cep = city_match.group(1)
                        city = city_match.group(2).strip().upper()
                    else:
                        city = city_match.group(1).strip().upper()
                    
                    if not any(word in city for word in ['TELEFONICA', 'BRASIL', 'ENGENHEIRO', 'AVENIDA']) and len(city) > 3:
                        client.city = city
                        break
            
            cep_patterns = [r'CEP:\s*(\d{5}-?\d{3})', r'\b(\d{5}-\d{3})\b', r'\b(\d{8})\b']
            
            for pattern in cep_patterns:
                cep_matches = re.findall(pattern, text)
                if cep_matches:
                    for cep in cep_matches:
                        if len(cep) == 8 and '-' not in cep:
                            formatted_cep = f"{cep[:5]}-{cep[5:]}"
                        else:
                            formatted_cep = cep
                        
                        if True:
                            client.cep = formatted_cep
                            break
                    if client.cep:
                        break
        
        if street_info['logradouro'] and client.city and client.cep:
            logradouro = re.sub(r'\bAVE\s+AV\b', 'AVENIDA', street_info['logradouro'], flags=re.IGNORECASE)
            logradouro = re.sub(r'\bR\.\s+RUA\b', 'RUA', logradouro, flags=re.IGNORECASE)
            logradouro = re.sub(r'\bR\.\s+', 'RUA ', logradouro, flags=re.IGNORECASE)
            logradouro = re.sub(r'\bAV\.\s+', 'AVENIDA ', logradouro, flags=re.IGNORECASE)
            logradouro = re.sub(r'\s+', ' ', logradouro).strip()
            
            address_parts = [logradouro]
            if street_info['numero']:
                address_parts.append(street_info['numero'])
            if street_info['bairro']:
                address_parts.append(f"BAIRRO {street_info['bairro']}")
            
            client.address = f"{', '.join(address_parts)}, CEP {client.cep}, {client.city} - SP"
        elif street_info['logradouro']: 
            client.address = street_info['logradouro']
        
        return client
    
    def _extract_vehicle_data(self, text: str, pdf_path: str = None) -> VehicleData:
        """Extrai dados do veículo usado na troca"""
        vehicle = VehicleData()
        
        used_vehicle_section = re.search(r'DESCRIÇÃO DO\(S\) VEÍCULO\(S\) USADO\(S\)(?:\s*\(PARA TROCA\))?.*?(?=VALORES|OBSERVAÇÕES|$)', text, re.DOTALL | re.IGNORECASE)
        
        if used_vehicle_section:
            section_text = used_vehicle_section.group(0)
        else:
            section_text = text
        
        if not vehicle.plate:
            plate_match = re.search(r'([A-Z]{3}[0-9][A-Z0-9][0-9]{2})', section_text)
            if plate_match: 
                vehicle.plate = plate_match.group(1)
        
        if not vehicle.model and vehicle.plate:
            line_pattern = rf'{re.escape(vehicle.plate)}\s+([A-Z0-9\s\.\-]+?)\s+(?:PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)'
            model_match = re.search(line_pattern, section_text, re.IGNORECASE)
            if model_match:
                raw_model = model_match.group(1).strip()
                vehicle.model = self._clean_vehicle_model(raw_model)
            else:
                flexible_pattern = rf'{re.escape(vehicle.plate)}\s+([A-Z0-9][A-Z0-9\s\.\-]{{5,30}})'
                flexible_match = re.search(flexible_pattern, section_text, re.IGNORECASE)
                if flexible_match:
                    raw_model = re.sub(r'\s+(PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE).*$', '', flexible_match.group(1).strip(), flags=re.IGNORECASE)
                    raw_model = re.sub(r'\s+(RMEATN[O]?[U]?[A]?[L]?|RPERTEO|RPRETO).*$', '', raw_model, flags=re.IGNORECASE)
                    vehicle.model = self._clean_vehicle_model(raw_model)
            
            if not vehicle.chassis:
                chassis_matches = self.patterns['chassis'].findall(section_text)
                if chassis_matches: 
                    vehicle.chassis = chassis_matches[0]
                
        if used_vehicle_section:
            section_text_used = used_vehicle_section.group(0)
            
            color_pattern = r'\b(PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)\b'
            color_match = re.search(color_pattern, section_text_used, re.IGNORECASE)
            if color_match:
                vehicle.color = color_match.group(1).upper()
            else:
                if pdf_path:
                    try:
                        import fitz
                        doc = fitz.open(pdf_path)
                        pymupdf_text = ""
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            pymupdf_text += page.get_text() + "\n"
                        doc.close()
                        
                        pymupdf_section = re.search(r'DESCRIÇÃO DO\(S\) VEÍCULO\(S\) USADO\(S\)(?:\s*\(PARA TROCA\))?.*?(?=VALORES|OBSERVAÇÕES|$)', pymupdf_text, re.DOTALL | re.IGNORECASE)
                        if pymupdf_section:
                            pymupdf_section_text = pymupdf_section.group(0)
                            pymupdf_color_match = re.search(color_pattern, pymupdf_section_text, re.IGNORECASE)
                            if pymupdf_color_match:
                                vehicle.color = pymupdf_color_match.group(1).upper()
                    except Exception:
                        pass
            
        if not vehicle.year_model:
            main_pattern = r'\b((?:19|20)\d{2})\s*/\s*((?:19|20)\d{2})\b(?!\w)'
            
            matches = re.findall(main_pattern, section_text)
            
            for year1, year2 in matches:
                year1_int = int(year1)
                year2_int = int(year2)
                
                if (1990 <= year1_int <= 2030 and 
                    1990 <= year2_int <= 2030 and 
                    abs(year2_int - year1_int) <= 5):
                    
                    pattern_with_context = rf'([A-Z]{{2,}}.*?){re.escape(year1)}\s*/\s*{re.escape(year2)}([A-Z]{{2,}}.*?)'
                    context_match = re.search(pattern_with_context, section_text, re.IGNORECASE)
                    
                    if not context_match:
                        vehicle.year_model = f"{year1}/{year2}"
                        break
            
            if not vehicle.year_model:
                fallback_patterns = [
                    r'ANO/MODELO[:\s]+(\d{4})\s*/\s*(\d{4})',
                    r'ANO[:\s]*(\d{4})[^\d]*MODELO[:\s]*(\d{4})',
                    r'(?:^|\s)(\d{4})\s*/\s*(\d{4})(?=\s+[A-Z0-9]{17})',
                    r'(?:^|\s)(\d{4})\s*/\s*(\d{4})(?=\s*$|\s*\n)',
                    r'(?<=\s)(\d{4})\s*/\s*(\d{4})(?=\s*[A-Z]{17})',
                ]
                
                for pattern in fallback_patterns:
                    year_match = re.search(pattern, section_text, re.MULTILINE)
                    if year_match:
                        year1, year2 = year_match.group(1), year_match.group(2)
                        year1_int = int(year1)
                        year2_int = int(year2)
                        
                        if (1990 <= year1_int <= 2030 and 
                            1990 <= year2_int <= 2030 and 
                            abs(year2_int - year1_int) <= 5):
                            vehicle.year_model = f"{year1}/{year2}"
                            break
        
        if vehicle.year_model and not re.match(r'^\d{4}/\d{4}$', vehicle.year_model):
            year_matches = re.findall(r'\b(\d{4})\b', vehicle.year_model)
            if len(year_matches) >= 2:
                vehicle.year_model = f"{year_matches[0]}/{year_matches[1]}"
            else:
                vehicle.year_model = ""
        
        if used_vehicle_section:
            value_pattern = r'([A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+[A-Z0-9\s\.\-]+?\s+(?:PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)\s+([\d.,]+)'
            value_match = re.search(value_pattern, section_text, re.IGNORECASE)
            
            if value_match:
                raw_value = value_match.group(2)
                formatted_value = raw_value.replace('.', '').replace(',', ',')
                vehicle.value = formatted_value
            else:
                fallback_value_pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
                fallback_match = re.search(fallback_value_pattern, section_text)
                if fallback_match: 
                    vehicle.value = fallback_match.group(1)
        
        if vehicle.model and not vehicle.brand:
            vehicle.brand = self._extract_brand_from_model(vehicle.model)
        
        return vehicle
    
    def _extract_document_data(self, text: str) -> DocumentData:
        document = DocumentData()
        
        proposal_match = self.patterns['proposal_number'].search(text)
        if proposal_match: document.proposal_number = proposal_match.group(1)
        
        return document
    
    def _extract_new_vehicle_data(self, text: str) -> Optional[NewVehicleData]:
        new_vehicle = NewVehicleData()
        
        vehicle_section = re.search(r'IDENTIFICAÇÃO DO VEÍCULO.*?(?=DESCRIÇÃO|$)', text, re.DOTALL)
        
        if vehicle_section:
            section_text = vehicle_section.group(0)
            
            model_match = re.search(r'Modelo:\s*\n?\s*([A-Z\s\d\.\/\-]+)', section_text)
            if model_match: new_vehicle.model = model_match.group(1).strip()
            
            brand_match = re.search(r'Marca:\s*\n?\s*([A-Z\s]+)', section_text)
            if brand_match: new_vehicle.brand = brand_match.group(1).strip()
            
            color_patterns = [
                r'Cor:\s*([A-Z\s]+?)(?:\s+Ano|\s*\n|$)',
                r'Cor\s*:\s*([A-Z\s]+?)(?:\s+Ano|\s*\n|$)',
                r'([A-Z\s]+)\s*\(cor\)',
                r'Cor\s*([A-Z\s]+?)(?:\s+Ano|\s*\n|$)'
            ]
            
            for pattern in color_patterns:
                color_match = re.search(pattern, section_text, re.IGNORECASE)
                if color_match: 
                    color_raw = color_match.group(1).strip()
                    color_clean = color_raw.replace('\n', ' ').replace('  ', ' ').strip()
                    
                    
                    color_clean = re.sub(r'\b(?:ANO|FAB|MOD|FABMOD|FABRICACAO|MODELO)\b.*$', '', color_clean, flags=re.IGNORECASE).strip()
                    
                    if color_clean and len(color_clean) > 1:
                        new_vehicle.color = color_clean.upper()
                        break
            
            year_match = re.search(r'Ano Fab/Mod:\s*\n?\s*(\d{4}\s*/\s*\d{4})', section_text)
            if year_match: new_vehicle.year_model = year_match.group(1).replace(' ', '')
            
            chassis_match = re.search(r'Chassi:\s*\n?\s*([A-Z0-9]{17})', section_text)
            if chassis_match: new_vehicle.chassis = chassis_match.group(1)
        
        value_patterns = [r'Subtotal:\s*\n?\s*([\d.,]+)', r'Total:\s*\n?\s*([\d.,]+)', r'Veículo:\s*\n?\s*([\d.,]+)']
        for pattern in value_patterns:
            match = re.search(pattern, text)
            if match: new_vehicle.value = match.group(1); break
        
        return new_vehicle if new_vehicle.model or new_vehicle.brand else None
    
    def _clean_vehicle_model(self, raw_model: str) -> str:
        if not raw_model: return ""
        
        model = raw_model.strip()
        
        model = re.sub(r'\b(?:VALOR|COR|PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)\b.*$', '', model, flags=re.IGNORECASE).strip()
        
        corrections = {'FLEXPRETO': 'FLEX', 'FLEXBRANCO': 'FLEX', 'FLEXPRATA': 'FLEX', 'AUTOPRETO': 'AUTOMATICO', 'AUTOBRANCO': 'AUTOMATICO', 'AUTOPRATA': 'AUTOMATICO'}
        for wrong, correct in corrections.items():
            if wrong in model: model = model.replace(wrong, correct)
        
        if 'FLEXP' in model and 'RPERTEOMIER' in model: 
            model = re.sub(r'FLEXP\s+RPERTEOMIER.*', '', model)
        elif 'FLEXP' in model and 'RPERTEO' in model: 
            model = re.sub(r'FLEXP\s+RPERTEO.*', '', model)
        elif 'RPERTEOMIER' in model: 
            model = re.sub(r'\s*RPERTEOMIER.*', '', model)
        elif 'RPERTEO' in model: 
            model = re.sub(r'\s*RPERTEO.*', '', model)
        elif any(corrupt in model for corrupt in ['RMEATNOUAL', 'RMEATNUAL', 'RMEATN']): 
            model = re.sub(r'\s*RMEATN[OUAL]*.*', '', model)
        elif any(corrupt in model for corrupt in ['AUTOPMR', 'RÁETTI', 'TIOCO']): 
            model = re.sub(r'\s+AUTO[A-Z]*$', ' AU', model, flags=re.IGNORECASE)
            model = re.sub(r'\s+AUTOPMR.*$', ' AU', model, flags=re.IGNORECASE)
        
        
        model = re.sub(r'\b(?:AUTOMATIC|FLEXP|RPERTEOMIER|RPERTEO)\b.*$', '', model, flags=re.IGNORECASE)
        
        model = re.sub(r'[^A-Z0-9\s\.\-/]', ' ', model)
        
        ocr_corrections = {r'\bFRLAENXC\b': 'FLEX', r'\bFLEXP\b': 'FLEX', r'\bTOTALB\b': 'TOTAL', r'\bR-LINE\b': 'R-LINE', r'\bTIPT\b': 'TIPT', r'\b1\.4\b': '1.4', r'\b250\b': '250', r'\bTSI\b': 'TSI', r'\bAUTOMATI.*\b': 'AU'}
        for wrong, correct in ocr_corrections.items(): model = re.sub(wrong, correct, model, flags=re.IGNORECASE)
        
        words = model.split(); cleaned_words = []; previous_word = ""
        for word in words:
            if word != previous_word: cleaned_words.append(word); previous_word = word
        model = " ".join(cleaned_words)
        
        model = re.sub(r'\s+', ' ', model).strip()
        
        
        model = re.sub(r'\s+(TOTAL[A-Z]*|FLEX|R-LINE|TIPT)\s*$', '', model, flags=re.IGNORECASE)
        
        if len(model) > 50:
            words = model.split(); model = " ".join(words[:6])
        
        return model.strip()
    
    def _extract_brand_from_model(self, model: str) -> str:
        if not model: return ""
        
        try:
            model_upper = model.upper().strip()
            
            if model_upper in self.model_to_brand:
                return self.model_to_brand[model_upper]
            
            model_words = model_upper.split()
            if model_words:
                main_model = model_words[0]  # Primeira palavra (ex: TRACKER)
                if main_model in self.model_to_brand:
                    return self.model_to_brand[main_model]
            
            if len(model_words) >= 2:
                # Tenta combinações como "MODELO 1.2", "MODELO 1.0", etc.
                for i in range(2, len(model_words) + 1):
                    partial_model = " ".join(model_words[:i])
                    if partial_model in self.model_to_brand:
                        return self.model_to_brand[partial_model]
            
            for dict_model, brand in self.model_to_brand.items():
                # Verifica se a primeira palavra do modelo extraído está no dicionário
                if model_words and model_words[0] in dict_model.split():
                    return brand
            
            return ""
            
        except Exception as e:
            self.log_error(e, "_extract_brand_from_model", model=model)
            return ""
    
    # Métodos adicionais do pdf_extractor.py
    def validate_extraction(self, data: ExtractedData) -> Dict[str, bool]:
        return {
            'client_name': bool(data.client.name), 
            'client_cpf': bool(data.client.cpf), 
            'client_rg': bool(data.client.rg),
            'vehicle_model': bool(data.vehicle.model), 
            'vehicle_plate': bool(data.vehicle.plate), 
            'vehicle_chassis': bool(data.vehicle.chassis),
            'document_date': bool(data.document.date)
        }
    
    def extract_cnh_data(self, cnh_pdf_path: str) -> ThirdPartyData:
        """Extrai dados da CNH Digital usando extrator especializado"""
        try:
            cnh_extractor = CNHExtractor()
            extracted_data = cnh_extractor.extract_from_file(cnh_pdf_path)
            
            return ThirdPartyData(
                name=extracted_data.get('nome', ''),
                cpf=extracted_data.get('cpf', ''),
                rg=extracted_data.get('rg', '')
            )
        except Exception as e:
            return ThirdPartyData(name='', cpf='', rg='')
    
    def extract_payment_data(self, payment_pdf_path: str) -> Optional[PaymentData]:
        """Extrai dados de pagamento de um comprovante PDF usando extrator especializado"""
        try:
            from .payment_receipt_extractor import PaymentReceiptExtractor
            payment_extractor = PaymentReceiptExtractor()
            
            extracted_data = payment_extractor.extract_from_file(payment_pdf_path)
            
            return PaymentData(
                amount=str(extracted_data.get('valor_pago', '')) if extracted_data.get('valor_pago') is not None else '',
                payment_method=str(extracted_data.get('metodo_pagamento', '')) if extracted_data.get('metodo_pagamento') is not None else '',
                bank_name=str(extracted_data.get('banco_pagador', '')) if extracted_data.get('banco_pagador') is not None else '',
                agency=str(extracted_data.get('agencia_pagador', '')) if extracted_data.get('agencia_pagador') is not None else '',
                account=str(extracted_data.get('conta_pagador', '')) if extracted_data.get('conta_pagador') is not None else ''
            )
        except Exception as e:
            return None
    
    def extract_address_data(self, address_pdf_path: str) -> Dict[str, str]:
        try:
            from .address_extractor import extract_address_from_bill
            
            extracted_data = extract_address_from_bill(address_pdf_path)
            
            if extracted_data and extracted_data.get('LOGRADOURO'):
                address_parts = []
                if extracted_data['LOGRADOURO']:
                    address_parts.append(extracted_data['LOGRADOURO'])
                if extracted_data['NUMERO']:
                    address_parts.append(extracted_data['NUMERO'])
                if extracted_data['COMPLEMENTO']:
                    address_parts.append(extracted_data['COMPLEMENTO'])
                if extracted_data['BAIRRO']:
                    address_parts.append(f"BAIRRO {extracted_data['BAIRRO']}")
                if extracted_data['CEP']:
                    address_parts.append(f"CEP {extracted_data['CEP']}")
                if extracted_data['CIDADE'] and extracted_data['ESTADO']:
                    address_parts.append(f"{extracted_data['CIDADE']} - {extracted_data['ESTADO']}")
                
                full_address = ', '.join(filter(None, address_parts))
                
                return {
                    'address': full_address,
                    'city': extracted_data['CIDADE'] or '',
                    'cep': extracted_data['CEP'] or '',
                    'structured_data': extracted_data
                }
            
            return {'address': '', 'city': '', 'cep': ''}
            
        except Exception as e:
            pass
            return {'address': '', 'city': '', 'cep': ''}
    
    def combine_third_party_data(self, cnh_pdf_path: str, address_pdf_path: str) -> ThirdPartyData:
        try:
            third_party = self.extract_cnh_data(cnh_pdf_path)
            address_data = self.extract_address_data(address_pdf_path)
            
            third_party.address = address_data['address']
            third_party.city = address_data['city']
            third_party.cep = address_data['cep']
            
            if 'structured_data' in address_data:
                third_party._extracted_address_data = address_data
            
            third_party = self._cross_validate_third_party_data(third_party, address_data)
            
            return third_party
            
        except Exception: 
            return ThirdPartyData()
    
    def _cross_validate_third_party_data(self, third_party: ThirdPartyData, address_data: Dict[str, str]) -> ThirdPartyData:
        if third_party.cep and third_party.city:
            cep_digits = third_party.cep.replace('-', '')
        
        if third_party.address and third_party.city and third_party.cep:
            if third_party.cep not in third_party.address:
                full_address = f"{third_party.address}, CEP {third_party.cep}, {third_party.city}"
                third_party.address = full_address
        
        return third_party
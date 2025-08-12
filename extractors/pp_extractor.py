import re, sys
from pathlib import Path
from typing import Optional, Dict

if str(Path(__file__).parent.parent) not in sys.path: sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ..data import ClientData, VehicleData, DocumentData, NewVehicleData, ExtractedData
    from ..utils import LoggerMixin
except (ImportError, ValueError):
    from data import ClientData, VehicleData, DocumentData, NewVehicleData, ExtractedData
    from utils import LoggerMixin

class ProposalExtractor(LoggerMixin):
    
    def __init__(self):
        super().__init__()
        self.patterns = self._setup_regex_patterns()
    
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
    
    def extract_proposal_data(self, text: str, pdf_path: str = None) -> ExtractedData:
        client = self._extract_client_data(text)
        vehicle = self._extract_vehicle_data(text, pdf_path)
        document = self._extract_document_data(text)
        new_vehicle = self._extract_new_vehicle_data(text)
        
        return ExtractedData(client=client, vehicle=vehicle, document=document, new_vehicle=new_vehicle, payment=None, third_party=None)
    
    def _extract_client_data(self, text: str) -> ClientData:
        client = ClientData()
        
        name_patterns = [
            r'Cliente:\s*\n?\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]+?)(?:\s*Código:|\s*Endereço:|\s*CNPJ/CPF:|\n)',
            r'IDENTIFICAÇÃO DO PROPONENTE\s*\n[^\n]*\n\s*Cliente:\s*([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ\s]+?)(?:\s*Código:|\s*Endereço:)',
            r'^([A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,})',
            r'([A-Z]{2,}\s+[A-Z]{2,}\s+(?:DE|DA|DO|DOS|DAS)\s+[A-Z]{2,})',
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
        vehicle = VehicleData()
        
        used_vehicle_section = re.search(r'DESCRIÇÃO DO\(S\) VEÍCULO\(S\) USADO\(S\)(?:\s*\(PARA TROCA\))?.*?(?=VALORES|OBSERVAÇÕES|$)', text, re.DOTALL | re.IGNORECASE)
        
        if used_vehicle_section:
            section_text = used_vehicle_section.group(0)
        else:
            section_text = text
        
        plate_patterns = [
            r'Placa\s+([A-Z]{3}[0-9][A-Z0-9][0-9]{2})',
            r'([A-Z]{3}[0-9][A-Z0-9][0-9]{2})',
        ]
        
        for pattern in plate_patterns:
            plate_match = re.search(pattern, section_text)
            if plate_match: 
                vehicle.plate = plate_match.group(1)
                break
        
        model_patterns = [
            r'Modelo\s+([A-Z0-9\s\.\-]{3,50}?)(?:\s+Cor|\s+Valor|\s+Fab/Mod|\s+\d{4}/|\n)',
            rf'{re.escape(vehicle.plate) if vehicle.plate else r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"}\s+([A-Z][A-Z0-9\s\.\-]{{5,50}}?)(?:\s+(?:PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE))',
            rf'{re.escape(vehicle.plate) if vehicle.plate else r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"}\s+([A-Z0-9\s\.\-]{{3,50}}?)(?:\s+\d{{1,3}}\.\d{{3}},\d{{2}})',
            r'([A-Z][A-Z0-9\s\.\-]{10,50}?)\s+(?:PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)',
        ]
        
        for pattern in model_patterns:
            model_match = re.search(pattern, section_text, re.IGNORECASE)
            if model_match:
                raw_model = model_match.group(1).strip()
                vehicle.model = self._clean_vehicle_model(raw_model)
                if len(vehicle.model) >= 3:
                    break
        
        chassis_patterns = [
            r'Chassi\s+([A-Z0-9]{17})',
            r'([A-Z0-9]{17})',
        ]
        
        for pattern in chassis_patterns:
            chassis_match = re.search(pattern, section_text)
            if chassis_match:
                vehicle.chassis = chassis_match.group(1)
                break
                
        color_patterns = [
            r'Cor\s+([A-Z\s]+?)(?:\s+Valor|\s+Fab/Mod|\s+Avaliação|\s+\d{1,3}\.\d{3},\d{2}|\n)',
            rf'{re.escape(vehicle.plate) if vehicle.plate else r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"}\s+[A-Z0-9\s\.\-]+?\s+(PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)',
            r'\b(PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)\s+(?:\d{1,3}\.\d{3},\d{2})',
            r'\b(PRETO|BRANCO|BRANCA|PRATA|AZUL|VERMELHO|CINZA|DOURADO|VERDE|AMARELO|BEGE)\b',
        ]
        
        for pattern in color_patterns:
            color_match = re.search(pattern, section_text, re.IGNORECASE)
            if color_match:
                vehicle.color = color_match.group(1).upper().strip()
                break
        
        if not vehicle.color and pdf_path:
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
                            color_pattern = r'Cor\s+([A-Z\s]+?)(?:\s+Valor|\s+Fab/Mod|\s+Avaliação|\s+\d{1,3}\.\d{3},\d{2}|\n)'
                            pymupdf_color_match = re.search(color_pattern, pymupdf_section_text, re.IGNORECASE)
                            if pymupdf_color_match:
                                vehicle.color = pymupdf_color_match.group(1).upper()
                    except Exception:
                        pass
            
        year_model_patterns = [
            r'Fab/Mod:\s*(\d{4})\s*/\s*(\d{4})',
            r'(\d{4})\s*/\s*(\d{4})',
        ]
        
        for pattern in year_model_patterns:
            year_match = re.search(pattern, section_text)
            if year_match:
                year1, year2 = year_match.groups()
                year1_int = int(year1)
                year2_int = int(year2)
                
                if (1990 <= year1_int <= 2030 and 
                    1990 <= year2_int <= 2030 and 
                    abs(year2_int - year1_int) <= 5):
                    vehicle.year_model = f"{year1}/{year2}"
                    break
        
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
                raw_value = value_match.group(2); formatted_value = raw_value.replace('.', '').replace(',', ','); vehicle.value = formatted_value
            else:
                fallback_value_pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2})'; fallback_match = re.search(fallback_value_pattern, section_text)
                if fallback_match: vehicle.value = fallback_match.group(1)
        
        if vehicle.model and not vehicle.brand:
            vehicle.brand = self._extract_brand_from_model(vehicle.model)
        
        return vehicle
    
    def _extract_document_data(self, text: str) -> DocumentData:
        document = DocumentData()
        
        proposal_match = self.patterns['proposal_number'].search(text)
        if proposal_match: document.proposal_number = proposal_match.group(1)
        
        date_location_pattern = r'([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ\s]+),\s*(\d{1,2})\s*de\s*([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑa-záàâãéèêíïóôõöúçñ]+)\s*de\s*(\d{4})'
        
        matches = re.findall(date_location_pattern, text, re.IGNORECASE | re.MULTILINE)
        
        months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12',
            'marco': '03'
        }
        
        for city, day, month_name, year in matches:
            city_clean = city.strip().upper()
            month_name_clean = month_name.lower().strip()
            
            month_num = months.get(month_name_clean, '01')
            
            document.date = f"{day.zfill(2)}/{month_num}/{year}"
            document.location = f"{city_clean} - SP"
            break
        
        if not document.date:
            date_patterns = [r'Emissão da Proposta:\s*(\d{2}/\d{2}/\d{4})', r'(\d{1,2})\s*de\s*([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑa-záàâãéèêíïóôõöúçñ]+)\s*de\s*(\d{4})', r'\b(\d{2}/\d{2}/\d{4})\b']
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text, re.IGNORECASE)
                if date_match:
                    if len(date_match.groups()) == 3 and 'de' in pattern:
                        day, month_name, year = date_match.groups()
                        month_name_clean = month_name.lower().strip()
                        month_num = months.get(month_name_clean, '01')
                        document.date = f"{day.zfill(2)}/{month_num}/{year}"
                    else:
                        document.date = date_match.group(1)
                    break
            
            if not document.date:
                date_matches = self.patterns['date'].findall(text)
                if date_matches: document.date = date_matches[-1] if len(date_matches) > 1 else date_matches[0]
        
        location_patterns = [
            r'Cliente:.*?Cidade:\s*([A-Z\s]+)', 
            r'([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ\s]+)\s*[-\s]*\s*SP\b',
            r'([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ]+)\s*[-\s,]*\s*\d{2}\s*de\s*\w+\s*de\s*\d{4}',
            r'([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ]+)\s*[-\s,]*\s*\d{2}/\d{2}/\d{4}'
        ]
        
        for pattern in location_patterns:
            location_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if location_match and len(location_match.groups()) > 0:
                city = location_match.group(1).strip().upper()
                if 'JACAREI' in city or 'JACAREÍ' in city or 'JACARE' in city:
                    city = 'JACAREI'
                document.location = f"{city} - SP"
                break
        
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
            
            # CKDEV-NOTE: Improved color extraction to handle complex color names
            color_patterns = [
                r'Cor:\s*\n?\s*([A-Z\s]+)',
                r'Cor\s*:\s*([A-Z\s]+)',
                r'([A-Z\s]+)\s*\(cor\)',
                r'Cor\s*([A-Z\s]+)'
            ]
            
            for pattern in color_patterns:
                color_match = re.search(pattern, section_text, re.IGNORECASE)
                if color_match: 
                    color_raw = color_match.group(1).strip()
                    color_clean = color_raw.replace('\n', ' ').replace('  ', ' ').strip()
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
        
        if 'FLEXP' in model and 'RPERTEO' in model: model = re.sub(r'FLEXP\s+RPERTEO.*', 'FLEX', model)
        elif 'RPERTEO' in model: model = re.sub(r'\s*RPERTEO.*', '', model)
        elif any(corrupt in model for corrupt in ['RMEATNOUAL', 'RMEATNUAL', 'RMEATN']): model = re.sub(r'\s*RMEATN[OUAL]*.*', '', model)
        elif any(corrupt in model for corrupt in ['AUTOPMR', 'RÁETTI', 'TIOCO']): model = re.sub(r'\s+AUTO[A-Z]*$', ' AU', model, flags=re.IGNORECASE); model = re.sub(r'\s+AUTOPMR.*$', ' AU', model, flags=re.IGNORECASE)
        
        model = re.sub(r'[^A-Z0-9\s\.\-/]', ' ', model)
        
        ocr_corrections = {r'\bFRLAENXC\b': 'FLEX', r'\bFLEXP\b': 'FLEX', r'\bTOTALB\b': 'TOTAL', r'\bR-LINE\b': 'R-LINE', r'\bTIPT\b': 'TIPT', r'\b1\.4\b': '1.4', r'\b250\b': '250', r'\bTSI\b': 'TSI', r'\bAUTOMATI.*\b': 'AU'}
        for wrong, correct in ocr_corrections.items(): model = re.sub(wrong, correct, model, flags=re.IGNORECASE)
        
        words = model.split(); cleaned_words = []; previous_word = ""
        for word in words:
            if word != previous_word: cleaned_words.append(word); previous_word = word
        model = " ".join(cleaned_words)
        
        model = re.sub(r'\s+', ' ', model).strip()
        
        known_models = {r'^JETTA.*1\.4.*250.*TSI.*': 'JETTA 1.4 250 TSI', r'^NIVUS.*HIGHLINE.*200.*TSI.*': 'NIVUS HIGHLINE 200 TSI', r'^T-?CROSS.*200.*TSI.*': 'T-CROSS 200 TSI', r'^VIRTUS.*1\.0.*200.*TSI.*': 'VIRTUS 1.0 200 TSI', r'^POLO.*1\.0.*200.*TSI.*': 'POLO 1.0 200 TSI', r'^UP.*1\.0.*TSI.*': 'UP 1.0 TSI', r'^TRACKER.*': 'TRACKER'}
        for pattern, normalized in known_models.items():
            if re.search(pattern, model, re.IGNORECASE): model = normalized; break
        
        model = re.sub(r'\s+(TOTAL[A-Z]*|FLEX|R-LINE|TIPT)\s*$', '', model, flags=re.IGNORECASE)
        
        if len(model) > 50:
            words = model.split(); model = " ".join(words[:6])
        
        return model.strip()
    
    def _extract_brand_from_model(self, model: str) -> str:
        if not model: return ""
        
        try:
            try:
                from ..utils.brand_lookup import get_brand_lookup
            except ImportError:
                from utils.brand_lookup import get_brand_lookup
            
            brand_lookup = get_brand_lookup()
            brand = brand_lookup.get_brand_from_model(model)
            return brand if brand else ""
        except Exception as e:
            return ""
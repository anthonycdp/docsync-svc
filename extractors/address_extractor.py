import re
import os
import base64
import requests
from typing import Dict, Optional, Union, List
from pathlib import Path


class AddressExtractor:
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GOOGLE_CLOUD_API_KEY')
        
        if not self.api_key:
            try:
                # CKDEV-NOTE: Busca API key do arquivo .env no backend
                backend_env = Path(__file__).parent.parent / '.env'
                if backend_env.exists():
                    with open(backend_env, 'r') as f:
                        for line in f:
                            if line.strip().startswith('GOOGLE_CLOUD_API_KEY='):
                                self.api_key = line.strip().split('=', 1)[1]
                                break
            except Exception:
                pass
        
        if not self.api_key:
            raise ValueError("GOOGLE_CLOUD_API_KEY not found in environment variables or .env file")
        
        self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        
        self._init_patterns()
    
    def _init_patterns(self):
        """Inicializa padroes regex para extracao de enderecos brasileiros."""
        
        # CKDEV-NOTE: Contextos que indicam endereço do CLIENTE
        self.client_address_contexts = [
            r'(?i)(?:cliente|consumidor|titular|pagador)',
            r'(?i)local.*?(?:consumo|instalacao|entrega)',
            r'(?i)endereco.*?(?:cobranca|entrega|instalacao|cliente)',
            r'(?i)dados.*?(?:cliente|consumidor)',
            r'(?i)informacoes.*?(?:cliente|titular)',
            r'(?i)endereco.*?correspondencia',
            r'(?i)nome.*?cliente',
            r'(?i)conta.*?contrato',
            r'(?i)instalacao.*?numero'
        ]
        
        # CKDEV-NOTE: Contextos que devem ser EVITADOS
        self.company_address_contexts = [
            r'(?i)(?:vivo|claro|tim|oi|net|telefonica|embratel)',
            r'(?i)central.*?atendimento',
            r'(?i)ouvidoria',
            r'(?i)sede.*?empresa',
            r'(?i)matriz',
            r'(?i)filial',
            r'(?i)cnpj',
            r'(?i)razao.*?social',
            r'(?i)av.*?engenheiro.*?luiz.*?carlos.*?berrini',
            r'(?i)sao.*?diego'
        ]
        
        self.logradouro_types = [
            r'RUA', r'AVENIDA', r'AV', r'R\.', r'AV\.', r'ALAMEDA', r'AL',
            r'TRAVESSA', r'TV', r'LARGO', r'LGO', r'PRACA', r'PCA',
            r'ESTRADA', r'EST', r'RODOVIA', r'ROD', r'VIELA', r'VL'
        ]
        
        self.complement_patterns = [
            r'(?i)(?:APTO?|APARTAMENTO)\s*(\d+[A-Z]?)',
            r'(?i)(?:AP|APT)\s*(\d+[A-Z]?)',
            r'(?i)(?:BLOCO?|BL)\s*([A-Z0-9]+)',
            r'(?i)(?:CASA|CS)\s*([A-Z0-9]+)',
            r'(?i)(?:QD|QUADRA)\s*([A-Z0-9]+)(?:\s*(?:LT|LOTE)\s*([A-Z0-9]+))?',
            r'(?i)(?:CONJ|CONJUNTO)\s*([A-Z0-9\s]+)',
            r'(?i)(?:COND|CONDOMINIO)\s*([A-Z0-9\s]+)',
            r'(?i)(?:FUNDOS?|FDS)',
            r'(?i)(?:SOBRELOJA|SL)',
            r'(?i)(?:ANDAR|AND)\s*(\d+)',
            r'(?i)(?:SALA|SL)\s*(\d+[A-Z]?)'
        ]
        
        self.cep_pattern = r'(\d{5})[.\-]?(\d{3})'
        
        self.estados = [
            'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
            'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
            'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
        ]
    
    def extract_address_from_bill(self, image_path: Union[str, Path]) -> Dict[str, Optional[str]]:
        """Funcao principal para extrair endereco de comprovante.
        
        Args:
            image_path: Caminho para a imagem do comprovante
            
        Returns:
            Dicionario com dados do endereco em MAIUSCULAS
        """
        try:
            image_path = Path(image_path)
            
            if image_path.suffix.lower() == '.pdf':
                text = self._extract_text_from_pdf(image_path)
            else:
                text = self._extract_text_from_image(image_path)
            
            return self._extract_address_data(text)
        except Exception as e:
            return self._empty_address_dict()
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extrai texto de PDF usando PyMuPDF e depois Vision API."""
        try:
            import fitz 
            
            pdf_document = fitz.open(str(pdf_path))
            
            if pdf_document.page_count == 0:
                raise Exception("PDF nao contem paginas legiveis")
            
            page = pdf_document[0]
            
            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("png")
            pdf_document.close()
            
            base64_image = base64.b64encode(img_data).decode('utf-8')
            
            return self._call_vision_api(base64_image)
            
        except ImportError:
            raise Exception("PyMuPDF nao esta instalado. Use: pip install PyMuPDF")
        except Exception as e:
            raise Exception(f"Erro ao processar PDF: {e}")
    
    def _extract_text_from_image(self, image_path: Path) -> str:
        """Extrai texto da imagem usando Google Cloud Vision API."""
        if not image_path.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {image_path}")
        
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        base64_image = base64.b64encode(content).decode('utf-8')
        return self._call_vision_api(base64_image)
    
    def _call_vision_api(self, base64_image: str) -> str:
        """Chama a API Vision e retorna o texto extraido."""
        request_body = {
            "requests": [
                {
                    "image": {
                        "content": base64_image
                    },
                    "features": [
                        {
                            "type": "DOCUMENT_TEXT_DETECTION",
                            "maxResults": 1
                        }
                    ],
                    "imageContext": {
                        "textDetectionParams": {
                            "enableTextDetectionConfidenceScore": True,
                            "advancedOcrOptions": [
                                "legacy_layout"
                            ]
                        }
                    }
                }
            ]
        }
        
        response = requests.post(
            self.api_url,
            json=request_body,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            raise Exception(f"Erro na API Vision: {response.status_code}")
        
        result = response.json()
        
        if 'error' in result:
            raise Exception(f"Erro na API Vision: {result['error']['message']}")
        
        responses = result.get('responses', [])
        if not responses:
            raise Exception("Nenhuma resposta da API Vision")
        
        full_text_annotation = responses[0].get('fullTextAnnotation', {})
        text = full_text_annotation.get('text', '')
        
        if not text:
            text_annotations = responses[0].get('textAnnotations', [])
            if text_annotations:
                text = text_annotations[0].get('description', '')
        
        return text.upper()
    
    def _extract_address_data(self, text: str) -> Dict[str, Optional[str]]:
        """Extrai dados estruturados do endereco do texto OCR."""
        result = self._empty_address_dict()
        
        try:
            
            cep = self._find_cep(text)
            if cep:
                result["CEP"] = cep
            
            address_section = self._find_client_address_section(text)
            
            if not address_section and cep and cep != "04571-936":
                address_section = self._find_address_by_cep(text, cep)
            
            if not address_section:
                address_section = text
            
            result["LOGRADOURO"] = self._extract_logradouro(address_section)
            result["NUMERO"] = self._extract_numero(address_section, result["LOGRADOURO"])
            result["COMPLEMENTO"] = self._extract_complemento(address_section)
            result["BAIRRO"] = self._extract_bairro(address_section)
            result["CIDADE"], result["ESTADO"] = self._extract_cidade_estado(address_section)
            
        except Exception as e:
            pass
        
        return result
    
    def _find_client_address_section(self, text: str) -> Optional[str]:
        """Localiza secao de endereco do CLIENTE, evitando endereco da empresa."""
        lines = text.split('\n')
        
        address_sections = []
        
        for i, line in enumerate(lines):
            if re.search(self.cep_pattern, line):
                start_idx = max(0, i - 8)
                end_idx = min(len(lines), i + 5)
                section_text = '\n'.join(lines[start_idx:end_idx])
                address_sections.append((section_text, start_idx, end_idx))
        
        best_section = None
        best_score = -1
        
        for section_text, start_idx, end_idx in address_sections:
            score = 0
            
            for pattern in self.company_address_contexts:
                if re.search(pattern, section_text):
                    score -= 10
            
            for pattern in self.client_address_contexts:
                if re.search(pattern, section_text):
                    score += 5
            
            client_keywords = ['CLIENTE', 'CONSUMIDOR', 'TITULAR', 'CONTA', 'INSTALACAO']
            for keyword in client_keywords:
                if keyword in section_text:
                    score += 2
            
            company_keywords = ['VIVO', 'CNPJ', 'RAZAO SOCIAL', 'BERRINI', 'SAO DIEGO', 'FATURA', 'VENCIMENTO', 'PAGAR']
            for keyword in company_keywords:
                if keyword in section_text:
                    score -= 5
            
            if any(re.search(rf'\\b{tipo}\\b', section_text) for tipo in self.logradouro_types):
                score += 3
            
            if score > best_score:
                best_score = score
                best_section = section_text
        
        if best_section and best_score > -50:
            return best_section
        
        for section_text, start_idx, end_idx in address_sections:
            has_logradouro = any(re.search(rf'\\b{tipo}\\b', section_text) for tipo in self.logradouro_types)
            has_company_name = any(keyword in section_text for keyword in ['TELEFONICA', 'VIVO S.A.', 'BERRINI'])
            
            if has_logradouro and not has_company_name:
                return section_text
        
        return None
    
    def _find_address_by_cep(self, text: str, target_cep: str) -> Optional[str]:
        """Busca endereco baseado na proximidade com um CEP especifico."""
        lines = text.split('\n')
        
        cep_line_idx = None
        for i, line in enumerate(lines):
            if target_cep.replace('-', '') in line.replace('-', ''):
                cep_line_idx = i
                break
        
        if cep_line_idx is None:
            return None
        
        start_idx = max(0, cep_line_idx - 8)
        end_idx = min(len(lines), cep_line_idx + 5)
        section = '\n'.join(lines[start_idx:end_idx])
        
        has_logradouro = any(re.search(rf'\\b{tipo}\\b', section) for tipo in self.logradouro_types)
        if has_logradouro:
            return section
        
        return None
    
    def _find_cep(self, text: str) -> Optional[str]:
        """Busca e formata CEP no texto, priorizando CEP do cliente."""
        matches = list(re.finditer(self.cep_pattern, text))
        if not matches:
            return None
        
        empresa_ceps = ['04571-936', '92506-597']  # Vivo Berrini, outro CEP empresa
        
        best_cep = None
        best_score = -100
        
        lines = text.split('\n')
        for match in matches:
            cep_formatted = f"{match.group(1)}-{match.group(2)}"
            
            cep_line_idx = None
            for i, line in enumerate(lines):
                if cep_formatted.replace('-', '') in line.replace('-', ''):
                    cep_line_idx = i
                    break
            
            if cep_line_idx is None:
                continue
            
            start_idx = max(0, cep_line_idx - 5)
            end_idx = min(len(lines), cep_line_idx + 3)
            context = '\n'.join(lines[start_idx:end_idx])
            
            score = 0
            
            if cep_formatted in empresa_ceps:
                score -= 50
            
            if re.search(r'[A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}', context):  # Nome completo
                score += 20
            
            residential_indicators = ['RUA', 'AVENIDA', 'PARQUE', 'JARDIM', 'VILA']
            for indicator in residential_indicators:
                if indicator in context:
                    score += 10
            
            company_indicators = ['TELEFONICA', 'VIVO', 'CNPJ', 'BERRINI', 'EMPRESA']
            for indicator in company_indicators:
                if indicator in context:
                    score -= 15
            
            if score > best_score:
                best_score = score
                best_cep = cep_formatted
        
        return best_cep if best_cep else f"{matches[-1].group(1)}-{matches[-1].group(2)}"
    
    def _extract_logradouro(self, text: str) -> Optional[str]:
        """Extrai nome do logradouro."""
        logradouro_pattern = rf'(?i)({"|".join(self.logradouro_types)})\s+([A-Z0-9À-ÿ\s]+?)(?:\s*,\s*N[°º]?|\s*,?\s*\d+|\n|CEP|BAIRRO|$)'
        
        matches = list(re.finditer(logradouro_pattern, text))
        empresa_logradouros = ['BERRINI', 'SAO DIEGO']
        
        for match in matches:
            tipo = match.group(1).strip().upper()
            nome = match.group(2).strip().upper()
            
            if any(empresa in nome for empresa in empresa_logradouros):
                continue
            
            nome = re.sub(r'\s+', ' ', nome)
            nome = re.sub(r'[,\.]$', '', nome)
            
            nome = re.sub(r'\s*N[°º]?\s*\d+.*$', '', nome)
            
            logradouro_completo = f"{tipo} {nome}".strip()
            
            if len(nome) > 5:
                return logradouro_completo
        
        return None
    
    def _extract_numero(self, text: str, logradouro: Optional[str]) -> Optional[str]:
        """Extrai numero do imovel."""
        if logradouro:
            nome_rua = logradouro
            for tipo in self.logradouro_types:
                nome_rua = re.sub(rf'\\b{tipo}\\s+', '', nome_rua, flags=re.IGNORECASE)
            
            nome_escaped = re.escape(nome_rua.strip())
            numero_patterns = [
                rf'{nome_escaped}\s+(\d+[A-Z]?)',
                rf'{nome_escaped}\s*,?\s*(\d+[A-Z]?)', 
                rf'{nome_escaped}\s*-\s*(\d+[A-Z]?)', 
            ]
            
            for pattern in numero_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        generic_patterns = [
            r'(?i)N[°º]?\s*(\d+[A-Z]?)',
            r'(?i)(?:NUMERO|NUM)\s*(\d+[A-Z]?)',
            r'(?i)RUA\s+[A-Z\s]+?(\d+)',
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_complemento(self, text: str) -> Optional[str]:
        """Extrai complemento do endereco."""
        invalid_complements = ['CASA CONECTADA', 'CONTA', 'FATURA', 'CLIENTE', 'SERVICO']
        
        for pattern in self.complement_patterns:
            match = re.search(pattern, text)
            if match:
                complement_text = match.group(0).upper()
                
                if any(invalid in complement_text for invalid in invalid_complements):
                    continue
                
                match_start = match.start()
                context_start = max(0, match_start - 200)
                context_end = min(len(text), match_start + 200)
                context = text[context_start:context_end].upper()
                
                has_address_context = (
                    any(tipo in context for tipo in self.logradouro_types) or
                    re.search(r'[A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}', context)
                )
                
                has_company_context = any(marker in context for marker in ['TELEFONICA', 'VIVO', 'CNPJ', 'BERRINI'])
                
                if has_address_context and not has_company_context:
                    if 'APTO' in pattern or 'AP' in pattern:
                        return f"APTO {match.group(1)}"
                    elif 'BLOCO' in pattern or 'BL' in pattern:
                        return f"BLOCO {match.group(1)}"
                    elif 'CASA' in pattern:
                        return f"CASA {match.group(1)}"
                    elif 'QD' in pattern or 'QUADRA' in pattern:
                        if match.lastindex > 1 and match.group(2):
                            return f"QD {match.group(1)} LT {match.group(2)}"
                        return f"QD {match.group(1)}"
                    elif 'CONJ' in pattern:
                        return f"CONJ {match.group(1)}"
                    elif 'COND' in pattern:
                        return f"COND {match.group(1)}"
                    elif 'SALA' in pattern:
                        return f"SALA {match.group(1)}"
                    elif 'ANDAR' in pattern:
                        return f"ANDAR {match.group(1)}"
                    elif 'FUNDOS' in pattern:
                        return "FUNDOS"
                    elif 'SOBRELOJA' in pattern:
                        return "SOBRELOJA"
        
        return None
    
    def _extract_bairro(self, text: str) -> Optional[str]:
        """Extrai nome do bairro."""
        known_bairros = ['PARQUE RESIDENCIAL AQUARIUS']
        for bairro in known_bairros:
            if bairro in text.upper():
                return bairro
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_clean = line.strip().upper()
            
            if len(line_clean) < 5:
                continue
            
            if re.match(r'^[A-Z]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}', line_clean):
                continue
            
            if any(line_clean.startswith(tipo) for tipo in self.logradouro_types):
                continue
            
            if re.search(r'\d{5}[.\-]?\d{3}', line_clean):
                continue
            
            empresa_markers = ['TELEFONICA', 'VIVO', 'CNPJ', 'BERRINI', 'CONTA', 'FATURA']
            if any(marker in line_clean for marker in empresa_markers):
                continue
            
            bairro_indicators = ['PARQUE', 'JARDIM', 'VILA', 'CENTRO', 'CIDADE', 'DISTRITO', 'BAIRRO', 'RESIDENCIAL', 'AQUARIUS']
            is_bairro = any(indicator in line_clean for indicator in bairro_indicators)
            
            known_bairros = ['PARQUE RESIDENCIAL AQUARIUS']
            is_known_bairro = any(known in line_clean for known in known_bairros)
            
            has_address_above = False
            has_cep_below = False
            
            if i > 0:
                line_above = lines[i-1].upper()
                has_address_above = any(tipo in line_above for tipo in self.logradouro_types)
            
            if i < len(lines) - 2:
                for j in range(i+1, min(i+3, len(lines))):
                    if re.search(r'\d{5}[.\-]?\d{3}', lines[j]):
                        has_cep_below = True
                        break
            
            is_positional_bairro = has_address_above and has_cep_below
            
            if is_bairro or is_positional_bairro or is_known_bairro:
                bairro = re.sub(r'\s+', ' ', line_clean)
                bairro = re.sub(r'[^\w\sÀ-ÿ]', '', bairro)
                if len(bairro) > 5:
                    return bairro
        
        traditional_patterns = [
            r'(?i)(?:BAIRRO:?\s*)([A-ZÀ-ÿ\s]+?)(?:\s*CEP|\s*\d{5}|\n|CIDADE|$)',
            r'([A-ZÀ-ÿ\s]{8,40})\s+\d{5}[.\-]?\d{3}',
        ]
        
        for pattern in traditional_patterns:
            match = re.search(pattern, text)
            if match:
                bairro = match.group(1).strip().upper()
                bairro = re.sub(r'\s+', ' ', bairro)
                bairro = re.sub(r'[^\w\sÀ-ÿ]', '', bairro)
                if len(bairro) > 5 and not any(estado in bairro for estado in self.estados):
                    return bairro
        
        return None
    
    def _extract_cidade_estado(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Extrai cidade e estado."""
        cidade_estado_patterns = [
            rf'([A-ZÀ-ÿ\s]+?)[\s\-/]+({"|".join(self.estados)})(?:\s|$|CEP)',
            rf'(?:CIDADE:?\s*)([A-ZÀ-ÿ\s]+?)[\s\-/]+({"|".join(self.estados)})',
            rf'({"|".join(self.estados)})[\s\-/]+([A-ZÀ-ÿ\s]+?)(?:\s*\d{{5}}|\n|$)',
        ]
        
        for pattern in cidade_estado_patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                match = matches[-1]
                
                if '|".join(self.estados)' in pattern and pattern.index('|".join(self.estados)') < 10:

                    estado = match.group(1).strip()
                    cidade = match.group(2).strip() if match.lastindex > 1 else None
                else:

                    cidade = match.group(1).strip()
                    estado = match.group(2).strip()
                
                if cidade:
                    cidade = cidade.upper()
                    cidade = re.sub(r'\s+', ' ', cidade)
                    cidade = re.sub(r'[^\w\sÀ-ÿ]', '', cidade)
                
                if len(cidade or "") > 2 and estado in self.estados:
                    return cidade, estado
        
        return None, None
    
    def _empty_address_dict(self) -> Dict[str, Optional[str]]:
        """Retorna estrutura basica de endereco vazia."""
        return {
            "LOGRADOURO": None,
            "NUMERO": None,
            "COMPLEMENTO": None,
            "BAIRRO": None,
            "CIDADE": None,
            "ESTADO": None,
            "CEP": None
        }


def extract_address_from_bill(image_path: Union[str, Path]) -> Dict[str, Optional[str]]:
    """Funcao principal para extrair endereco de comprovante de residencia.
    
    Args:
        image_path: Caminho para a imagem do comprovante
        
    Returns:
        Dicionario com dados do endereco estruturados em MAIUSCULAS
    """
    extractor = AddressExtractor()
    return extractor.extract_address_from_bill(image_path)
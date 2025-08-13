import re
import os
import base64
import requests
from typing import Dict, Optional, Union, List
from pathlib import Path


class PaymentReceiptExtractor:
    
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
    
    def extract_from_file(self, file_path: Union[str, Path]) -> Dict[str, Union[str, float, None]]:
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']:
            return self._extract_from_image(file_path)
        elif file_path.suffix.lower() == '.pdf':
            return self._extract_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
    
    def _extract_from_image(self, image_path: Path) -> Dict[str, Union[str, float, None]]:
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        base64_image = base64.b64encode(content).decode('utf-8')
        
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
                    ]
                }
            ]
        }
        
        response = requests.post(
            self.api_url,
            json=request_body,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            raise Exception(f"Vision API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'error' in result:
            raise Exception(f"Vision API error: {result['error']['message']}")
        
        responses = result.get('responses', [])
        if not responses:
            raise Exception("No response from Vision API")
        
        full_text_annotation = responses[0].get('fullTextAnnotation', {})
        text = full_text_annotation.get('text', '')
        
        if not text:
            text_annotations = responses[0].get('textAnnotations', [])
            if text_annotations:
                text = text_annotations[0].get('description', '')
        
        return self._extract_payment_data_from_text(text)
    
    def _extract_from_pdf(self, pdf_path: Path) -> Dict[str, Union[str, float, None]]:
        try:
            import fitz
            
            pdf_document = fitz.open(str(pdf_path))
            
            if pdf_document.page_count == 0:
                raise Exception("PDF contains no readable pages")
            
            full_text = ""
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                mat = fitz.Matrix(3.0, 3.0)
                pix = page.get_pixmap(matrix=mat)
                
                img_data = pix.tobytes("png")
                base64_image = base64.b64encode(img_data).decode('utf-8')
                
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
                            ]
                        }
                    ]
                }
                
                response = requests.post(
                    self.api_url,
                    json=request_body,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code != 200:
                    continue
                
                result = response.json()
                
                if 'error' in result:
                    continue 
                
                responses = result.get('responses', [])
                if responses:
                    full_text_annotation = responses[0].get('fullTextAnnotation', {})
                    page_text = full_text_annotation.get('text', '')
                    
                    if not page_text:
                        text_annotations = responses[0].get('textAnnotations', [])
                        if text_annotations:
                            page_text = text_annotations[0].get('description', '')
                    
                    full_text += page_text + "\n"
            
            pdf_document.close()
            return self._extract_payment_data_from_text(full_text)
            
        except ImportError:
            raise Exception("PyMuPDF not installed. To process PDFs, install: pip install PyMuPDF")
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise Exception(f"PDF may be password protected or have digital signature issues: {e}")
            raise Exception(f"Error processing PDF: {e}")
    
    def _extract_payment_data_from_text(self, text: str) -> Dict[str, Union[str, float, None]]:
        data = {
            "valor_pago": None,
            "metodo_pagamento": None,
            "banco_pagador": None,
            "agencia_pagador": None,
            "conta_pagador": None
        }
        
        original_text = text
        
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        data["valor_pago"] = self._extract_payment_amount(text)
        
        data["metodo_pagamento"] = self._extract_payment_method(text)
        
        payer_section = self._extract_payer_section(original_text)
        receiver_section = self._extract_receiver_section(original_text)
        
        if payer_section:

            section_bank = self._extract_bank_from_section(payer_section)
            section_agency = self._extract_agency_from_section(payer_section)
            section_account = self._extract_account_from_section(payer_section)
            

            data["banco_pagador"] = section_bank if section_bank else self._extract_payer_bank(text)
            data["agencia_pagador"] = section_agency if section_agency else self._extract_payer_agency(text)
            data["conta_pagador"] = section_account if section_account else self._extract_payer_account(text)
        else:

            extracted_agency = self._extract_payer_agency(text)
            extracted_account = self._extract_payer_account(text)
            
            data["banco_pagador"] = self._extract_payer_bank(text)
            
            if not data["banco_pagador"]:
                validated_bank = self._cross_validate_bank_with_context(text, extracted_agency, extracted_account)
                if validated_bank:
                    data["banco_pagador"] = validated_bank
            
            data["agencia_pagador"] = extracted_agency
            data["conta_pagador"] = extracted_account

        receiver_bank = None
        if receiver_section:
            receiver_bank = self._extract_bank_from_section(receiver_section)
        else:
            receiver_bank = self._extract_receiver_bank(text)
        
        
        # CKDEV-NOTE: Debug mode disabled - no OCR text logging
        
        return data
    
    def _extract_payment_amount(self, text: str) -> Optional[float]:
        value_patterns = [

            r'(?:valor\s+pago|VALOR\s+PAGO)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:valor\s+da\s+transf|VALOR\s+DA\s+TRANSF)[^\d]*R?\$?\s*([\d.,]+)',
            r'(?:valor|VALOR)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:valor\s+da\s+ted|VALOR\s+DA\s+TED)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:total\s+do\s+deposito|TOTAL\s+DO\s+DEPOSITO)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:importancia|IMPORTANCIA)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:quantia|QUANTIA)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?:total|TOTAL)[:\s]*R?\$?\s*([\d.,]+)',
            r'(?<!ag[:\s])(?<!agencia[:\s])(?<!conta[:\s])R\$\s*([\d.,]+)',
            r'(?:^|\s)(\d{1,3}(?:\.\d{3})*,\d{2})(?:\s|$)',
        ]
        
        potential_values = []
        for pattern in value_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                value_str = match.group(1)
                if re.match(r'^\d{4}$', value_str.strip()):
                    continue
                    
                try:
                    value_str = value_str.replace(' ', '')
                    
                    if ',' in value_str:
                        parts = value_str.split(',')
                        if len(parts) == 2 and len(parts[1]) <= 2:
                            value_str = parts[0].replace('.', '') + '.' + parts[1]
                        elif len(parts) == 3:
                            value_str = parts[0] + parts[1] + '.' + parts[2]
                        else:
                            value_str = value_str.replace(',', '')
                    elif '.' in value_str:
                        parts = value_str.split('.')
                        if len(parts[-1]) == 3:
                            value_str = value_str.replace('.', '')
                    
                    value = float(value_str)
                    
                    if value > 999 and value < 10000 and ',' not in match.group(1) and '.' not in match.group(1):
                        continue
                    
                    potential_values.append((value, match.start(), pattern))
                    
                except ValueError:
                    continue
        
        if potential_values:
            potential_values.sort(key=lambda x: (x[1], x[2]))
            return potential_values[0][0]
        
        return None
    
    def _extract_payment_method(self, text: str) -> Optional[str]:
        text_upper = text.upper()
        
        if any(pix_term in text_upper for pix_term in ['PIX', 'COMPROVANTE DE TRANSFERENCIA PIX']):
            return 'PIX'
        elif any(ted_term in text_upper for ted_term in ['TED', 'COMPROVANTE DE TED']):
            return 'TED'
        elif 'DOC' in text_upper:
            return 'DOC'
        elif 'DEPOSITO' in text_upper:
            return 'DEPÓSITO'
        else:
            return 'TRANSFERÊNCIA'
    
    def _extract_payer_bank(self, text: str) -> Optional[str]:
        """
        CKDEV-NOTE: Lógica aprimorada para distinguir banco pagador vs favorecido
        Prioriza associações diretas com agência/conta do pagador
        """
        
        # CKDEV-NOTE: Primeiro tenta associar banco com agência/conta extraída
        extracted_agency = self._extract_payer_agency(text)
        extracted_account = self._extract_payer_account(text)
        
        # Estratégia 0: Padrão específico para TED da CAIXA (formato "BANCO: CAIXA ECONOMICA FEDERAL")
        caixa_ted_patterns = [
            r'(?:remetente|pagador)[\s\S]*?banco:\s*(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL)',
            r'banco:\s*(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL)[\s\S]*?(?:ag|agencia|agência)',
        ]
        
        for pattern in caixa_ted_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return self._normalize_bank_name(match.group(1))
        
        # Estratégia 1: Buscar banco próximo aos dados do pagador (agência/conta)
        if extracted_agency:
            proximity_patterns = [
                # Procura banco antes da agência (até 3 linhas)
                rf'(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL|CEF)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                rf'(ITAU\s+UNIBANCO\s+S\.?A\.?|ITA\s+UNIBANCO\s+S\.?A\.?|BANCO\s+ITAU|BCO\s+ITAU)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                rf'(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                rf'(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO|BRADESCO)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                rf'(BANCO\s+DO\s+BRASIL|BCO\s+DO\s+BRASIL)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                rf'(NUBANK|NU\s+PAGAMENTOS)[\s\S]{{0,150}}?{re.escape(extracted_agency)}',
                
                # Procura banco depois da agência (até 2 linhas)
                rf'{re.escape(extracted_agency)}[\s\S]{{0,100}}?(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL|CEF)',
                rf'{re.escape(extracted_agency)}[\s\S]{{0,100}}?(ITAU\s+UNIBANCO\s+S\.?A\.?|ITA\s+UNIBANCO\s+S\.?A\.?|BANCO\s+ITAU|BCO\s+ITAU)',
                rf'{re.escape(extracted_agency)}[\s\S]{{0,100}}?(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)',
                rf'{re.escape(extracted_agency)}[\s\S]{{0,100}}?(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO|BRADESCO)',
                rf'{re.escape(extracted_agency)}[\s\S]{{0,100}}?(BANCO\s+DO\s+BRASIL|BCO\s+DO\s+BRASIL)',
            ]
            
            for pattern in proximity_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    bank = match.group(1).upper()
                    return self._normalize_bank_name(bank)
        
        # Estratégia 2: Buscar na estrutura de comprovante PIX (primeira instituição mencionada)
        # CKDEV-NOTE: Em comprovantes PIX, dados do remetente aparecem antes dos do favorecido
        pix_structure_patterns = [
            # Procura primeira menção de instituição após dados básicos
            r'(?:cpf|documento)[\s\S]*?institui[çc][ãa]o[\s\n]*(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL|CEF)',
            r'(?:cpf|documento)[\s\S]*?institui[çc][ãa]o[\s\n]*(ITAU\s+UNIBANCO\s+S\.?A\.?|ITA\s+UNIBANCO\s+S\.?A\.?)',
            r'(?:cpf|documento)[\s\S]*?institui[çc][ãa]o[\s\n]*(BANCO\s+SANTANDER|BCO\s+SANTANDER)',
            r'(?:cpf|documento)[\s\S]*?institui[çc][ãa]o[\s\n]*(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO)',
            r'(?:cpf|documento)[\s\S]*?institui[çc][ãa]o[\s\n]*(BANCO\s+DO\s+BRASIL|BCO\s+DO\s+BRASIL)',
            
            # Linha que contém apenas o nome da instituição (típico de PIX)
            r'^(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL|CEF)$',
            r'^(ITAU\s+UNIBANCO\s+S\.?A\.?|ITA\s+UNIBANCO\s+S\.?A\.?)$',
            r'^(BANCO\s+SANTANDER|BCO\s+SANTANDER)$',
            r'^(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO)$',
            r'^(BANCO\s+DO\s+BRASIL|BCO\s+DO\s+BRASIL)$',
        ]
        
        for pattern in pix_structure_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                bank = match.group(1).upper()
                # CKDEV-NOTE: Verifica se não é o banco do favorecido
                if not self._is_receiver_bank(text, bank):
                    return self._normalize_bank_name(bank)
        
        # Estratégia 3: Buscar explicitamente seções do pagador/remetente
        payer_section_patterns = [
            r'(?:dados\s+da\s+transfer[êe]ncia|remetente)[\s\S]*?(?:nome\s+favorecido|favorecido|para)',
            r'(?:pagador|dados\s+do\s+pagador)[\s\S]*?(?:dados\s+do\s+favorecido|benefici[áa]rio)',
        ]
        
        for section_pattern in payer_section_patterns:
            section_match = re.search(section_pattern, text, re.IGNORECASE | re.DOTALL)
            if section_match:
                section = section_match.group(0)
                
                bank_in_section_patterns = [
                    r'(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL|CEF)',
                    r'(ITAU\s+UNIBANCO\s+S\.?A\.?|ITA\s+UNIBANCO\s+S\.?A\.?)',
                    r'(BANCO\s+SANTANDER|BCO\s+SANTANDER)',
                    r'(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO)',
                    r'(BANCO\s+DO\s+BRASIL|BCO\s+DO\s+BRASIL)',
                    r'(NUBANK|NU\s+PAGAMENTOS)',
                ]
                
                for bank_pattern in bank_in_section_patterns:
                    bank_match = re.search(bank_pattern, section, re.IGNORECASE)
                    if bank_match:
                        bank = bank_match.group(1).upper()
                        return self._normalize_bank_name(bank)
        
        return None
    
    def _normalize_bank_name(self, bank_name: str) -> str:
        """CKDEV-NOTE: Normaliza nomes de bancos para formato padronizado"""
        bank_upper = bank_name.upper()
        
        if 'CAIXA' in bank_upper and ('ECONOMICA' in bank_upper or 'ECONÔMICA' in bank_upper or 'FEDERAL' in bank_upper):
            return 'CAIXA ECONÔMICA FEDERAL'
        elif 'CEF' == bank_upper.strip():
            return 'CAIXA ECONÔMICA FEDERAL'
        elif 'ITAU' in bank_upper or 'ITAÚ' in bank_upper:
            return 'ITAÚ UNIBANCO S.A.'
        elif 'SANTANDER' in bank_upper:
            return 'BANCO SANTANDER (BRASIL) S.A.'
        elif 'BRADESCO' in bank_upper:
            return 'BCO BRADESCO S.A.'
        elif 'BRASIL' in bank_upper and ('BCO' in bank_upper or 'BANCO' in bank_upper):
            return 'BANCO DO BRASIL S.A.'
        elif 'NUBANK' in bank_upper or 'NU PAGAMENTOS' in bank_upper:
            return 'NU PAGAMENTOS S.A.'
        else:
            return bank_name.strip()
    
    def _is_receiver_bank(self, text: str, bank_name: str) -> bool:
        """CKDEV-NOTE: Verifica se o banco está associado ao favorecido/destinatário"""
        receiver_indicators = [
            rf'(?:favorecido|benefici[áa]rio|para|destino|destinat[áa]rio)[\s\S]{{0,200}}?{re.escape(bank_name)}',
            rf'institui[çc][ãa]o\s+favorecido[\s\S]{{0,100}}?{re.escape(bank_name)}',
            rf'nome\s+favorecido[\s\S]{{0,300}}?{re.escape(bank_name)}',
        ]
        
        for pattern in receiver_indicators:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                return True
        
        return False
    
    def _cross_validate_bank_with_context(self, text: str, agency: Optional[str], account: Optional[str]) -> Optional[str]:
        if agency:
            context_patterns = [
                rf'(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ|BCO\s+ITAÚ|ITAÚ|ITAU)[\s\S]{{0,200}}?{re.escape(agency)}',
                rf'(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)[\s\S]{{0,200}}?{re.escape(agency)}',
                rf'(BCO\s+BRADESCO|BANCO\s+BRADESCO|BRADESCO)[\s\S]{{0,200}}?{re.escape(agency)}',
                rf'{re.escape(agency)}[\s\S]{{0,200}}?(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ|BCO\s+ITAÚ|ITAÚ|ITAU)',
                rf'{re.escape(agency)}[\s\S]{{0,200}}?(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)',
                rf'{re.escape(agency)}[\s\S]{{0,200}}?(BCO\s+BRADESCO|BANCO\s+BRADESCO|BRADESCO)',
            ]
            
            for pattern in context_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    bank = match.group(1).upper()
                    if 'ITAÚ' in bank or 'ITAU' in bank:
                        return 'ITAÚ UNIBANCO S.A.'
                    elif 'SANTANDER' in bank:
                        return 'BANCO SANTANDER (BRASIL) S.A.'
                    elif 'BRADESCO' in bank:
                        return 'BCO BRADESCO S.A.'
        
        if account:
            context_patterns = [
                rf'(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ|BCO\s+ITAÚ|ITAÚ|ITAU)[\s\S]{{0,300}}?{re.escape(account)}',
                rf'(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)[\s\S]{{0,300}}?{re.escape(account)}',
                rf'{re.escape(account)}[\s\S]{{0,300}}?(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ|BCO\s+ITAÚ|ITAÚ|ITAU)',
                rf'{re.escape(account)}[\s\S]{{0,300}}?(BANCO\s+SANTANDER|BCO\s+SANTANDER|SANTANDER)',
            ]
            
            for pattern in context_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    bank = match.group(1).upper()
                    if 'ITAÚ' in bank or 'ITAU' in bank:
                        return 'ITAÚ UNIBANCO S.A.'
                    elif 'SANTANDER' in bank:
                        return 'BANCO SANTANDER (BRASIL) S.A.'
        
        return None
    
    def _extract_payer_agency(self, text: str) -> Optional[str]:
        agency_patterns = [
            r'(?:pagador)[\s\S]{0,150}?ag[êe]ncia\s+(\d{3,5}[-]?\d?)\s+conta',
            r'(?:pagador)[\s\S]{0,100}?(?:agencia|agência|ag)[:\s]*(\d{3,5}[-]?\d?)',
            r'(?:dados\s+do\s+pagador|remetente|origem)[\s\S]*?(?:agencia|agência|ag)[:\s]*(\d{3,5}[-]?\d?)',
            r'(?:conta\s+debitada|debitado)[\s\S]*?(?:agencia|agência|ag)[:\s]*(\d{3,5}[-]?\d?)',
            
            r'(?:agencia|agência|ag\.?)[:\s]*(\d{3,5}[-]?\d?)',
            
            r'(?:agencia|agência|ag)[\s\n]*[:\-]?[\s\n]*(\d{3,5}[-]?\d?)(?:\s|$|\n)',
            
            r'(?:bradesco|itau|itaú|santander|caixa|bb)[\s\S]*?(?:ag|agência|agencia)[:\s]*(\d{3,5}[-]?\d?)',
            
            r'(?:ag|agência|agencia)[\s.:]*(\d{3,5})[\s/\-]*(?:conta|cc)',
            
            r'(?:^|\s)ag\s+(\d{4})(?:\s|$)',
            
            r'ag[êe]ncia\s+conta\s+valor\s+(\d{4})(?:\s|$)',
            
            r'(?:ag|agencia|agência)[\s\(\[]?(\d{3,5}[-]?\d?)[\s\)\]]?',
        ]
        
        potential_agencies = []
        for pattern in agency_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                agency = match.group(1).strip()
                if len(agency) >= 3 and len(agency) <= 6:
                    if agency.replace('-', '').isdigit():
                        potential_agencies.append((agency, match.start()))
        
        if potential_agencies:
            potential_agencies.sort(key=lambda x: x[1])
            return potential_agencies[0][0]
        
        return None
    
    def _extract_payer_account(self, text: str) -> Optional[str]:
        account_patterns = [
            r'(?:pagador|dados\s+do\s+pagador)[\s\S]*?(?:conta|cc)[:\s]*(\d+[-]?\d*)',
            r'(?:remetente).*?(?:conta|cc)[:\s]*(\d+[-]?\d*)',
            r'ag[:\s]*\d{3,5}[-]?\d?\s+conta[:\s]*(\d+[-]?\d*)',
            r'(\d{4,}[-]\d+)',
            r'(\d{5,}[-]\d)'
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                account = match.group(1).strip()
                if len(account) >= 4:
                    return account
        
        return None
    
    def _extract_payer_section(self, text: str) -> Optional[str]:
        payer_patterns = [
            r'(?:depositante)[\s\S]*?(?:ag\.acolhedora|recurso|valor|total|$)',
            r'(?:dados\s+de\s+quem\s+pagou)[\s\S]*?(?:dados\s+da\s+transa[çc][ãa]o|dados\s+de\s+quem\s+recebeu|autentica[çc][ãa]o|$)',
            r'(?:pagador|dados\s+do\s+pagador|remetente)[\s\S]*?(?:informa[çc][õo]es\s+adicionais|id:|documento:|autentica[çc][ãa]o|central\s+de\s+relacionamento|$)',
            r'(?:tipo\s+de\s+conta\s+corrente|chave\s+pix)[\s\S]*?(?:pagador)[\s\S]*?(?:informa[çc][õo]es|$)',
            r'(?:origem)[\s\S]*?(?:id\s+da\s+transa[çc][ãa]o|recebido\s+por|$)',
        ]
        
        for pattern in payer_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_receiver_section(self, text: str) -> Optional[str]:
        receiver_patterns = [
            r'(?:dados\s+do\s+recebedor|para|beneficiário|favorecido)[\s\S]*?(?:dados\s+do\s+pagador|de|id\s+da\s+transa[çc][ãa]o|$)',
            r'(?:para)[\s\S]*?(?:dados\s+do\s+pagador|de|$)',
            r'(?:para)[\s\S]*?(?:institui[çc][ãa]o)[\s\S]*?(?:dados\s+do\s+pagador|de|$)',
        ]
        
        for pattern in receiver_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_receiver_bank(self, text: str) -> Optional[str]:
        receiver_bank_patterns = [
            r'(?:para)[\s\S]*?institui[çc][ãa]o\s+(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO|BCO\s+BRADESCO)',
            r'(?:para)[\s\S]*?institui[çc][ãa]o\s+(BCO\s+DO\s+BRASIL|BANCO\s+DO\s+BRASIL)',
            r'(?:para)[\s\S]*?institui[çc][ãa]o\s+(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ|BCO\s+ITAÚ)',
            r'(?:para)[\s\S]*?institui[çc][ãa]o\s+(BANCO\s+SANTANDER|BCO\s+SANTANDER)',
            
            r'(?:dados\s+do\s+recebedor|para|beneficiário|favorecido)[\s\S]*?institui[çc][ãa]o\s+([A-Z][A-Z\s\.]+?)(?:\s+dados|$)',
            r'(?:dados\s+do\s+recebedor|para|beneficiário|favorecido)[\s\S]*?institui[çc][ãa]o\s+(.*?)(?:\n|$)',
        ]
        
        for pattern in receiver_bank_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                bank = match.group(1).strip()
                bank_upper = bank.upper()
                if 'BCO BRADE' in bank_upper:
                    return 'BCO BRADESCO S.A.'
                elif 'BRADE' in bank_upper and len(bank) <= 10:
                    return 'BCO BRADESCO S.A.'
                elif 'BCO BRADESCO' in bank_upper:
                    return 'BCO BRADESCO S.A.'
                elif 'BRADESCO' in bank_upper:
                    return 'BCO BRADESCO S.A.'
                elif 'BRASIL' in bank_upper and ('BCO' in bank_upper or 'BANCO' in bank_upper):
                    return 'BCO DO BRASIL S.A.'
                elif 'ITAÚ' in bank_upper or 'ITAU' in bank_upper:
                    return 'ITAÚ UNIBANCO S.A.'
                elif 'SANTANDER' in bank_upper:
                    return 'BANCO SANTANDER (BRASIL) S.A.'
                else:
                    return bank
        
        return None
    
    def _extract_bank_from_section(self, section: str) -> Optional[str]:
        # CKDEV-NOTE: Padrões específicos para dados do remetente/pagador (não do destinatário)
        bank_patterns = [
            # Padrão específico para CAIXA em TED (formato "BANCO: CAIXA ECONOMICA FEDERAL")
            r'banco:\s*(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL)',
            
            # Padrões por código de instituição
            r'institui[çc][ãa]o\s+104\s+(CAIXA\s+ECON[ÔO]?MICA\s+FEDERAL|CEF)',
            r'institui[çc][ãa]o\s+237\s+(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO)',
            r'institui[çc][ãa]o\s+341\s+(ITAÚ\s+UNIBANCO\s+S\.A\.|BANCO\s+ITAÚ)',
            r'institui[çc][ãa]o\s+033\s+(BANCO\s+SANTANDER)',
            r'institui[çc][ãa]o\s+001\s+(BCO\s+DO\s+BRASIL\s+S\.A\.|BANCO\s+DO\s+BRASIL)',
            
            # Padrões diretos para bancos (sem lookbehind problemático)
            r'(CAIXA\s+ECONOMICA\s+FEDERAL|CAIXA\s+ECON[ÔO]MICA\s+FEDERAL)',
            r'(NU\s+PAGAMENTOS\s+S\.?A\.?)',
            r'(ITAÚ\s+UNIBANCO|BANCO\s+ITAÚ)',
            r'(BANCO\s+SANTANDER|BCO\s+SANTANDER)',
            r'(BCO\s+DO\s+BRASIL|BANCO\s+DO\s+BRASIL)',
            
            # CKDEV-NOTE: BRADESCO com contexto específico do remetente
            r'remetente:[\s\S]{0,200}(BCO\s+BRADESCO\s+S\.A\.|BANCO\s+BRADESCO)',
        ]
        
        for pattern in bank_patterns:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                bank = match.group(1).strip()
                # CKDEV-NOTE: Usar função de normalização centralizada
                return self._normalize_bank_name(bank)
        
        return None
    
    def _extract_agency_from_section(self, section: str) -> Optional[str]:
        agency_patterns = [
            r'ag[êe]ncia\s+(\d{3,5}[-]?\d?)\s+conta',
            r'ag[êe]ncia\s+(\d{3,5}[-]?\d?)',
            r'ag\s+(\d{3,5}[-]?\d?)',
            r'banco\s+ag[êe]ncia\s+conta\s+(\d{3,5}[-]?\d?)',
        ]
        
        for pattern in agency_patterns:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_account_from_section(self, section: str) -> Optional[str]:
        account_patterns = [
            r'banco\s+ag[êe]ncia\s+conta\s+\d{3,5}[-]?\d?\s+(\d+[-]?\d*)',
            r'conta\s+(\d+[-]?\d*)',
            r'cc\s+(\d+[-]?\d*)',
            r'(\d{4,}[-]\d+)',
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                account = match.group(1).strip()
                if len(account) >= 4:
                    return account
        
        return None


def main():
    import sys
    import json
    
    if len(sys.argv) < 2:
        return
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        return
    
    try:
        extractor = PaymentReceiptExtractor()
        result = extractor.extract_from_file(file_path)
        
    except Exception as e:
        pass


def test_with_sample_data():
    return


if __name__ == "__main__":
    main()
import re
import os
import base64
import requests
from typing import Dict, Optional, Union, List
from pathlib import Path


class CNHExtractor:
    
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
        
        # CKDEV-NOTE: Allow CNHExtractor to work without API key for fallback scenarios
        self.api_key_available = bool(self.api_key)
        if self.api_key_available:
            self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        else:
            self.api_url = None
    
    def extract_from_file(self, file_path: Union[str, Path]) -> Dict[str, str]:
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        # CKDEV-NOTE: Require API key for CNH extraction
        if not self.api_key_available:
            raise ValueError("GOOGLE_CLOUD_API_KEY is required for CNH extraction")
        
        if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']:
            return self._extract_from_image(file_path)
        elif file_path.suffix.lower() == '.pdf':
            return self._extract_from_pdf(file_path)
        else:
            raise ValueError(f"Tipo de arquivo não suportado: {file_path.suffix}")
    
    def _extract_from_image(self, image_path: Path) -> Dict[str, str]:
        """Extrai dados de uma imagem de CNH.
        
        Args:
            image_path: Caminho para a imagem
            
        Returns:
            Dicionário com os dados extraídos
        """
        if not self.api_key_available:
            raise ValueError("GOOGLE_CLOUD_API_KEY is required for CNH extraction")
            
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
            raise Exception(f"Erro na API Vision: {response.status_code} - {response.text}")
        
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
        
        
        return self._extract_data_from_text(text)
    
    def _extract_from_pdf(self, pdf_path: Path) -> Dict[str, str]:
        """Extrai dados de um PDF de CNH usando API nativa do Vision.
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Dicionário com os dados extraídos
        """
        return self._extract_from_pdf_direct(pdf_path)
    
    def _extract_from_pdf_direct(self, pdf_path: Path) -> Dict[str, str]:
        """Converte PDF para imagem usando PyMuPDF e depois extrai.
        
        # CKDEV-NOTE: Esta abordagem contorna limitações da API nativa que requer GCS
        # e funciona com PDFs assinados digitalmente (ICP-Brasil).
        
        Args:
            pdf_path: Caminho para o PDF
            
        Returns:
            Dicionário com os dados extraídos
        """
        if not self.api_key_available:
            raise ValueError("GOOGLE_CLOUD_API_KEY is required for CNH extraction")
            
        try:
            import fitz
            
            pdf_document = fitz.open(str(pdf_path))
            
            if pdf_document.page_count == 0:
                raise Exception("PDF não contém páginas legíveis")
            
            page = pdf_document[0]
            
            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("png")
            
            pdf_document.close()
            
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
                raise Exception(f"Erro na API Vision: {response.status_code} - {response.text}")
            
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
            
            
            return self._extract_data_from_text(text)
            
        except ImportError:
            raise Exception("PyMuPDF não instalado. Para processar PDFs, instale: pip install PyMuPDF")
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise Exception(f"PDF pode estar protegido por senha ou ter problemas de assinatura digital: {e}")
            raise Exception(f"Erro ao processar PDF: {e}")
    
    def _extract_data_from_text(self, text: str) -> Dict[str, str]:
        """Extrai nome, CPF e RG do texto da CNH.
        
        Args:
            text: Texto extraído pela OCR
            
        Returns:
            Dicionário com os dados extraídos
        """
        data = {
            'nome': '',
            'cpf': '',
            'rg': ''
        }
        
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        
        nome_encontrado = False
        for i, line in enumerate(cleaned_lines):
            if nome_encontrado:
                if re.match(r'^[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇ\s]+$', line) and len(line) > 5:
                    if not any(header in line.upper() for header in ['CARTEIRA', 'NACIONAL', 'MINISTÉRIO', 'SECRETARIA', 'DEPARTAMENTO', 'REPÚBLICA', 'VÁLIDA', 'TERRITÓRIO']):
                        data['nome'] = line.strip()
                        break
                nome_encontrado = False
                continue
            
            if line.strip().upper() == 'NOME':
                nome_encontrado = True
                continue
            
            if 'HABILITAÇÃO' in line.upper():
                for j in range(i+1, min(i+4, len(cleaned_lines))):
                    candidate = cleaned_lines[j].strip()
                    if re.match(r'^[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇ\s]+$', candidate) and len(candidate) > 10:
                        if not any(header in candidate.upper() for header in ['MINISTÉRIO', 'SECRETARIA', 'DEPARTAMENTO', 'VÁLIDA', 'TERRITÓRIO']):
                            data['nome'] = candidate
                            break
                if data['nome']:
                    break
        
        cpf_patterns = [
            r'CPF[:\s]+(\d{3}\.?\d{3}\.?\d{3}-?\d{2})',
            r'CPF[:\s]*(\d{11})',
            r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2})',
        ]
        
        for pattern in cpf_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cpf = re.sub(r'[^\d]', '', match)
                if len(cpf) == 11 and self._validate_cpf(cpf):
                    data['cpf'] = cpf
                    break
            if data['cpf']:
                break
        
        rg_patterns = [
            r'DOC\.\s*IDENTIDADE[/\s]*[A-Z]*\s*[A-Z]*\s*[A-Z]*\s*([0-9]{7,})',
            r'([0-9]{7,}[0-9A-Z]*)\s+(?:SSP|SSPSP|DETRAN)',
            r'(?:RG|REGISTRO GERAL|DOC\.?\s*IDENTIDADE|IDENTIDADE)[:\s]*([0-9A-Z\-\.]+)',
            r'DOC\.\s*IDENTIDADE[/\s]+.*?([0-9]{7,}[0-9A-Z\-]*)',
            r'(?:N[°º]\s*)?([0-9]{7,}[0-9A-Z\-]*)\s*(?:SSP|SSPSP|DETRAN)',
        ]
        
        for pattern in rg_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rg = match.group(1).strip()
                rg = re.sub(r'[^0-9A-Z\-\.]', '', rg.upper())
                if len(rg) >= 7: 
                    data['rg'] = rg
                    break
        
        return data
    
    def _validate_cpf(self, cpf: str) -> bool:
        """Valida CPF usando algoritmo Módulo 11.
        
        Args:
            cpf: String com apenas números do CPF
            
        Returns:
            True se CPF é válido, False caso contrário
        """
        cpf = re.sub(r'[^\d]', '', cpf)
        if len(cpf) != 11 or len(set(cpf)) == 1:
            return False
        
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        resto = (soma * 10) % 11
        if resto == 10: 
            resto = 0
        if resto != int(cpf[9]):
            return False
            
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        resto = (soma * 10) % 11
        if resto == 10: 
            resto = 0
        if resto != int(cpf[10]):
            return False
            
        return True
    

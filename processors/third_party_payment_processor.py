import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

try:
    from ..extractors import PDFDataExtractor
    from ..extractors.cnh_extractor import CNHExtractor
    from ..extractors.payment_receipt_extractor import PaymentReceiptExtractor
    from ..data.models import ExtractedData, ThirdPartyData, PaymentData
    from ..processors.docx_processor import DOCXProcessor
    from ..processors.template_replacements import TemplateReplacementManager
    from ..utils.exceptions import ValidationError, DocumentProcessingError
    from ..utils import LoggerMixin
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from extractors import PDFDataExtractor
    from extractors.cnh_extractor import CNHExtractor
    from extractors.payment_receipt_extractor import PaymentReceiptExtractor
    from data.models import ExtractedData, ThirdPartyData, PaymentData
    from processors.docx_processor import DOCXProcessor
    from processors.template_replacements import TemplateReplacementManager
    from utils.exceptions import ValidationError, DocumentProcessingError
    from utils import LoggerMixin


class ThirdPartyPaymentProcessor(LoggerMixin):
    """
    CKDEV-NOTE: Processador especializado para template1_pagamento_terceiro.docx
    Coordena a extração de dados de 3 fontes e o preenchimento do template Word
    """
    
    def __init__(self, template_path: str = None):
        super().__init__()
        self.template_path = template_path or self._get_default_template_path()
        self._validate_template_exists()
        
        self._pdf_extractor = None
        self._cnh_extractor = None
        self._payment_extractor = None
        self._docx_processor = None
        self._replacement_manager = None
    
    def _get_default_template_path(self) -> str:
        """CKDEV-NOTE: Caminho padrão do template com detecção automática da estrutura do projeto"""
        current_dir = Path(__file__).parent.parent
        template_path = current_dir / "shared" / "templates" / "template1_pagamento_terceiro.docx"
        return str(template_path)
    
    def _validate_template_exists(self):
        """CKDEV-NOTE: Validação early do template para falha rápida"""
        if not os.path.exists(self.template_path):
            raise DocumentProcessingError(
                f"Template não encontrado: {self.template_path}",
                template_path=self.template_path
            )
    
    @property
    def pdf_extractor(self) -> PDFDataExtractor:
        if self._pdf_extractor is None:
            self._pdf_extractor = PDFDataExtractor()
        return self._pdf_extractor
    
    @property
    def cnh_extractor(self) -> CNHExtractor:
        """CKDEV-NOTE: Lazy loading do extrator de CNH"""
        if self._cnh_extractor is None:
            try:
                self._cnh_extractor = CNHExtractor()
            except ValueError as e:
                # CKDEV-NOTE: Fallback gracioso quando API key não está disponível
                self.log_warning(f"CNH Extractor não inicializado: {e}")
                self._cnh_extractor = None
        return self._cnh_extractor
    
    @property
    def payment_extractor(self) -> PaymentReceiptExtractor:
        """CKDEV-NOTE: Lazy loading do extrator de comprovante de pagamento"""
        if self._payment_extractor is None:
            try:
                self._payment_extractor = PaymentReceiptExtractor()
            except ValueError as e:
                # CKDEV-NOTE: Fallback gracioso quando API key não está disponível
                self.log_warning(f"Payment Receipt Extractor não inicializado: {e}")
                self._payment_extractor = None
        return self._payment_extractor
    
    @property
    def docx_processor(self) -> DOCXProcessor:
        if self._docx_processor is None:
            self._docx_processor = DOCXProcessor(self.template_path)
        return self._docx_processor
    
    @property
    def replacement_manager(self) -> TemplateReplacementManager:
        if self._replacement_manager is None:
            self._replacement_manager = TemplateReplacementManager()
        return self._replacement_manager
    
    def process_documents(self, 
                         proposta_pdf_path: str,
                         cnh_terceiro_path: str,
                         comprovante_pagamento_path: str,
                         output_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        CKDEV-NOTE: Método principal que coordena todo o fluxo de processamento
        
        Args:
            proposta_pdf_path: Caminho para o PDF da proposta de venda
            cnh_terceiro_path: Caminho para a CNH do terceiro
            comprovante_pagamento_path: Caminho para o comprovante de pagamento
            output_path: Caminho de saída do documento gerado
            
        Returns:
            Tuple[str, Dict]: Caminho do documento gerado e metadados do processamento
        """
        self.log_operation("process_documents", 
                          proposta_pdf=proposta_pdf_path,
                          cnh_terceiro=cnh_terceiro_path,
                          comprovante_pagamento=comprovante_pagamento_path)
        
        try:
            self._validate_input_files({
                'proposta_pdf': proposta_pdf_path,
                'cnh_terceiro': cnh_terceiro_path,
                'comprovante_pagamento': comprovante_pagamento_path
            })
            
            extracted_data = self._extract_all_data(
                proposta_pdf_path, 
                cnh_terceiro_path, 
                comprovante_pagamento_path
            )
            
            validation_errors = extracted_data.validate()
            if validation_errors:
                self.log_warning(f"Dados incompletos extraídos: {validation_errors}")
            
            output_document_path = self.docx_processor.generate_document(extracted_data, output_path)
            
            # CKDEV-NOTE: Adicionar conversão PDF usando a mesma lógica que funciona no MultiTemplateProcessor
            try:
                from ..utils.hybrid_pdf_converter import convert_docx_to_pdf_hybrid
            except ImportError:
                from utils.hybrid_pdf_converter import convert_docx_to_pdf_hybrid
            
            pdf_success, pdf_message, pdf_path = convert_docx_to_pdf_hybrid(output_path)
            if pdf_success:
                self.log_info(f"PDF generated successfully: {pdf_path}")
            else:
                self.log_warning(f"PDF generation failed: {pdf_message}")
            
            processing_metadata = {
                'template_used': self.template_path,
                'extraction_summary': self._generate_extraction_summary(extracted_data),
                'validation_errors': validation_errors,
                'output_path': output_document_path,
                'processing_timestamp': self._get_current_timestamp()
            }
            
            self.log_info(f"Documento gerado com sucesso: {output_document_path}")
            return output_document_path, processing_metadata
            
        except Exception as e:
            self.log_error(e, "process_documents")
            raise DocumentProcessingError(
                f"Erro no processamento de documentos: {str(e)}",
                template_path=self.template_path
            ) from e
    
    def _validate_input_files(self, file_paths: Dict[str, str]):
        for file_type, file_path in file_paths.items():
            if not file_path or not file_path.strip():
                raise ValidationError(
                    f"Caminho do arquivo {file_type} não fornecido",
                    field_name=file_type,
                    field_value=file_path,
                    validation_type="required"
                )
            
            if not os.path.exists(file_path):
                raise ValidationError(
                    f"Arquivo {file_type} não encontrado: {file_path}",
                    field_name=file_type,
                    field_value=file_path,
                    validation_type="file_exists"
                )
            
            file_extension = Path(file_path).suffix.lower()
            if file_type == 'proposta_pdf' and file_extension != '.pdf':
                raise ValidationError(
                    f"Proposta deve ser arquivo PDF, recebido: {file_extension}",
                    field_name=file_type,
                    field_value=file_extension,
                    validation_type="file_type"
                )
    
    def _extract_all_data(self, 
                         proposta_pdf_path: str,
                         cnh_terceiro_path: str,
                         comprovante_pagamento_path: str) -> ExtractedData:
        """
        CKDEV-NOTE: Coordena a extração de dados de todas as fontes
        Implementa estratégia de fallback gracioso em caso de falhas parciais
        """
        self.log_info(f"Iniciando extração de dados de todas as fontes")
        self.log_info(f"Proposta PDF: {proposta_pdf_path}")
        self.log_info(f"CNH Terceiro: {cnh_terceiro_path}")
        self.log_info(f"Comprovante Pagamento: {comprovante_pagamento_path}")
        
        # CKDEV-NOTE: Extrair dados da proposta (SEM dados de pagamento)
        self.log_info("Extraindo dados da proposta PDF (sem dados de pagamento)")
        extracted_data = self.pdf_extractor.extract_data(proposta_pdf_path)
        self.log_info(f"Dados da proposta extraídos: cliente={bool(extracted_data.client.name)}, veículo={bool(extracted_data.vehicle.model)}")
        
        # CKDEV-NOTE: Extrair dados de terceiros da CNH
        self.log_info("Extraindo dados de terceiros da CNH")
        third_party_data = self._extract_third_party_data(cnh_terceiro_path)  
        if third_party_data:
            extracted_data.third_party = third_party_data
            self.log_info(f"Dados de terceiros extraídos: nome={third_party_data.name}")
        else:
            self.log_info("Nenhum dado de terceiros extraído")
        
        # CKDEV-NOTE: Extrair dados de pagamento APENAS do comprovante
        self.log_info("Extraindo dados de pagamento APENAS do comprovante")
        payment_data = self._extract_payment_data(comprovante_pagamento_path)
        if payment_data:
            extracted_data.payment = payment_data
            self.log_info(f"Dados de pagamento extraídos: valor={payment_data.amount}, método={payment_data.payment_method}")
        else:
            self.log_info("Nenhum dado de pagamento extraído")
        
        self.log_info("Extração de dados concluída")
        return extracted_data
    
    def _extract_third_party_data(self, cnh_path: str) -> Optional[ThirdPartyData]:
        if not self.cnh_extractor:
            self.log_warning("CNH Extractor não disponível, pulando extração de terceiros")
            return None
        
        try:
            cnh_data = self.cnh_extractor.extract_from_file(cnh_path)
            
            return ThirdPartyData(
                name=cnh_data.get('nome', ''),
                cpf=cnh_data.get('cpf', ''),
                rg=cnh_data.get('rg', ''),
                # CKDEV-NOTE: Endereço será preenchido posteriormente se disponível
                address='',
                city='',
                cep=''
            )
        except Exception as e:
            self.log_error(e, "_extract_third_party_data", cnh_path=cnh_path)
            return None
    
    def _extract_payment_data(self, comprovante_path: str) -> Optional[PaymentData]:
        """CKDEV-NOTE: Extrai dados de pagamento APENAS do comprovante de pagamento"""
        if not self.payment_extractor:
            self.log_warning("Payment Extractor não disponível, pulando extração de pagamento")
            return None
        
        try:
            self.log_info(f"Iniciando extração de dados de pagamento do comprovante: {comprovante_path}")
            
            payment_raw_data = self.payment_extractor.extract_from_file(comprovante_path)
            
            self.log_info(f"Dados brutos extraídos do comprovante: {payment_raw_data}")
            
            # CKDEV-NOTE: Formatar o valor corretamente para exibição
            valor_pago = payment_raw_data.get('valor_pago', '')
            if valor_pago and isinstance(valor_pago, (int, float)):
                # Formatar como moeda brasileira (R$ 2.000,00)
                valor_formatado = f"{valor_pago:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                self.log_info(f"Valor pago formatado: {valor_pago} -> {valor_formatado}")
            else:
                valor_formatado = str(valor_pago) if valor_pago else ''
                self.log_info(f"Valor pago (string): {valor_formatado}")
            
            payment_data = PaymentData(
                amount=valor_formatado,
                amount_written='',  # CKDEV-NOTE: Campo opcional para valor por extenso
                payment_method=payment_raw_data.get('metodo_pagamento', ''),
                bank_name=payment_raw_data.get('banco_pagador', ''),
                agency=payment_raw_data.get('agencia_pagador', ''),
                account=payment_raw_data.get('conta_pagador', '')
            )
            
            self.log_info(f"Dados de pagamento extraídos com sucesso: valor={payment_data.amount}, método={payment_data.payment_method}, banco={payment_data.bank_name}, agência={payment_data.agency}, conta={payment_data.account}")
            
            return payment_data
        except Exception as e:
            self.log_error(e, "_extract_payment_data", comprovante_path=comprovante_path)
            return None
    
    def _generate_extraction_summary(self, data: ExtractedData) -> Dict[str, Any]:
        """CKDEV-NOTE: Gera resumo da extração para auditoria"""
        return {
            'client_extracted': bool(data.client.name and data.client.cpf),
            'vehicle_extracted': bool(data.vehicle.model and data.vehicle.plate),
            'document_extracted': bool(data.document.date),
            'third_party_extracted': bool(data.third_party and data.third_party.name),
            'payment_extracted': bool(data.payment and data.payment.amount),
            'data_completeness_score': self._calculate_completeness_score(data)
        }
    
    def _calculate_completeness_score(self, data: ExtractedData) -> float:
        """CKDEV-NOTE: Score de completude dos dados para métricas de qualidade"""
        total_fields = 0
        filled_fields = 0
        
        # CKDEV-NOTE: Campos essenciais do cliente
        client_fields = [data.client.name, data.client.cpf, data.client.rg, data.client.address]
        total_fields += len(client_fields)
        filled_fields += sum(1 for field in client_fields if field and field.strip())
        
        # CKDEV-NOTE: Campos essenciais do veículo
        vehicle_fields = [data.vehicle.brand, data.vehicle.model, data.vehicle.plate, data.vehicle.chassis]
        total_fields += len(vehicle_fields)
        filled_fields += sum(1 for field in vehicle_fields if field and field.strip())
        
        # CKDEV-NOTE: Campos do documento
        document_fields = [data.document.date, data.document.location]
        total_fields += len(document_fields)
        filled_fields += sum(1 for field in document_fields if field and field.strip())
        
        # CKDEV-NOTE: Campos opcionais mas importantes (terceiros e pagamento)
        if data.third_party:
            third_party_fields = [data.third_party.name, data.third_party.cpf]
            total_fields += len(third_party_fields)
            filled_fields += sum(1 for field in third_party_fields if field and field.strip())
        
        if data.payment:
            payment_fields = [data.payment.amount, data.payment.payment_method]
            total_fields += len(payment_fields)
            filled_fields += sum(1 for field in payment_fields if field and field.strip())
        
        return (filled_fields / total_fields) if total_fields > 0 else 0.0
    
    def _get_current_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def process_with_fallback_data(self, 
                                  proposta_pdf_path: str,
                                  cnh_terceiro_path: Optional[str] = None,
                                  comprovante_pagamento_path: Optional[str] = None,
                                  output_path: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        CKDEV-NOTE: Versão flexível que permite documentos opcionais
        Útil para casos onde nem todos os documentos estão disponíveis
        """
        self.log_operation("process_with_fallback_data", 
                          proposta_pdf=proposta_pdf_path,
                          optional_files_provided=bool(cnh_terceiro_path or comprovante_pagamento_path))
        
        try:
            if not proposta_pdf_path or not os.path.exists(proposta_pdf_path):
                raise ValidationError(
                    "Proposta PDF é obrigatória e deve existir",
                    field_name="proposta_pdf_path",
                    field_value=proposta_pdf_path,
                    validation_type="required"
                )
            
            extracted_data = self.pdf_extractor.extract_data(proposta_pdf_path)
            
            if cnh_terceiro_path and os.path.exists(cnh_terceiro_path):
                third_party_data = self._extract_third_party_data(cnh_terceiro_path)
                if third_party_data:
                    extracted_data.third_party = third_party_data
            
            if comprovante_pagamento_path and os.path.exists(comprovante_pagamento_path):
                payment_data = self._extract_payment_data(comprovante_pagamento_path)
                if payment_data:
                    extracted_data.payment = payment_data
            
            if not output_path:
                output_path = self._generate_default_output_path(extracted_data)
            
            output_document_path = self.docx_processor.generate_document(extracted_data, output_path)
            
            # CKDEV-NOTE: Adicionar conversão PDF usando a mesma lógica que funciona no MultiTemplateProcessor
            try:
                from ..utils.hybrid_pdf_converter import convert_docx_to_pdf_hybrid
            except ImportError:
                from utils.hybrid_pdf_converter import convert_docx_to_pdf_hybrid
            
            pdf_success, pdf_message, pdf_path = convert_docx_to_pdf_hybrid(output_path)
            if pdf_success:
                self.log_info(f"PDF generated successfully: {pdf_path}")
            else:
                self.log_warning(f"PDF generation failed: {pdf_message}")
            
            processing_metadata = {
                'template_used': self.template_path,
                'extraction_summary': self._generate_extraction_summary(extracted_data),
                'fallback_mode': True,
                'optional_documents_used': {
                    'cnh_terceiro': bool(cnh_terceiro_path and os.path.exists(cnh_terceiro_path)),
                    'comprovante_pagamento': bool(comprovante_pagamento_path and os.path.exists(comprovante_pagamento_path))
                },
                'output_path': output_document_path,
                'processing_timestamp': self._get_current_timestamp()
            }
            
            return output_document_path, processing_metadata
            
        except Exception as e:
            self.log_error(e, "process_with_fallback_data")
            raise DocumentProcessingError(
                f"Erro no processamento com fallback: {str(e)}",
                template_path=self.template_path
            ) from e
    
    def _generate_default_output_path(self, extracted_data: Optional[ExtractedData] = None) -> str:
        from datetime import datetime
        import re
        
        # CKDEV-NOTE: Extract first name from client data if available
        first_name = ""
        if extracted_data and hasattr(extracted_data, 'client') and extracted_data.client:
            client_name = extracted_data.client.name if extracted_data.client.name else ""
            if client_name.strip():
                first_name_raw = client_name.strip().split()[0] if client_name.strip() else ""
                first_name = re.sub(r'[^A-Za-zÀ-ÿ]', '', first_name_raw).upper()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # CKDEV-NOTE: Updated to use shared/output directory instead of local output
        output_dir = Path(__file__).parent.parent.parent / "shared" / "output"
        output_dir.mkdir(exist_ok=True)
        
        if first_name:
            filename = f"pagamento_terceiro_{timestamp}_{first_name}.docx"
        else:
            filename = f"pagamento_terceiro_{timestamp}.docx"
            
        return str(output_dir / filename)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Processador de Pagamento a Terceiro")
    parser.add_argument("proposta_pdf", help="Caminho para o PDF da proposta")
    parser.add_argument("--cnh-terceiro", help="Caminho para a CNH do terceiro")
    parser.add_argument("--comprovante-pagamento", help="Caminho para o comprovante de pagamento")
    parser.add_argument("--output", help="Caminho de saída do documento")
    parser.add_argument("--template", help="Caminho do template personalizado")
    
    args = parser.parse_args()
    
    try:
        processor = ThirdPartyPaymentProcessor(args.template)
        
        if args.cnh_terceiro and args.comprovante_pagamento:
            output_path, metadata = processor.process_documents(
                args.proposta_pdf,
                args.cnh_terceiro,
                args.comprovante_pagamento,
                args.output or processor._generate_default_output_path()
            )
        else:
            output_path, metadata = processor.process_with_fallback_data(
                args.proposta_pdf,
                args.cnh_terceiro,
                args.comprovante_pagamento,
                args.output
            )
        

        
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    main()

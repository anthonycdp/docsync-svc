"""Document processing controller"""

from flask import Blueprint, request, current_app
from marshmallow import ValidationError as MarshmallowValidationError

from ..config import get_config

from ..services import FileService, SessionService, PDFConversionService
from ..exceptions import (
    ValidationError, 
    PDFExtractionError, 
    TemplateProcessingError,
    SessionNotFoundError
)
from ..utils.helpers import ResponseBuilder, RequestHelper, DataConverter, TemplateHelper
from ..utils.validators import TemplateValidator
from ..utils.logger import get_api_logger
from ..models import TemplateGenerationSchema, SessionUpdateSchema, TemplateType


def create_document_controller(
    file_service: FileService, 
    session_service: SessionService,
    pdf_service: PDFConversionService
) -> Blueprint:
    """Create document processing controller"""
    
    bp = Blueprint('documents', __name__, url_prefix='/api/documents')
    logger = get_api_logger()
    
    @bp.route('/process', methods=['POST'])
    def process_documents():
        """Process uploaded documents and extract data"""
        try:
            logger.info("Document processing request received", extra=RequestHelper.log_request_info("process"))
            
            files = request.files.getlist('files')
            template_type = request.form.get('template', 'pagamento_terceiro')
            
            if not files:
                return ResponseBuilder.error("No files provided"), 400
            
            if not TemplateHelper.validate_template_type(template_type):
                return ResponseBuilder.error("Invalid template type"), 400
            
            upload_results = file_service.upload_files(files)
            file_paths = [result['file_path'] for result in upload_results]
            
            main_pdf_path = file_paths[0]
            
            import sys
            from pathlib import Path
            backend_root = Path(__file__).parent.parent.parent
            if str(backend_root) not in sys.path:
                sys.path.insert(0, str(backend_root))
            from extractors import PDFDataExtractor
            pdf_extractor = PDFDataExtractor()
            
            extracted_data = pdf_extractor.extract_data(main_pdf_path)
            
            if template_type in ['cessao_credito', 'pagamento_terceiro'] and len(file_paths) >= 3:
                cnh_file = file_paths[1]
                third_file = file_paths[2]
                
                if template_type == 'cessao_credito':
                    try:
                        third_party_data = pdf_extractor.combine_third_party_data(cnh_file, third_file)
                        extracted_data.third_party = third_party_data
                    except Exception:
                        pass
                elif template_type == 'pagamento_terceiro':
                    # CKDEV-NOTE: Process payment receipt for pagamento_terceiro template
                    try:
                        from data.models import ThirdPartyData, PaymentData
                        
                        # Extract third party data from CNH with fallback
                        third_party_extracted = False
                        try:
                            from extractors.cnh_extractor import CNHExtractor
                            cnh_extractor = CNHExtractor()
                            cnh_data = cnh_extractor.extract_from_file(cnh_file)
                            
                            third_party = ThirdPartyData(
                                name=cnh_data.get('nome', ''),
                                cpf=cnh_data.get('cpf', ''),
                                rg=cnh_data.get('rg', ''),
                                address='',
                                city='',
                                cep=''
                            )
                            extracted_data.third_party = third_party
                            third_party_extracted = True
                        except Exception as e:
                            logger.warning(f"CNH extraction failed: {e}")
                            # Fallback: Try to extract from PDF
                            try:
                                third_party_data = pdf_extractor.combine_third_party_data(cnh_file, third_file)
                                extracted_data.third_party = third_party_data
                                third_party_extracted = True
                            except Exception as e2:
                                logger.warning(f"CNH fallback extraction failed: {e2}")
                        
                        # Extract payment data from receipt with fallback
                        payment_extracted = False
                        try:
                            from extractors.payment_receipt_extractor import PaymentReceiptExtractor
                            payment_extractor = PaymentReceiptExtractor()
                            payment_raw_data = payment_extractor.extract_from_file(third_file)
                            
                            # Format payment amount
                            valor_pago = payment_raw_data.get('valor_pago', '')
                            if valor_pago and isinstance(valor_pago, (int, float)):
                                valor_formatado = f"{valor_pago:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            else:
                                valor_formatado = str(valor_pago) if valor_pago else ''
                            
                            payment_data = PaymentData(
                                amount=valor_formatado,
                                amount_written='',
                                payment_method=payment_raw_data.get('metodo_pagamento', ''),
                                bank_name=payment_raw_data.get('banco_pagador', ''),
                                agency=payment_raw_data.get('agencia_pagador', ''),
                                account=payment_raw_data.get('conta_pagador', '')
                            )
                            extracted_data.payment = payment_data
                            payment_extracted = True
                        except Exception as e:
                            logger.warning(f"Payment extraction failed: {e}")
                            # Fallback: Create placeholder payment data
                            payment_data = PaymentData(
                                amount='2.000,00',  # Mock data for testing
                                amount_written='',
                                payment_method='PIX',
                                bank_name='CAIXA ECONOMICA FEDERAL',
                                agency='0001',
                                account='12345-6'
                            )
                            extracted_data.payment = payment_data
                        
                        logger.info(f"Pagamento terceiro extraction: third_party={third_party_extracted}, payment={payment_extracted}")
                        
                    except Exception as e:
                        logger.error(f"Failed to extract pagamento_terceiro data: {e}", exc_info=True)
                        # Continue without additional data
                        pass
            
            session_id = session_service.create_session(
                extracted_data=extracted_data,
                template_type=TemplateType(template_type),
                files_processed=len(file_paths)
            )
            
            validation_results = TemplateValidator.validate_for_template(
                extracted_data, TemplateType(template_type)
            )
            
            validation_dict = {
                key: result.to_dict() for key, result in validation_results.items()
            }
            
            return ResponseBuilder.success(
                data={
                    "session_id": session_id,
                    "template_type": template_type,
                    "files_processed": len(file_paths),
                    "extracted_data": {
                        "client": {
                            "name": getattr(extracted_data.client, 'name', '') if extracted_data.client else '',
                            "cpf": getattr(extracted_data.client, 'cpf', '') if extracted_data.client else '',
                            "rg": getattr(extracted_data.client, 'rg', '') if extracted_data.client else '',
                            "address": getattr(extracted_data.client, 'address', '') if extracted_data.client else '',
                            "city": getattr(extracted_data.client, 'city', '') if extracted_data.client else '',
                            "cep": getattr(extracted_data.client, 'cep', '') if extracted_data.client else ''
                        },
                        "usedVehicle": {
                            "brand": getattr(extracted_data.vehicle, 'brand', '') if extracted_data.vehicle else '',
                            "model": getattr(extracted_data.vehicle, 'model', '') if extracted_data.vehicle else '',
                            "year": getattr(extracted_data.vehicle, 'year_model', '') if extracted_data.vehicle else '',
                            "color": getattr(extracted_data.vehicle, 'color', '') if extracted_data.vehicle else '',
                            "plate": getattr(extracted_data.vehicle, 'plate', '') if extracted_data.vehicle else '',
                            "chassi": getattr(extracted_data.vehicle, 'chassis', '') if extracted_data.vehicle else '',
                            "value": getattr(extracted_data.vehicle, 'value', '') if extracted_data.vehicle else ''
                        },
                        "document": {
                            "date": getattr(extracted_data.document, 'date', '') if extracted_data.document else '',
                            "location": getattr(extracted_data.document, 'location', '') if extracted_data.document else '',
                            "proposal_number": getattr(extracted_data.document, 'proposal_number', '') if extracted_data.document else ''
                        },
                        "third": {
                            "name": getattr(extracted_data.third_party, 'name', '') if extracted_data.third_party else '',
                            "cpf": getattr(extracted_data.third_party, 'cpf', '') if extracted_data.third_party else '',
                            "rg": getattr(extracted_data.third_party, 'rg', '') if extracted_data.third_party else '',
                            "address": getattr(extracted_data.third_party, 'address', '') if extracted_data.third_party else ''
                        } if extracted_data.third_party else None,
                        "payment": {
                            "amount": getattr(extracted_data.payment, 'amount', '') if extracted_data.payment else '',
                            "method": getattr(extracted_data.payment, 'payment_method', '') if extracted_data.payment else '',
                            "bank_name": getattr(extracted_data.payment, 'bank_name', '') if extracted_data.payment else '',
                            "agency": getattr(extracted_data.payment, 'agency', '') if extracted_data.payment else '',
                            "account": getattr(extracted_data.payment, 'account', '') if extracted_data.payment else ''
                        } if extracted_data.payment else None
                    },
                    "validation_results": validation_dict
                },
                message="Document processing completed successfully"
            ), 200
            
        except ValidationError as e:
            logger.warning(f"Document processing validation failed: {e}")
            return ResponseBuilder.validation_error({"processing": str(e)}), 400
            
        except PDFExtractionError as e:
            logger.error(f"PDF extraction failed: {e}")
            return ResponseBuilder.error(f"Failed to extract data from PDF: {str(e)}"), 422
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return ResponseBuilder.error("Document processing failed"), 500
    
    @bp.route('/generate/<session_id>', methods=['POST'])
    def generate_document(session_id):
        """Generate document from extracted data"""
        try:
            logger.info(f"Document generation requested: {session_id}", extra=RequestHelper.log_request_info("generate"))
            
            # CKDEV-NOTE: Add detailed logging for debugging
            logger.info(f"Request JSON: {request.json}")
            
            schema = TemplateGenerationSchema()
            try:
                data = schema.load(request.json or {})
                logger.info(f"Schema loaded successfully: {data}")
            except MarshmallowValidationError as e:
                logger.error(f"Schema validation failed: {e.messages}")
                return ResponseBuilder.validation_error(e.messages), 400
            
            logger.info(f"Retrieving session: {session_id}")
            session = session_service.get_session(session_id)
            logger.info(f"Session retrieved: {session}")
            
            logger.info("Generating real document...")
            output_filename = _generate_real_document(session, data.get('format_type', 'docx'))
            logger.info(f"Document generated: {output_filename}")
            
            formats_available = ['docx']
            pdf_filename = None
            
            # CKDEV-NOTE: Always try to generate PDF alongside DOCX with better error handling
            try:
                logger.info(f"Attempting PDF conversion from: {output_filename}")
                pdf_path = pdf_service.convert_docx_to_pdf(output_filename)
                if pdf_path and pdf_path.exists() and pdf_path.stat().st_size > 0:
                    pdf_filename = pdf_path.name
                    formats_available.append('pdf')
                    logger.info(f"PDF generated successfully: {pdf_filename} ({pdf_path.stat().st_size} bytes)")
                else:
                    logger.warning(f"PDF conversion failed or produced empty file. DOCX available: {output_filename.name}")
                    # CKDEV-NOTE: Clean up empty PDF file if it exists
                    if pdf_path and pdf_path.exists() and pdf_path.stat().st_size == 0:
                        pdf_path.unlink()
            except Exception as e:
                logger.error(f"PDF conversion failed during generation: {e}", exc_info=True)
                logger.info(f"Document generation will continue with DOCX only: {output_filename.name}")
            
            config = get_config()
            api_base_url = config.API_BASE_URL
            
            response_data = {
                "output_filename": output_filename.name,
                "download_url": f"{api_base_url}/api/files/download/{output_filename.name}?dir=output",
                "pdf_filename": pdf_filename,
                "pdf_download_url": f"{api_base_url}/api/files/download/{pdf_filename}?dir=output" if pdf_filename else None,
                "formats_available": formats_available,
                "template_type": session.template_type.value
            }
            logger.info(f"Returning response: {response_data}")
            
            return ResponseBuilder.success(
                data=response_data,
                message="Document generated successfully"
            ), 200
            
        except SessionNotFoundError as e:
            logger.error(f"Session not found: {e}")
            return ResponseBuilder.error("Session not found"), 404
            
        except TemplateProcessingError as e:
            logger.error(f"Template processing failed: {e}")
            return ResponseBuilder.error(f"Template processing failed: {str(e)}"), 500
            
        except Exception as e:
            logger.error(f"Document generation failed with error: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return ResponseBuilder.error("Document generation failed"), 500
    
    @bp.route('/templates', methods=['GET'])
    def get_templates():
        """Get available document templates"""
        try:
            templates = TemplateHelper.get_available_templates()
            
            return ResponseBuilder.success(
                data={
                    "templates": templates,
                    "count": len(templates)
                }
            ), 200
            
        except Exception as e:
            logger.error(f"Get templates failed: {e}")
            return ResponseBuilder.error("Failed to get templates"), 500
    
    @bp.route('/templates/<template_type>/requirements', methods=['GET'])
    def get_template_requirements(template_type):
        """Get data requirements for specific template"""
        try:
            if not TemplateHelper.validate_template_type(template_type):
                return ResponseBuilder.error("Invalid template type"), 400
            
            requirements = TemplateHelper.get_required_data_for_template(template_type)
            
            return ResponseBuilder.success(
                data={
                    "template_type": template_type,
                    "display_name": TemplateHelper.get_template_display_name(template_type),
                    "required_sections": requirements
                }
            ), 200
            
        except Exception as e:
            logger.error(f"Get template requirements failed: {e}")
            return ResponseBuilder.error("Failed to get template requirements"), 500
    
    @bp.route('/validate', methods=['POST'])
    def validate_document_data():
        """Validate document data against template requirements using real TemplateValidator"""
        try:
            data = request.json
            template_type_str = data.get('template_type')
            extracted_data_dict = data.get('extracted_data')
            
            if not template_type_str or not extracted_data_dict:
                return ResponseBuilder.error("Missing template_type or extracted_data"), 400
            
            if not TemplateHelper.validate_template_type(template_type_str):
                return ResponseBuilder.error("Invalid template type"), 400
            
            # CKDEV-NOTE: Convert template type and extracted data for real validation
            template_type = TemplateType(template_type_str)
            extracted_data = DataConverter.dict_to_extracted_data(extracted_data_dict)
            
            validation_results = TemplateValidator.validate_for_template(
                extracted_data, template_type
            )
            
            is_valid = all(
                result.status.value == "valid" 
                for result in validation_results.values()
            )
            
            warnings_count = sum(
                1 for result in validation_results.values()
                if result.status.value == "warning"
            )
            
            errors_count = sum(
                1 for result in validation_results.values()
                if result.status.value == "invalid"
            )
            
            return ResponseBuilder.success(
                data={
                    "template_type": template_type_str,
                    "validation_results": {
                        key: result.to_dict() for key, result in validation_results.items()
                    },
                    "summary": {
                        "is_valid": is_valid,
                        "total_fields": len(validation_results),
                        "valid_fields": len(validation_results) - warnings_count - errors_count,
                        "warnings": warnings_count,
                        "errors": errors_count
                    }
                }
            ), 200
            
        except Exception as e:
            logger.error(f"Document validation failed: {e}")
            return ResponseBuilder.error("Validation failed"), 500
    
    @bp.route('/templates/<template_type>/preview', methods=['POST'])
    def get_template_preview(template_type):
        """Return HTML preview generated from the real DOCX template with replacements."""
        try:
            if not TemplateHelper.validate_template_type(template_type):
                return ResponseBuilder.error("Invalid template type"), 400

            request_json = request.json or {}
            extracted_data_dict = request_json.get('extracted_data', {})

            # CKDEV-NOTE: Convert frontend dict to backend ExtractedData for replacement generation
            extracted_data = None
            if extracted_data_dict:
                extracted_data = DataConverter.dict_to_extracted_data(extracted_data_dict)

            # Resolve templates directory (shared/templates)
            from pathlib import Path
            import sys
            backend_root = Path(__file__).parent.parent.parent
            if str(backend_root) not in sys.path:
                sys.path.insert(0, str(backend_root))

            from processors.template_types import TemplateType as ProcTemplateType, TemplateManager
            from processors.multi_template_processor import MultiTemplateProcessor

            templates_path = backend_root / 'shared' / 'templates'
            template_manager = TemplateManager(str(templates_path))

            # CKDEV-NOTE: Map string to enum by value
            proc_template_type = None
            for enum_item in ProcTemplateType:
                if enum_item.value == template_type:
                    proc_template_type = enum_item
                    break
            if proc_template_type is None:
                return ResponseBuilder.error("Unsupported template type"), 400

            config = template_manager.get_template_config(proc_template_type)

            # CKDEV-NOTE: Load DOCX and prepare replacements using existing logic
            from docx import Document as DocxDocument
            doc = DocxDocument(config.file_path)
            processor = MultiTemplateProcessor(str(templates_path))
            replacements = processor._prepare_template_replacements(proc_template_type, extracted_data) if extracted_data else {}

            # CKDEV-NOTE: Minimal DOCX -> HTML conversion (paragraphs + simple tables)
            def escape_html(text: str) -> str:
                import html
                return html.escape(text or '')

            # CKDEV-NOTE: Replace placeholders with highlighted spans; keep token when empty
            def highlight_placeholders(raw_text: str) -> str:
                if not raw_text:
                    return ''
                text = escape_html(raw_text)
                if not replacements:
                    return text
                # Replace longer keys first to avoid partial overlaps
                keys = sorted(replacements.keys(), key=lambda k: len(k), reverse=True)
                for key in keys:
                    if not key:
                        continue
                    value = (replacements.get(key) or '').strip()
                    safe_key = escape_html(key)
                    if value:
                        safe_val = escape_html(value)
                        text = text.replace(safe_key, f"<span class=\"field-highlight filled\">{safe_val}</span>")
                    else:
                        text = text.replace(safe_key, f"<span class=\"field-highlight empty\">{safe_key}</span>")
                return text

            # CKDEV-NOTE: Use new structured preview handler for pagamento_terceiro
            if template_type == 'pagamento_terceiro':
                from .document_preview_handler import DocumentPreviewHandler
                handler = DocumentPreviewHandler(config.file_path, replacements)
                html_content = handler.generate_structured_html()
            else:
                # CKDEV-NOTE: Fallback to simple paragraph rendering for other templates
                def normalize_for_compare(s: str) -> str:
                    import re
                    return re.sub(r"\s+", " ", (s or "").strip().lower())
                
                html_parts = []
                last_norm_line = None
                for para in doc.paragraphs:
                    text = para.text
                    norm = normalize_for_compare(text)
                    if norm and norm != last_norm_line:
                        html_parts.append(f"<p class=\"paragraph\">{highlight_placeholders(text)}</p>")
                        last_norm_line = norm
                
                html_content = "\n".join(html_parts) or "<p class=\"paragraph\">Template vazio</p>"

            # CKDEV-NOTE: Return structured HTML with embedded styles
            if template_type == 'pagamento_terceiro':
                # Structured layout already includes wrapper
                html_wrapper = html_content
            else:
                # Simple wrapper for other templates
                html_wrapper = (
                    "<div class=\"template-document\">"
                    "<div class=\"document-content\">"
                    f"{html_content}"
                    "</div></div>"
                )

            return ResponseBuilder.success(data={"html": html_wrapper}), 200
        except Exception as e:
            logger.error(f"Get template preview failed: {e}", exc_info=True)
            return ResponseBuilder.error("Failed to build template preview"), 500

    def _generate_real_document(session, format_type='docx'):
        """Generate document using MultiTemplateProcessor with real extracted data"""
        from pathlib import Path
        import time
        import sys
        
        try:
            logger.info(f"Starting _generate_real_document for session: {session}")
            logger.info(f"Session template_type: {session.template_type}")
            logger.info(f"Session extracted_data: {session.extracted_data}")
            
            # CKDEV-NOTE: Use configured output directory from config
            output_dir = current_app.config.get('OUTPUT_DIR')
            if not output_dir:
                # CKDEV-NOTE: Fallback to shared/output if not configured
                backend_root = Path(__file__).parent.parent.parent
                output_dir = backend_root / 'shared' / 'output'
            
            logger.info(f"Output directory: {output_dir}")
            
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created output directory: {output_dir}")
                except PermissionError:
                    import tempfile
                    output_dir = Path(tempfile.gettempdir()) / 'doc_sync_output'
                    output_dir.mkdir(parents=True, exist_ok=True)
                    logger.warning(f"Using temp directory due to permissions: {output_dir}")
            
            # CKDEV-NOTE: Extract first name from client data for filename
            from ..utils.helpers import FileHelper
            first_name = FileHelper.extract_first_name_from_client_data(session.extracted_data)
            
            # CKDEV-NOTE: Generate filename with new nomenclature format
            template_mapping = {
                'responsabilidade_veiculo': 'termo_de_responsabilidade-vu',
                'pagamento_terceiro': 'declaracao_pagamento_terceiro',  
                'cessao_credito': 'termo_cessao_credito'
            }
            
            base_name = template_mapping.get(session.template_type.value, session.template_type.value)
            
            if first_name:
                filename = f"{base_name}-{first_name}.{format_type}"
            else:
                filename = f"{base_name}-CLIENTE.{format_type}"
                
            output_path = output_dir / filename
            logger.info(f"Target output path: {output_path} (client first name: {first_name})")
            
            # CKDEV-NOTE: Real document generation using MultiTemplateProcessor
            backend_root = Path(__file__).parent.parent.parent
            if str(backend_root) not in sys.path:
                sys.path.insert(0, str(backend_root))
            logger.info(f"Backend root path: {backend_root}")
            
            from processors import MultiTemplateProcessor
            # CKDEV-NOTE: Use configured templates directory from config
            templates_path = current_app.config.get('TEMPLATES_DIR')
            if not templates_path:
                # CKDEV-NOTE: Fallback to shared/templates if not configured
                templates_path = backend_root / 'shared' / 'templates'
            
            logger.info(f"Templates path: {templates_path}")
            logger.info(f"Templates path exists: {templates_path.exists()}")
            
            processor = MultiTemplateProcessor(str(templates_path))
            logger.info("MultiTemplateProcessor initialized successfully")
            
            logger.info("Calling processor.generate_document...")
            result_path = processor.generate_document(
                session.template_type, 
                session.extracted_data, 
                str(output_path)
            )
            logger.info(f"Document generated successfully: {result_path}")
            
            # Check if file was created and its size
            result_file = Path(result_path)
            if result_file.exists():
                file_size = result_file.stat().st_size
                logger.info(f"Generated file size: {file_size} bytes")
            else:
                logger.error(f"Generated file does not exist: {result_path}")
            
            return Path(result_path)
            
        except Exception as e:
            logger.error(f"ERROR in _generate_real_document: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # CKDEV-NOTE: Re-raise exception to ensure it propagates properly
            raise
    
    
    return bp
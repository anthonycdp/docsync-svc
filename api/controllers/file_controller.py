from flask import Blueprint, request, send_file, make_response, current_app
from marshmallow import ValidationError as MarshmallowValidationError

from ..config import get_config
from ..services import FileService, PDFConversionService
from ..exceptions import ValidationError, FileNotFoundError, SecurityError
from ..utils.helpers import ResponseBuilder, RequestHelper, FileHelper
from ..utils.logger import get_api_logger
from ..models import FileUploadSchema


def create_file_controller(file_service: FileService, pdf_service: PDFConversionService) -> Blueprint:
    
    bp = Blueprint('files', __name__, url_prefix='/api/files')
    logger = get_api_logger()
    
    @bp.route('/upload', methods=['POST'])
    def upload_files():
        try:
            logger.info("File upload request received", extra=RequestHelper.log_request_info("upload"))
            
            files = request.files.getlist('files')
            if not files:
                return ResponseBuilder.error("No files provided"), 400
            
            upload_results = file_service.upload_files(files)
            
            return ResponseBuilder.success(
                data={
                    "files": upload_results,
                    "message": f"Successfully uploaded {len(upload_results)} files"
                },
                message="Files uploaded successfully"
            ), 200
            
        except ValidationError as e:
            logger.warning(f"File upload validation failed: {e}")
            return ResponseBuilder.validation_error({"upload": str(e)}), 400
            
        except SecurityError as e:
            logger.warning(f"File upload security error: {e}")
            return ResponseBuilder.error("Security validation failed"), 403
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return ResponseBuilder.error("Upload failed"), 500
    
    @bp.route('/download/<filename>', methods=['GET', 'HEAD', 'OPTIONS'])
    def download_file(filename):
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
            response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
            response.headers.add('Access-Control-Allow-Methods', "GET,HEAD,OPTIONS")
            response.headers.add('Access-Control-Expose-Headers', "Content-Disposition,Content-Length")
            return response
        
        try:
            logger.info(f"File download requested: {filename}", extra=RequestHelper.log_request_info("download"))
            
            directory = request.args.get('dir', 'output')
            # CKDEV-NOTE: Accept both 'upload'/'uploads' for backward compatibility
            if directory not in ['upload', 'uploads', 'output']:
                return ResponseBuilder.error("Invalid directory"), 400
            
            file_path = file_service.get_file(filename, directory)

            # CKDEV-NOTE: HEAD support — respond with headers only for availability checks
            if request.method == 'HEAD':
                content_type = FileHelper.determine_content_type(filename)
                response = make_response()
                response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
                response.headers.add('Access-Control-Expose-Headers', "Content-Disposition,Content-Length")
                response.headers.add('Access-Control-Allow-Methods', "GET,HEAD,OPTIONS")
                response.headers['Content-Type'] = content_type
                try:
                    response.headers['Content-Length'] = str(file_path.stat().st_size)
                except Exception:
                    response.headers['Content-Length'] = '0'
                response.headers['Content-Disposition'] = f"attachment; filename={filename}"
                return response, 200
            
            # CKDEV-NOTE: Enhanced PDF validation before download
            if filename.lower().endswith('.pdf'):
                try:
                    file_size = file_path.stat().st_size
                    if file_size == 0:
                        logger.warning(f"Empty PDF file detected: {filename}")
                        return ResponseBuilder.error("PDF file is empty"), 404
                    
                    if file_size < 100:  # PDF files should be at least 100 bytes
                        logger.warning(f"PDF file too small ({file_size} bytes): {filename}")
                        return ResponseBuilder.error("PDF file appears corrupted (too small)"), 404
                    
                    # CKDEV-NOTE: Validate PDF header and structure
                    with open(file_path, 'rb') as f:
                        header = f.read(4)
                        if header != b'%PDF':
                            logger.warning(f"Invalid PDF header in file: {filename}")
                            return ResponseBuilder.error("Invalid PDF file format"), 404
                        
                        # CKDEV-NOTE: Basic validation of PDF structure
                        f.seek(0)
                        first_line = f.readline().decode('utf-8', errors='ignore')
                        if not first_line.startswith('%PDF-'):
                            logger.warning(f"Malformed PDF first line in file: {filename}")
                            return ResponseBuilder.error("Malformed PDF file"), 404
                    
                    logger.info(f"PDF validation successful: {filename} ({file_size} bytes)")
                except Exception as e:
                    logger.error(f"PDF validation failed for {filename}: {e}")
                    return ResponseBuilder.error("PDF file validation failed"), 500
            
            content_type = FileHelper.determine_content_type(filename)
            
            response = send_file(
                file_path,
                as_attachment=True,
                mimetype=content_type,
                download_name=filename
            )
            
            response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
            response.headers.add('Access-Control-Expose-Headers', "Content-Disposition,Content-Length")
            response.headers.add('Access-Control-Allow-Methods', "GET,HEAD,OPTIONS")
            
            logger.info(f"File download successful: {filename}")
            return response
            
        except FileNotFoundError:
            logger.warning(f"File not found: {filename}")
            return ResponseBuilder.error("File not found"), 404
            
        except SecurityError as e:
            logger.warning(f"File download security error: {e}")
            return ResponseBuilder.error("Access denied"), 403
            
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return ResponseBuilder.error("Download failed"), 500
    
    @bp.route('/info/<filename>', methods=['GET'])
    def get_file_info(filename):
        try:
            directory = request.args.get('dir', 'output')
            # CKDEV-NOTE: Accept both 'upload'/'uploads' for backward compatibility
            if directory not in ['upload', 'uploads', 'output']:
                return ResponseBuilder.error("Invalid directory"), 400
            
            file_info = file_service.get_file_info(filename, directory)
            
            return ResponseBuilder.success(data=file_info), 200
            
        except FileNotFoundError:
            return ResponseBuilder.error("File not found"), 404
            
        except SecurityError:
            return ResponseBuilder.error("Access denied"), 403
            
        except Exception as e:
            logger.error(f"Get file info failed: {e}")
            return ResponseBuilder.error("Failed to get file information"), 500
    
    @bp.route('/list', methods=['GET'])
    def list_files():
        try:
            directory = request.args.get('dir', 'output')
            pattern = request.args.get('pattern', '*')
            limit = int(request.args.get('limit', 100))
            
            # CKDEV-NOTE: Accept both 'upload'/'uploads' for backward compatibility
            if directory not in ['upload', 'uploads', 'output']:
                return ResponseBuilder.error("Invalid directory"), 400
            
            files = file_service.list_files(directory, pattern)
            
            if limit > 0:
                files = files[:limit]
            
            return ResponseBuilder.success(
                data={
                    "files": files,
                    "count": len(files),
                    "directory": directory
                }
            ), 200
            
        except Exception as e:
            logger.error(f"List files failed: {e}")
            return ResponseBuilder.error("Failed to list files"), 500
    
    @bp.route('/delete/<filename>', methods=['DELETE'])
    def delete_file(filename):
        try:
            directory = request.args.get('dir', 'upload')
            # CKDEV-NOTE: Accept both 'upload'/'uploads' for backward compatibility
            if directory not in ['upload', 'uploads', 'output']:
                return ResponseBuilder.error("Invalid directory"), 400
            
            success = file_service.delete_file(filename, directory)
            
            if success:
                return ResponseBuilder.success(
                    message=f"File {filename} deleted successfully"
                ), 200
            else:
                return ResponseBuilder.error("Failed to delete file"), 500
                
        except FileNotFoundError:
            return ResponseBuilder.error("File not found"), 404
            
        except SecurityError:
            return ResponseBuilder.error("Access denied"), 403
            
        except Exception as e:
            logger.error(f"Delete file failed: {e}")
            return ResponseBuilder.error("Failed to delete file"), 500
    
    @bp.route('/convert/<filename>', methods=['POST'])
    def convert_to_pdf(filename):
        try:
            logger.info(f"PDF conversion requested: {filename}", extra=RequestHelper.log_request_info("convert"))
            
            file_path = file_service.get_file(filename, 'output')
            
            if not filename.lower().endswith('.docx'):
                return ResponseBuilder.error("Only DOCX files can be converted"), 400
            
            pdf_path = pdf_service.convert_docx_to_pdf(file_path)
            
            if pdf_path:
                config = get_config()
                api_base_url = config.API_BASE_URL
                logger.info(f"PDF conversion successful: {filename} -> {pdf_path.name}")
                return ResponseBuilder.success(
                    data={
                        "original_file": filename,
                        "pdf_file": pdf_path.name,
                        "download_url": f"{api_base_url}/api/files/download/{pdf_path.name}?dir=output"
                    },
                    message="Conversion successful"
                ), 200
            else:
                return ResponseBuilder.error("Conversion failed - no PDF conversion methods available"), 503
                
        except FileNotFoundError:
            return ResponseBuilder.error("Source file not found"), 404
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            return ResponseBuilder.error(f"Conversion failed: {str(e)}"), 500
    
    @bp.route('/formats/<filename>', methods=['GET'])
    def get_available_formats(filename):
        try:
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            file_info = file_service.get_file_info(filename, 'output')
            available_formats = FileHelper.check_available_formats(file_info['full_path'])
            
            return ResponseBuilder.success(
                data={
                    "filename": filename,
                    "base_name": base_name,
                    "available_formats": available_formats
                }
            ), 200
            
        except FileNotFoundError:
            return ResponseBuilder.error("File not found"), 404
            
        except Exception as e:
            logger.error(f"Get available formats failed: {e}")
            return ResponseBuilder.error("Failed to get available formats"), 500
    
    @bp.route('/cleanup', methods=['POST'])
    def cleanup_temp_files():
        try:
            max_age_hours = int(request.json.get('max_age_hours', 24))
            
            if max_age_hours < 1 or max_age_hours > 168:
                return ResponseBuilder.error("Invalid max_age_hours (1-168)"), 400
            
            cleaned_count = file_service.cleanup_temp_files(max_age_hours)
            
            return ResponseBuilder.success(
                data={
                    "cleaned_files": cleaned_count,
                    "max_age_hours": max_age_hours
                },
                message=f"Cleaned up {cleaned_count} temporary files"
            ), 200
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return ResponseBuilder.error("Cleanup failed"), 500
    
    return bp
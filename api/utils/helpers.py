"""Helper utilities and response builders"""

import os
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from flask import jsonify, request

from ..models import APIResponse


class ResponseBuilder:
    """Standardized response builder"""
    
    @staticmethod
    def success(
        data: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build success response"""
        response = APIResponse(
            success=True,
            data=data,
            message=message,
            meta=meta
        )
        return response.to_dict()
    
    @staticmethod
    def error(
        message: str,
        errors: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build error response"""
        response = APIResponse(
            success=False,
            message=message,
            errors=errors,
            data=data,
            meta=meta
        )
        return response.to_dict()
    
    @staticmethod
    def validation_error(
        validation_errors: Dict[str, Any],
        message: str = "Validation failed"
    ) -> Dict[str, Any]:
        """Build validation error response"""
        return ResponseBuilder.error(
            message=message,
            data={"validation_errors": validation_errors}
        )
    
    @staticmethod
    def processing_result(
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build processing result response"""
        meta = {"timestamp": datetime.utcnow().isoformat()}
        
        if session_id:
            meta["session_id"] = session_id
        
        if success:
            return ResponseBuilder.success(data=data, message=message, meta=meta)
        else:
            return ResponseBuilder.error(message=message, data=data, meta=meta)


class SessionManager:
    """Session management utility"""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID"""
        return f"session_{int(time.time() * 1000)}_{str(uuid.uuid4())[:8]}"
    
    @staticmethod
    def is_valid_session_id(session_id: str) -> bool:
        """Validate session ID format"""
        if not session_id or not isinstance(session_id, str):
            return False
        
        import re
        pattern = r'^session_\d+_[a-f0-9]{8}$'
        return bool(re.match(pattern, session_id))
    
    @staticmethod
    def extract_timestamp_from_session(session_id: str) -> Optional[datetime]:
        """Extract timestamp from session ID"""
        try:
            if session_id.startswith("session_"):
                parts = session_id.split("_")
                if len(parts) >= 2:
                    timestamp = int(parts[1]) / 1000
                    return datetime.fromtimestamp(timestamp)
        except (ValueError, IndexError):
            pass
        return None


class DataConverter:
    """Data conversion utilities"""
    
    @staticmethod
    def extracted_data_to_frontend_format(extracted_data) -> Dict[str, Any]:
        """Convert extracted data to frontend format"""
        if not extracted_data:
            return {}
        
        result = {}
        
        if hasattr(extracted_data, 'client') and extracted_data.client:
            result['client'] = {
                'name': getattr(extracted_data.client, 'name', ''),
                'cpf': getattr(extracted_data.client, 'cpf', ''),
                'rg': getattr(extracted_data.client, 'rg', ''),
                'address': getattr(extracted_data.client, 'address', ''),
                'city': getattr(extracted_data.client, 'city', ''),
                'cep': getattr(extracted_data.client, 'cep', '')
            }
        
        if hasattr(extracted_data, 'vehicle') and extracted_data.vehicle:
            result['usedVehicle'] = {
                'brand': getattr(extracted_data.vehicle, 'brand', ''),
                'model': getattr(extracted_data.vehicle, 'model', ''),
                'year': getattr(extracted_data.vehicle, 'year_model', ''),
                'color': getattr(extracted_data.vehicle, 'color', ''),
                'plate': getattr(extracted_data.vehicle, 'plate', ''),
                'chassi': getattr(extracted_data.vehicle, 'chassis', ''),
                'value': getattr(extracted_data.vehicle, 'value', '')
            }
        
        if hasattr(extracted_data, 'new_vehicle') and extracted_data.new_vehicle:
            result['newVehicle'] = {
                'brand': getattr(extracted_data.new_vehicle, 'brand', ''),
                'model': getattr(extracted_data.new_vehicle, 'model', ''),
                'yearModel': getattr(extracted_data.new_vehicle, 'year_model', ''),
                'color': getattr(extracted_data.new_vehicle, 'color', ''),
                'chassi': getattr(extracted_data.new_vehicle, 'chassis', '')
            }
        
        if hasattr(extracted_data, 'document') and extracted_data.document:
            result['document'] = {
                'date': getattr(extracted_data.document, 'date', ''),
                'location': getattr(extracted_data.document, 'location', ''),
                'proposal_number': getattr(extracted_data.document, 'proposal_number', '')
            }
        
        if hasattr(extracted_data, 'third_party') and extracted_data.third_party:
            result['third'] = {
                'name': getattr(extracted_data.third_party, 'name', ''),
                'cpf': getattr(extracted_data.third_party, 'cpf', ''),
                'rg': getattr(extracted_data.third_party, 'rg', ''),
                'address': getattr(extracted_data.third_party, 'address', ''),
                'city': getattr(extracted_data.third_party, 'city', ''),
                'cep': getattr(extracted_data.third_party, 'cep', '')
            }
        
        if hasattr(extracted_data, 'payment') and extracted_data.payment:
            result['payment'] = {
                'amount': getattr(extracted_data.payment, 'amount', ''),
                'amount_written': getattr(extracted_data.payment, 'amount_written', ''),
                'method': getattr(extracted_data.payment, 'payment_method', ''),
                'bank_name': getattr(extracted_data.payment, 'bank_name', ''),
                'account': getattr(extracted_data.payment, 'account', ''),
                'agency': getattr(extracted_data.payment, 'agency', '')
            }
        
        return result
    
    @staticmethod
    def dict_to_extracted_data(data_dict: Dict[str, Any]):
        """Convert dictionary to ExtractedData object for validation"""
        import sys
        from pathlib import Path
        
        # CKDEV-NOTE: Add backend root to path for proper imports
        backend_root = Path(__file__).parent.parent.parent
        if str(backend_root) not in sys.path:
            sys.path.insert(0, str(backend_root))
        
        from data.models import ExtractedData, ClientData, VehicleData, DocumentData, PaymentData, ThirdPartyData, NewVehicleData
        
        # CKDEV-NOTE: Convert client data
        client_data = data_dict.get('client', {})
        client = ClientData(
            name=client_data.get('name', ''),
            cpf=client_data.get('cpf', ''),
            rg=client_data.get('rg', ''),
            address=client_data.get('address', ''),
            city=client_data.get('city', ''),
            cep=client_data.get('cep', '')
        )
        
        # CKDEV-NOTE: Convert vehicle data (used vehicle)
        vehicle_data = data_dict.get('usedVehicle', data_dict.get('vehicle', {}))
        vehicle = VehicleData(
            brand=vehicle_data.get('brand', ''),
            model=vehicle_data.get('model', ''),
            plate=vehicle_data.get('plate', ''),
            chassis=vehicle_data.get('chassis', vehicle_data.get('chassi', '')),
            color=vehicle_data.get('color', ''),
            year_model=vehicle_data.get('year', vehicle_data.get('yearModel', vehicle_data.get('year_model', ''))),
            value=vehicle_data.get('value', '')
        )
        
        # CKDEV-NOTE: Convert document data
        document_data = data_dict.get('document', {})
        document = DocumentData(
            date=document_data.get('date', ''),
            location=document_data.get('location', ''),
            proposal_number=document_data.get('proposal_number', '')
        )
        
        # CKDEV-NOTE: Optional payment data
        payment = None
        payment_data = data_dict.get('payment', {})
        if payment_data:
            payment = PaymentData(
                amount=payment_data.get('amount', ''),
                amount_written=payment_data.get('amount_written', ''),
                payment_method=payment_data.get('method', payment_data.get('payment_method', '')),
                bank_name=payment_data.get('bank_name', ''),
                account=payment_data.get('account', ''),
                agency=payment_data.get('agency', '')
            )
        
        # CKDEV-NOTE: Optional third party data
        third_party = None
        third_data = data_dict.get('third', data_dict.get('third_party', {}))
        if third_data:
            third_party = ThirdPartyData(
                name=third_data.get('name', ''),
                cpf=third_data.get('cpf', ''),
                rg=third_data.get('rg', ''),
                address=third_data.get('address', ''),
                city=third_data.get('city', ''),
                cep=third_data.get('cep', '')
            )
        
        # CKDEV-NOTE: Optional new vehicle data
        new_vehicle = None
        new_vehicle_data = data_dict.get('newVehicle', data_dict.get('new_vehicle', {}))
        if new_vehicle_data:
            new_vehicle = NewVehicleData(
                brand=new_vehicle_data.get('brand', ''),
                model=new_vehicle_data.get('model', ''),
                plate=new_vehicle_data.get('plate', ''),
                chassis=new_vehicle_data.get('chassis', new_vehicle_data.get('chassi', '')),
                color=new_vehicle_data.get('color', ''),
                year_model=new_vehicle_data.get('year', new_vehicle_data.get('yearModel', new_vehicle_data.get('year_model', ''))),
                value=new_vehicle_data.get('value', ''),
                sales_order=new_vehicle_data.get('sales_order', '')
            )
        
        return ExtractedData(
            client=client,
            vehicle=vehicle,
            document=document,
            payment=payment,
            third_party=third_party,
            new_vehicle=new_vehicle
        )
    
    @staticmethod
    def update_extracted_data_field(extracted_data, field_path: str, value: str) -> bool:
        """Update a field in extracted data"""
        try:
            section, field_name = field_path.split('.', 1)
            
            field_mapping = {
                'chassi': 'chassis',
                'year': 'year_model',
                'yearModel': 'year_model',
                'method': 'payment_method'
            }
            
            backend_field = field_mapping.get(field_name, field_name)
            
            if section == 'client' and hasattr(extracted_data, 'client') and extracted_data.client:
                setattr(extracted_data.client, backend_field, value)
                return True
            elif section in ['usedVehicle', 'vehicle'] and hasattr(extracted_data, 'vehicle') and extracted_data.vehicle:
                setattr(extracted_data.vehicle, backend_field, value)
                return True
            elif section == 'newVehicle' and hasattr(extracted_data, 'new_vehicle') and extracted_data.new_vehicle:
                setattr(extracted_data.new_vehicle, backend_field, value)
                return True
            elif section == 'document' and hasattr(extracted_data, 'document') and extracted_data.document:
                setattr(extracted_data.document, backend_field, value)
                return True
            elif section == 'third' and hasattr(extracted_data, 'third_party') and extracted_data.third_party:
                setattr(extracted_data.third_party, backend_field, value)
                return True
            elif section == 'payment' and hasattr(extracted_data, 'payment') and extracted_data.payment:
                setattr(extracted_data.payment, backend_field, value)
                return True
            
            return False
        except Exception:
            return False


class RequestHelper:
    """Request helper utilities"""
    
    @staticmethod
    def get_client_ip() -> str:
        """Get client IP address"""
        forwarded_ip = request.headers.get('X-Forwarded-For')
        if forwarded_ip:
            return forwarded_ip.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        return request.remote_addr or 'unknown'
    
    @staticmethod
    def get_user_agent() -> str:
        """Get user agent string"""
        return request.headers.get('User-Agent', 'unknown')
    
    @staticmethod
    def get_request_id() -> str:
        """Get or generate request ID"""
        if hasattr(request, 'request_id'):
            return request.request_id
        
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        return request_id
    
    @staticmethod
    def log_request_info(action: str = "") -> Dict[str, Any]:
        """Get request information for logging"""
        return {
            "action": action,
            "method": request.method,
            "path": request.path,
            "ip": RequestHelper.get_client_ip(),
            "user_agent": RequestHelper.get_user_agent(),
            "request_id": RequestHelper.get_request_id(),
            "timestamp": datetime.utcnow().isoformat()
        }


class TemplateHelper:
    """Template processing helper utilities"""
    
    TEMPLATE_NAMES = {
        "pagamento_terceiro": "Declaração de Pagamento a Terceiro",
        "cessao_credito": "Termo de Cessão de Crédito",
        "responsabilidade_veiculo": "Termo de Responsabilidade de Veículo"
    }
    
    TEMPLATE_ENUM_MAP = {
        'pagamento_terceiro': 'DECLARACAO_PAGAMENTO',
        'cessao_credito': 'TERMO_DACAO_CREDITO', 
        'responsabilidade_veiculo': 'TERMO_RESPONSABILIDADE'
    }
    
    @staticmethod
    def get_template_display_name(template_type: str) -> str:
        """Get display name for template type"""
        return TemplateHelper.TEMPLATE_NAMES.get(template_type, template_type.title())
    
    @staticmethod
    def get_available_templates() -> List[Dict[str, str]]:
        """Get list of available templates"""
        return [
            {"id": "pagamento_terceiro", "name": "Pagamento a Terceiro"},
            {"id": "cessao_credito", "name": "Cessão de Crédito"},
            {"id": "responsabilidade_veiculo", "name": "Responsabilidade de Usado da Troca"}
        ]
    
    @staticmethod
    def validate_template_type(template_type: str) -> bool:
        """Validate template type"""
        return template_type in TemplateHelper.TEMPLATE_NAMES
    
    @staticmethod
    def get_required_data_for_template(template_type: str) -> List[str]:
        """Get required data sections for template"""
        base_requirements = ['client', 'document']
        
        if template_type in ['pagamento_terceiro', 'responsabilidade_veiculo']:
            base_requirements.append('vehicle')
        
        if template_type in ['pagamento_terceiro', 'cessao_credito']:
            base_requirements.append('third_party')
        
        if template_type == 'cessao_credito':
            base_requirements.append('payment')
        
        return base_requirements


class FileHelper:
    """File processing helper utilities"""
    
    @staticmethod
    def get_safe_filename_with_timestamp(original_filename: str, prefix: str = "") -> str:
        """Generate safe filename with timestamp"""
        from .file_utils import FileManager
        
        name, ext = os.path.splitext(original_filename)
        
        safe_name = FileManager.sanitize_filename(name)
        
        timestamp = int(time.time() * 1000)
        
        if prefix:
            final_name = f"{prefix}_{safe_name}_{timestamp}{ext}"
        else:
            final_name = f"{safe_name}_{timestamp}{ext}"
        
        return final_name
    
    @staticmethod
    def check_available_formats(file_path: str) -> List[str]:
        """Check which formats are available for a file"""
        from pathlib import Path
        
        formats = []
        path = Path(file_path)
        
        if path.exists():
            if path.suffix.lower() == '.docx':
                formats.append('docx')
                
                pdf_path = path.with_suffix('.pdf')
                if pdf_path.exists():
                    formats.append('pdf')
        
        return formats
    
    @staticmethod
    def extract_first_name_from_client_data(extracted_data) -> str:
        """Extract first name from client data for filename usage"""
        if not extracted_data or not hasattr(extracted_data, 'client') or not extracted_data.client:
            return ""
        
        client_name = extracted_data.client.name if extracted_data.client.name else ""
        if not client_name.strip():
            return ""
        
        # CKDEV-NOTE: Extract first name and sanitize for filename usage
        first_name = client_name.strip().split()[0] if client_name.strip() else ""
        
        # Remove special characters and keep only letters
        import re
        sanitized_name = re.sub(r'[^A-Za-zÀ-ÿ]', '', first_name)
        
        # Convert to uppercase for consistency
        return sanitized_name.upper() if sanitized_name else ""
    
    @staticmethod 
    def determine_content_type(filename: str) -> str:
        """Determine content type from filename"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        content_types = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png'
        }
        
        return content_types.get(ext, 'application/octet-stream')
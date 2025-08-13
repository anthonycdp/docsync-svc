from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum


class TemplateType(Enum):
    PAGAMENTO_TERCEIRO = "pagamento_terceiro"
    CESSAO_CREDITO = "cessao_credito"
    RESPONSABILIDADE_VEICULO = "responsabilidade_veiculo"
    
    DECLARACAO_PAGAMENTO = "pagamento_terceiro"
    TERMO_DACAO_CREDITO = "cessao_credito"  
    TERMO_RESPONSABILIDADE = "responsabilidade_veiculo"


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


@dataclass
class ValidationResult:
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status.value,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class ClientData:
    name: str = ""
    cpf: str = ""
    rg: str = ""
    address: str = ""
    city: str = ""
    cep: str = ""
    
    def is_valid(self) -> bool:
        return bool(self.name and self.cpf and self.rg and self.address)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cpf": self.cpf,
            "rg": self.rg,
            "address": self.address,
            "city": self.city,
            "cep": self.cep
        }


@dataclass
class VehicleData:
    brand: str = ""
    model: str = ""
    year_model: str = ""
    color: str = ""
    plate: str = ""
    chassis: str = ""
    value: str = ""
    
    def is_valid(self) -> bool:
        return bool(self.brand and self.model and self.plate and self.chassis)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "brand": self.brand,
            "model": self.model,
            "year_model": self.year_model,
            "color": self.color,
            "plate": self.plate,
            "chassis": self.chassis,
            "value": self.value
        }


@dataclass
class NewVehicleData:
    model: str = ""
    year_model: str = ""
    chassis: str = ""
    # CKDEV-NOTE: Added brand field for backward compatibility with old session data
    brand: str = ""
    plate: str = ""
    color: str = ""
    value: str = ""
    sales_order: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "year_model": self.year_model,
            "chassis": self.chassis,
            "brand": self.brand,
            "plate": self.plate,
            "color": self.color,
            "value": self.value,
            "sales_order": self.sales_order
        }


@dataclass
class DocumentData:
    date: str = ""
    location: str = ""
    proposal_number: str = ""
    
    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%d/%m/%Y")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "location": self.location,
            "proposal_number": self.proposal_number
        }


@dataclass
class ThirdPartyData:
    name: str = ""
    cpf: str = ""
    rg: str = ""
    address: str = ""
    city: str = ""
    cep: str = ""
    
    def is_valid(self) -> bool:
        return bool(self.name and self.cpf)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cpf": self.cpf,
            "rg": self.rg,
            "address": self.address,
            "city": self.city,
            "cep": self.cep
        }


@dataclass
class PaymentData:
    amount: str = ""
    amount_written: str = ""
    payment_method: str = ""
    bank_name: str = ""
    account: str = ""
    agency: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "amount": self.amount,
            "amount_written": self.amount_written,
            "payment_method": self.payment_method,
            "bank_name": self.bank_name,
            "account": self.account,
            "agency": self.agency
        }


@dataclass
class ExtractedData:
    client: Optional[ClientData] = None
    vehicle: Optional[VehicleData] = None
    new_vehicle: Optional[NewVehicleData] = None
    document: Optional[DocumentData] = None
    third_party: Optional[ThirdPartyData] = None
    payment: Optional[PaymentData] = None
    
    def __post_init__(self):
        if self.document is None:
            self.document = DocumentData()
    
    def is_valid_for_template(self, template_type: TemplateType) -> bool:
        if not self.client or not self.client.is_valid():
            return False
        
        if template_type in [TemplateType.PAGAMENTO_TERCEIRO, TemplateType.RESPONSABILIDADE_VEICULO]:
            if not self.vehicle or not self.vehicle.is_valid():
                return False
        
        if template_type in [TemplateType.PAGAMENTO_TERCEIRO, TemplateType.CESSAO_CREDITO]:
            if not self.third_party or not self.third_party.is_valid():
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "client": self.client.to_dict() if self.client else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "new_vehicle": self.new_vehicle.to_dict() if self.new_vehicle else None,
            "document": self.document.to_dict() if self.document else None,
            "third_party": self.third_party.to_dict() if self.third_party else None,
            "payment": self.payment.to_dict() if self.payment else None
        }


@dataclass
class SessionData:
    session_id: str
    extracted_data: ExtractedData
    template_type: TemplateType
    files_processed: int
    timestamp: datetime
    validation_results: Dict[str, ValidationResult] = field(default_factory=dict)
    
    def is_expired(self, max_age_hours: int = 24) -> bool:
        # CKDEV-NOTE: Temporarily disable session expiration for debugging
        # TODO: Re-enable after resolving session persistence issues
        return False
        
        # CKDEV-NOTE: Original expiration logic (temporarily disabled)
        # current_time = datetime.now(timezone.utc)
        # session_time = self.timestamp.replace(tzinfo=timezone.utc) if self.timestamp.tzinfo is None else self.timestamp
        # age = current_time - session_time
        # age_hours = age.total_seconds() / 3600
        # 
        # from ..utils.logger import get_service_logger
        # logger = get_service_logger('session')
        # logger.debug(f"Session {self.session_id}: age={age_hours:.2f}h, max={max_age_hours}h, expired={age_hours > max_age_hours}")
        # 
        # return age_hours > max_age_hours
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "template_type": self.template_type.value,
            "files_processed": self.files_processed,
            "timestamp": self.timestamp.isoformat(),
            "extracted_data": self.extracted_data.to_dict(),
            "validation_results": {
                key: result.to_dict() 
                for key, result in self.validation_results.items()
            }
        }


@dataclass
class FileUpload:
    filename: str
    content_type: str
    size: int
    data: bytes
    upload_time: datetime = field(default_factory=datetime.now)
    
    def is_pdf(self) -> bool:
        return (
            self.content_type == "application/pdf" or 
            self.filename.lower().endswith('.pdf')
        )
    
    def is_image(self) -> bool:
        image_types = {"image/jpeg", "image/png", "image/jpg"}
        image_extensions = {'.jpg', '.jpeg', '.png'}
        
        return (
            self.content_type in image_types or
            any(self.filename.lower().endswith(ext) for ext in image_extensions)
        )
    
    def is_docx(self) -> bool:
        return (
            self.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or
            self.filename.lower().endswith('.docx')
        )


@dataclass
class ProcessingResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "message": self.message
        }
        
        if self.data:
            result["data"] = self.data
        
        if self.errors:
            result["errors"] = self.errors
            
        if self.warnings:
            result["warnings"] = self.warnings
        
        return result


@dataclass
class APIResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.meta is None:
            self.meta = {
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def to_dict(self) -> Dict[str, Any]:
        response = {
            "success": self.success
        }
        
        if self.data is not None:
            response["data"] = self.data
            
        if self.message is not None:
            response["message"] = self.message
            
        if self.errors is not None:
            response["errors"] = self.errors
            
        if self.meta is not None:
            response["meta"] = self.meta
        
        return response
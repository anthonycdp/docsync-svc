import re
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

@dataclass
class ClientData:
    name: str = ""; cpf: str = ""; rg: str = ""; address: str = ""; city: str = ""; cep: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class VehicleData:
    brand: str = ""; model: str = ""; plate: str = ""; chassis: str = ""; color: str = ""; year_model: str = ""; value: str = ""
    
    def format_with_commas(self) -> str:
        parts = []; brand_to_use = self.brand.strip()
        if not brand_to_use and self.model.strip(): brand_to_use = self._extract_brand_from_model(self.model.strip())
        if brand_to_use: parts.append(brand_to_use)
        if self.model.strip(): parts.append(f"MODELO {self.model.strip()}")
        if self.chassis.strip(): parts.append(f"CHASSI {self.chassis.strip()}")
        if self.color.strip(): parts.append(f"COR {self.color.strip()}")
        if self.plate.strip(): parts.append(f"PLACA {self.plate.strip()}")
        if self.year_model.strip(): parts.append(self.year_model.strip())
        return ", ".join(parts) + "," if parts else ""
    def _extract_brand_from_model(self, model: str) -> str:
        """Extrai marca do modelo usando tabela CSV + fallback"""
        if not model: return ""
        try:
            try: from ..utils.brand_lookup import get_brand_lookup
            except ImportError: from utils.brand_lookup import get_brand_lookup
            brand_lookup = get_brand_lookup(); brand = brand_lookup.get_fallback_brand(model)
            return brand if brand else ""
        except Exception as e:
            # Fallback: extrai a primeira palavra do modelo como marca
            words = model.strip().split() if model else []
            return words[0] if words else ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentData:
    date: str = ""; location: str = ""; proposal_number: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass  
class PaymentData:
    amount: str = ""; amount_written: str = ""; payment_method: str = ""; bank_name: str = ""; account: str = ""; agency: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class PartyData:
    name: str = ""; cpf: str = ""; rg: str = ""; address: str = ""; role: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class NewVehicleData:
    brand: str = ""; model: str = ""; plate: str = ""; chassis: str = ""; color: str = ""; year_model: str = ""; value: str = ""; sales_order: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ThirdPartyData:
    name: str = ""; cpf: str = ""; rg: str = ""; address: str = ""; city: str = ""; cep: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExtractedData:
    client: ClientData; vehicle: VehicleData; document: DocumentData
    payment: Optional[PaymentData] = None; parties: Optional[List[PartyData]] = None
    new_vehicle: Optional[NewVehicleData] = None; third_party: Optional[ThirdPartyData] = None
    
    def validate(self) -> List[str]:
        errors = []
        if not self.client.name.strip(): errors.append("Nome do cliente obrigatório")
        if not self.client.cpf.strip(): errors.append("CPF do cliente obrigatório")
        if not self.vehicle.model.strip(): errors.append("Modelo do veículo obrigatório")
        if not self.vehicle.plate.strip(): errors.append("Placa do veículo obrigatória")
        if not self.document.date.strip(): errors.append("Data do documento obrigatória")
        return errors
    def sanitize_for_logging(self) -> Dict[str, Any]:
        return {
            'client': {'name': self.client.name[:3] + "***" if self.client.name else "", 'cpf': "***" if self.client.cpf else "", 'rg': "***" if self.client.rg else "", 'address': "***" if self.client.address else "", 'city': self.client.city, 'cep': "***" if self.client.cep else ""},
            'vehicle': {'brand': self.vehicle.brand, 'model': self.vehicle.model, 'plate': "***" if self.vehicle.plate else "", 'chassis': "***" if self.vehicle.chassis else "", 'color': self.vehicle.color, 'year_model': self.vehicle.year_model, 'value': "***" if self.vehicle.value else ""},
            'document': {'date': self.document.date, 'location': self.document.location, 'proposal_number': "***" if self.document.proposal_number else ""}
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
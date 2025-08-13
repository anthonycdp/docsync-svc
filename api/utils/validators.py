"""Validation utilities"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..models import ValidationResult, ValidationStatus, ExtractedData, TemplateType


class DataValidator:
    """Data validation utility class"""
    
    KNOWN_VEHICLE_COLORS = {
        'PRETO', 'BRANCO', 'PRATA', 'CINZA', 'AZUL', 'VERMELHO',
        'VERDE', 'AMARELO', 'DOURADO', 'MARROM', 'BEGE', 'LARANJA',
        'ROSA', 'ROXO', 'VINHO', 'BORDÔ', 'GRAFITE', 'CHAMPAGNE',
        'BRONZE', 'COBRE', 'PÉROLA', 'METÁLICO', 'FOSCO',
        'PRETO METÁLICO', 'BRANCO PEROLA', 'PRATA METALICO',
        'CINZA METALICO', 'AZUL METALICO', 'VERMELHO METÁLICO',
        'VERDE METALICO'
    }
    
    @staticmethod
    def validate_cpf(cpf: str) -> ValidationResult:
        """Validate Brazilian CPF"""
        if not cpf:
            return ValidationResult(
                ValidationStatus.INVALID,
                "CPF é obrigatório"
            )
        
        clean_cpf = re.sub(r'[^\d]', '', str(cpf))
        
        if len(clean_cpf) != 11:
            return ValidationResult(
                ValidationStatus.INVALID,
                "CPF deve ter 11 dígitos"
            )
        
        if clean_cpf == clean_cpf[0] * 11:
            return ValidationResult(
                ValidationStatus.INVALID,
                "CPF inválido - dígitos repetidos"
            )
        
        def calculate_digit(digits: str, position: int) -> str:
            total = sum(int(digits[i]) * (position + 1 - i) for i in range(position))
            remainder = total % 11
            return '0' if remainder < 2 else str(11 - remainder)
        
        if (clean_cpf[9] != calculate_digit(clean_cpf, 9) or
            clean_cpf[10] != calculate_digit(clean_cpf, 10)):
            return ValidationResult(
                ValidationStatus.INVALID,
                "CPF inválido - dígitos verificadores incorretos"
            )
        
        return ValidationResult(
            ValidationStatus.VALID,
            "CPF válido"
        )
    
    @staticmethod
    def validate_rg(rg: str) -> ValidationResult:
        """Validate Brazilian RG"""
        if not rg:
            return ValidationResult(
                ValidationStatus.INVALID,
                "RG é obrigatório"
            )
        
        clean_rg = re.sub(r'[^\w]', '', str(rg)).upper()
        
        if len(clean_rg) < 7:
            return ValidationResult(
                ValidationStatus.INVALID,
                "RG muito curto"
            )
        
        if len(clean_rg) > 15:
            return ValidationResult(
                ValidationStatus.INVALID,
                "RG muito longo"
            )
        
        if len(clean_rg) >= 7 and len(clean_rg) <= 12:
            return ValidationResult(
                ValidationStatus.VALID,
                "RG válido"
            )
        
        return ValidationResult(
            ValidationStatus.WARNING,
            "RG pode estar incompleto - verifique o formato"
        )
    
    @staticmethod
    def validate_vehicle_plate(plate: str) -> ValidationResult:
        """Validate Brazilian vehicle plate"""
        if not plate:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Placa é obrigatória"
            )
        
        plate = str(plate).upper().strip()
        
        old_format = re.match(r'^[A-Z]{3}-\d{4}$', plate)
        mercosul_format = re.match(r'^[A-Z]{3}\d[A-Z]\d{2}$', plate)
        
        if old_format or mercosul_format:
            return ValidationResult(
                ValidationStatus.VALID,
                "Placa válida"
            )
        
        return ValidationResult(
            ValidationStatus.INVALID,
            "Formato de placa inválido - use AAA-0000 ou AAA0A00"
        )
    
    @staticmethod
    def validate_vehicle_chassis(chassis: str) -> ValidationResult:
        """Validate vehicle chassis (VIN)"""
        if not chassis:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Chassi é obrigatório"
            )
        
        chassis = str(chassis).upper().strip()
        
        if len(chassis) != 17:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Chassi deve ter exatamente 17 caracteres"
            )
        
        if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', chassis):
            return ValidationResult(
                ValidationStatus.INVALID,
                "Formato de chassi inválido"
            )
        
        return ValidationResult(
            ValidationStatus.VALID,
            "Chassi válido"
        )
    
    @staticmethod
    def validate_vehicle_color(color: str) -> ValidationResult:
        """Validate vehicle color"""
        if not color:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Cor é obrigatória"
            )
        
        color_normalized = str(color).upper().strip()
        
        if color_normalized in DataValidator.KNOWN_VEHICLE_COLORS:
            return ValidationResult(
                ValidationStatus.VALID,
                "Cor válida"
            )
        
        for known_color in DataValidator.KNOWN_VEHICLE_COLORS:
            if color_normalized in known_color or known_color in color_normalized:
                return ValidationResult(
                    ValidationStatus.WARNING,
                    f"Cor similar encontrada: {known_color}"
                )
        
        return ValidationResult(
            ValidationStatus.WARNING,
            "Cor não reconhecida - confirmar se está correta"
        )
    
    @staticmethod
    def validate_date(date_str: str) -> ValidationResult:
        """Validate date string in DD/MM/YYYY format"""
        if not date_str:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Data é obrigatória"
            )
        
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
            return ValidationResult(
                ValidationStatus.INVALID,
                "Data deve ter formato DD/MM/AAAA"
            )
        
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            
            current_date = datetime.now()
            
            if date_obj.year < current_date.year - 10:
                return ValidationResult(
                    ValidationStatus.WARNING,
                    "Data muito antiga - confirmar se está correta"
                )
            
            if date_obj.date() > current_date.date():
                return ValidationResult(
                    ValidationStatus.INVALID,
                    "Data não pode ser futura"
                )
            
            return ValidationResult(
                ValidationStatus.VALID,
                "Data válida"
            )
        
        except ValueError:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Data inválida - verificar dia, mês e ano"
            )
    
    @staticmethod
    def validate_currency_amount(amount: str) -> ValidationResult:
        """Validate currency amount in Brazilian format"""
        if not amount:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Valor é obrigatório"
            )
        
        if not re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$', amount):
            return ValidationResult(
                ValidationStatus.INVALID,
                "Valor deve ter formato 000.000,00"
            )
        
        try:
            float_value = float(amount.replace('.', '').replace(',', '.'))
            
            if float_value <= 0:
                return ValidationResult(
                    ValidationStatus.INVALID,
                    "Valor deve ser maior que zero"
                )
            
            if float_value > 10000000:
                return ValidationResult(
                    ValidationStatus.WARNING,
                    "Valor muito alto - confirmar se está correto"
                )
            
            return ValidationResult(
                ValidationStatus.VALID,
                "Valor válido"
            )
        
        except ValueError:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Formato de valor inválido"
            )
    
    @staticmethod
    def validate_address(address: str) -> ValidationResult:
        """Validate address completeness"""
        if not address:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Endereço é obrigatório"
            )
        
        address = str(address).strip()
        
        if len(address) < 10:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Endereço muito curto - deve conter rua, número, bairro e cidade"
            )
        
        has_number = re.search(r'\d+', address)
        has_comma = ',' in address or '-' in address
        
        if not has_number:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Endereço pode estar incompleto - verificar número"
            )
        
        if len(address) < 30 and not has_comma:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Endereço pode estar incompleto - verificar bairro e cidade"
            )
        
        return ValidationResult(
            ValidationStatus.VALID,
            "Endereço completo"
        )


class TemplateValidator:
    """Template-specific validation"""
    
    @staticmethod
    def validate_for_template(
        data: ExtractedData, 
        template_type: TemplateType
    ) -> Dict[str, ValidationResult]:
        """Validate data for specific template type"""
        results = {}
        
        if data.client:
            results.update(TemplateValidator._validate_client_data(data.client))
        else:
            results['client'] = ValidationResult(
                ValidationStatus.INVALID,
                "Dados do cliente são obrigatórios"
            )
        
        if data.document:
            results.update(TemplateValidator._validate_document_data(data.document))
        else:
            results['document.date'] = ValidationResult(
                ValidationStatus.INVALID,
                "Data do documento é obrigatória"
            )
        
        if template_type in [TemplateType.PAGAMENTO_TERCEIRO, TemplateType.RESPONSABILIDADE_VEICULO]:
            if data.vehicle:
                results.update(TemplateValidator._validate_vehicle_data(data.vehicle))
            else:
                results['vehicle'] = ValidationResult(
                    ValidationStatus.INVALID,
                    "Dados do veículo são obrigatórios para este template"
                )
        
        if template_type in [TemplateType.PAGAMENTO_TERCEIRO, TemplateType.CESSAO_CREDITO]:
            if data.third_party:
                results.update(TemplateValidator._validate_third_party_data(data.third_party))
            else:
                results['third_party'] = ValidationResult(
                    ValidationStatus.INVALID,
                    "Dados do terceiro são obrigatórios para este template"
                )
        
        return results
    
    @staticmethod
    def _validate_client_data(client) -> Dict[str, ValidationResult]:
        """Validate client data"""
        results = {}
        
        if hasattr(client, 'name') and client.name:
            if len(client.name.strip()) >= 2:
                results['client.name'] = ValidationResult(
                    ValidationStatus.VALID, "Nome válido"
                )
            else:
                results['client.name'] = ValidationResult(
                    ValidationStatus.INVALID, "Nome muito curto"
                )
        else:
            results['client.name'] = ValidationResult(
                ValidationStatus.INVALID, "Nome obrigatório"
            )
        
        if hasattr(client, 'cpf'):
            results['client.cpf'] = DataValidator.validate_cpf(client.cpf)
        else:
            results['client.cpf'] = ValidationResult(
                ValidationStatus.INVALID, "CPF obrigatório"
            )
        
        if hasattr(client, 'rg'):
            results['client.rg'] = DataValidator.validate_rg(client.rg)
        else:
            results['client.rg'] = ValidationResult(
                ValidationStatus.INVALID, "RG obrigatório"
            )
        
        if hasattr(client, 'address'):
            results['client.address'] = DataValidator.validate_address(client.address)
        else:
            results['client.address'] = ValidationResult(
                ValidationStatus.INVALID, "Endereço obrigatório"
            )
        
        return results
    
    @staticmethod
    def _validate_vehicle_data(vehicle) -> Dict[str, ValidationResult]:
        """Validate vehicle data"""
        results = {}
        
        if hasattr(vehicle, 'brand') and vehicle.brand and vehicle.brand != '-':
            results['usedVehicle.brand'] = ValidationResult(
                ValidationStatus.VALID, "Marca identificada"
            )
        else:
            results['usedVehicle.brand'] = ValidationResult(
                ValidationStatus.INVALID, "Marca obrigatória"
            )
        
        if hasattr(vehicle, 'model') and vehicle.model and vehicle.model != '-':
            results['usedVehicle.model'] = ValidationResult(
                ValidationStatus.VALID, "Modelo válido"
            )
        else:
            results['usedVehicle.model'] = ValidationResult(
                ValidationStatus.INVALID, "Modelo obrigatório"
            )
        
        if hasattr(vehicle, 'year_model') and vehicle.year_model:
            results['usedVehicle.year'] = ValidationResult(
                ValidationStatus.VALID, "Ano/modelo válido"
            )
        else:
            results['usedVehicle.year'] = ValidationResult(
                ValidationStatus.WARNING, "Verificar ano/modelo"
            )
        
        if hasattr(vehicle, 'color'):
            results['usedVehicle.color'] = DataValidator.validate_vehicle_color(vehicle.color)
        else:
            results['usedVehicle.color'] = ValidationResult(
                ValidationStatus.INVALID, "Cor obrigatória"
            )
        
        if hasattr(vehicle, 'plate'):
            results['usedVehicle.plate'] = DataValidator.validate_vehicle_plate(vehicle.plate)
        else:
            results['usedVehicle.plate'] = ValidationResult(
                ValidationStatus.INVALID, "Placa obrigatória"
            )
        
        if hasattr(vehicle, 'chassis'):
            results['usedVehicle.chassi'] = DataValidator.validate_vehicle_chassis(vehicle.chassis)
        else:
            results['usedVehicle.chassi'] = ValidationResult(
                ValidationStatus.INVALID, "Chassi obrigatório"
            )
        
        # CKDEV-NOTE: Adicionar validação para valor do veículo que estava faltando
        if hasattr(vehicle, 'value') and vehicle.value:
            results['usedVehicle.value'] = DataValidator.validate_currency_amount(vehicle.value)
        else:
            results['usedVehicle.value'] = ValidationResult(
                ValidationStatus.WARNING, "Valor do veículo não informado"
            )
        
        return results
    
    @staticmethod
    def _validate_document_data(document) -> Dict[str, ValidationResult]:
        """Validate document data"""
        results = {}
        
        if hasattr(document, 'date'):
            results['document.date'] = DataValidator.validate_date(document.date)
        else:
            results['document.date'] = ValidationResult(
                ValidationStatus.INVALID, "Data obrigatória"
            )
        
        return results
    
    @staticmethod
    def _validate_third_party_data(third_party) -> Dict[str, ValidationResult]:
        """Validate third party data"""
        results = {}
        
        if hasattr(third_party, 'name') and third_party.name:
            results['third.name'] = ValidationResult(
                ValidationStatus.VALID, "Nome do terceiro válido"
            )
        else:
            results['third.name'] = ValidationResult(
                ValidationStatus.INVALID, "Nome do terceiro obrigatório"
            )
        
        if hasattr(third_party, 'cpf') and third_party.cpf:
            results['third.cpf'] = ValidationResult(
                ValidationStatus.VALID, "CPF/CNPJ do terceiro válido"
            )
        else:
            results['third.cpf'] = ValidationResult(
                ValidationStatus.INVALID, "CPF/CNPJ do terceiro obrigatório"
            )
        
        return results
import re
from typing import Dict, Any, Union

def validate_cpf(cpf: str) -> bool:
    if not cpf: return False
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11: return False
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9)); remainder1 = sum1 % 11; digit1 = 0 if remainder1 < 2 else 11 - remainder1
    if int(cpf[9]) != digit1: return False
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10)); remainder2 = sum2 % 11; digit2 = 0 if remainder2 < 2 else 11 - remainder2
    return int(cpf[10]) == digit2
def validate_vehicle_plate(plate: str) -> bool:
    if not plate: return False
    plate = plate.strip().upper()
    return bool(re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', plate) or re.match(r'^[A-Z]{3}[0-9]{4}$', plate))
def validate_chassis_number(chassis: str) -> bool:
    if not chassis: return False
    return bool(re.match(r'^[A-HJ-NPR-Z0-9]{17}$', chassis.strip().upper()))
def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    sensitive_keys = {'cpf', 'rg', 'document_number', 'chassis', 'plate', 'proposal_number', 'value', 'account', 'agency', 'address', 'cep'}
    def sanitize_value(key: str, value: Any) -> Any:
        return (value[:3] + "***" if len(value) > 3 else "***") if key.lower() in sensitive_keys and isinstance(value, str) and value.strip() else "***" if key.lower() in sensitive_keys else sanitize_log_data(value) if isinstance(value, dict) else [sanitize_value(key, item) for item in value] if isinstance(value, list) else value
    return {key: sanitize_value(key, value) for key, value in data.items()}


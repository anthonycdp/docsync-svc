"""Data schemas and validation models"""

import re
from datetime import datetime
from typing import Optional
from marshmallow import Schema, fields, validate, validates, ValidationError, post_load
from marshmallow.decorators import validates_schema


class CPFField(fields.String):
    
    def _validate(self, value, attr, data, **kwargs):
        if not value:
            return
        
        cpf = re.sub(r'[^\d]', '', str(value))
        
        if len(cpf) != 11:
            raise ValidationError("CPF deve ter 11 dígitos")
        
        if cpf == cpf[0] * 11:
            raise ValidationError("CPF inválido")
        
        def validate_cpf_digit(cpf_digits, digit_position):
            total = sum(int(cpf_digits[i]) * (digit_position + 1 - i) 
                       for i in range(digit_position))
            remainder = total % 11
            return '0' if remainder < 2 else str(11 - remainder)
        
        if (cpf[9] != validate_cpf_digit(cpf, 9) or 
            cpf[10] != validate_cpf_digit(cpf, 10)):
            raise ValidationError("CPF inválido")


class BrazilianPlateField(fields.String):
    
    def _validate(self, value, attr, data, **kwargs):
        if not value:
            return
        
        value = str(value).upper().strip()
        
        old_format = re.match(r'^[A-Z]{3}-\d{4}$', value)
        new_format = re.match(r'^[A-Z]{3}\d[A-Z]\d{2}$', value)
        
        if not (old_format or new_format):
            raise ValidationError("Formato de placa inválido")


class ChassisField(fields.String):
    
    def _validate(self, value, attr, data, **kwargs):
        if not value:
            return
        
        value = str(value).upper().strip()
        
        if len(value) != 17:
            raise ValidationError("Chassi deve ter 17 caracteres")
        
        if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', value):
            raise ValidationError("Formato de chassi inválido")


class ClientDataSchema(Schema):
    
    name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={
            "required": "Nome é obrigatório",
            "invalid": "Nome deve ser uma string válida"
        }
    )
    
    cpf = CPFField(
        required=True,
        error_messages={
            "required": "CPF é obrigatório"
        }
    )
    
    rg = fields.String(
        required=True,
        validate=validate.Length(min=7, max=15),
        error_messages={
            "required": "RG é obrigatório",
            "invalid": "RG deve ter entre 7 e 15 caracteres"
        }
    )
    
    address = fields.String(
        required=True,
        validate=validate.Length(min=10, max=200),
        error_messages={
            "required": "Endereço é obrigatório",
            "invalid": "Endereço deve ter entre 10 e 200 caracteres"
        }
    )
    
    city = fields.String(
        allow_none=True,
        validate=validate.Length(max=50)
    )
    
    cep = fields.String(
        allow_none=True,
        validate=validate.Regexp(
            regex=r'^\d{5}-?\d{3}$',
            error="CEP deve ter o formato 00000-000"
        )
    )
    
    @validates("name")
    def validate_name(self, value):
        if not value or not value.strip():
            raise ValidationError("Nome não pode estar vazio")
        
        if not re.match(r'^[A-Za-zÀ-ÿ\s]+$', value):
            raise ValidationError("Nome deve conter apenas letras e espaços")


class VehicleDataSchema(Schema):
    
    brand = fields.String(
        required=True,
        validate=validate.Length(min=2, max=30),
        error_messages={
            "required": "Marca é obrigatória"
        }
    )
    
    model = fields.String(
        required=True,
        validate=validate.Length(min=2, max=50),
        error_messages={
            "required": "Modelo é obrigatório"
        }
    )
    
    year_model = fields.String(
        allow_none=True,
        validate=validate.Regexp(
            regex=r'^\d{4}(/\d{4})?$',
            error="Ano deve ter formato AAAA ou AAAA/AAAA"
        )
    )
    
    color = fields.String(
        required=True,
        validate=validate.Length(min=3, max=20),
        error_messages={
            "required": "Cor é obrigatória"
        }
    )
    
    plate = BrazilianPlateField(
        required=True,
        error_messages={
            "required": "Placa é obrigatória"
        }
    )
    
    chassis = ChassisField(
        required=True,
        error_messages={
            "required": "Chassi é obrigatório"
        }
    )
    
    value = fields.String(
        allow_none=True,
        validate=validate.Regexp(
            regex=r'^\d{1,3}(\.\d{3})*,\d{2}$',
            error="Valor deve ter formato 000.000,00"
        )
    )
    
    @validates("color")
    def validate_color(self, value):
        if not value:
            return
        
        known_colors = {
            'PRETO', 'BRANCO', 'PRATA', 'CINZA', 'AZUL', 'VERMELHO',
            'VERDE', 'AMARELO', 'DOURADO', 'MARROM', 'BEGE', 'LARANJA',
            'ROSA', 'ROXO', 'VINHO', 'BORDÔ', 'GRAFITE', 'CHAMPAGNE',
            'BRONZE', 'COBRE', 'PÉROLA', 'METÁLICO', 'FOSCO',
            'PRETO METÁLICO', 'BRANCO PEROLA', 'PRATA METALICO',
            'CINZA METALICO', 'AZUL METALICO', 'VERMELHO METÁLICO',
            'VERDE METALICO'
        }
        
        if value.upper() not in known_colors:
            raise ValidationError(f"Cor '{value}' não reconhecida")


class DocumentDataSchema(Schema):
    
    date = fields.String(
        required=True,
        validate=validate.Regexp(
            regex=r'^\d{2}/\d{2}/\d{4}$',
            error="Data deve ter formato DD/MM/AAAA"
        ),
        error_messages={
            "required": "Data é obrigatória"
        }
    )
    
    location = fields.String(
        allow_none=True,
        validate=validate.Length(max=50)
    )
    
    proposal_number = fields.String(
        allow_none=True,
        validate=validate.Length(max=20)
    )
    
    @validates("date")
    def validate_date(self, value):
        try:
            date_obj = datetime.strptime(value, "%d/%m/%Y")
            
            if date_obj.year < datetime.now().year - 10:
                raise ValidationError("Data muito antiga")
                
            if date_obj.date() > datetime.now().date():
                raise ValidationError("Data não pode ser futura")
                
        except ValueError:
            raise ValidationError("Data inválida")


class ThirdPartyDataSchema(Schema):
    
    name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={
            "required": "Nome do terceiro é obrigatório"
        }
    )
    
    cpf = fields.String(
        required=True,
        error_messages={
            "required": "CPF/CNPJ do terceiro é obrigatório"
        }
    )
    
    rg = fields.String(
        allow_none=True,
        validate=validate.Length(min=7, max=20)
    )
    
    address = fields.String(
        allow_none=True,
        validate=validate.Length(min=10, max=200)
    )
    
    city = fields.String(
        allow_none=True,
        validate=validate.Length(max=50)
    )
    
    cep = fields.String(
        allow_none=True,
        validate=validate.Regexp(
            regex=r'^\d{5}-?\d{3}$',
            error="CEP deve ter o formato 00000-000"
        )
    )
    
    @validates("cpf")
    def validate_cpf_or_cnpj(self, value):
        if not value:
            return
        
        document = re.sub(r'[^\d]', '', str(value))
        
        if len(document) == 11:
            if document == document[0] * 11:
                raise ValidationError("CPF inválido")
        elif len(document) == 14:
            if document == document[0] * 14:
                raise ValidationError("CNPJ inválido")
        else:
            raise ValidationError("CPF deve ter 11 dígitos ou CNPJ deve ter 14 dígitos")


class PaymentDataSchema(Schema):
    
    amount = fields.String(
        required=True,
        validate=validate.Regexp(
            regex=r'^\d{1,3}(\.\d{3})*,\d{2}$',
            error="Valor deve ter formato 000.000,00"
        ),
        error_messages={
            "required": "Valor é obrigatório"
        }
    )
    
    amount_written = fields.String(
        allow_none=True,
        validate=validate.Length(max=200)
    )
    
    payment_method = fields.String(
        allow_none=True,
        validate=validate.OneOf([
            "PIX", "TED", "DOC", "DINHEIRO", "CHEQUE", "BOLETO", "CARTÃO"
        ])
    )
    
    bank_name = fields.String(
        allow_none=True,
        validate=validate.Length(max=50)
    )
    
    account = fields.String(
        allow_none=True,
        validate=validate.Length(max=20)
    )
    
    agency = fields.String(
        allow_none=True,
        validate=validate.Length(max=10)
    )


class ExtractedDataSchema(Schema):
    
    client = fields.Nested(ClientDataSchema, required=True)
    vehicle = fields.Nested(VehicleDataSchema, allow_none=True)
    new_vehicle = fields.Nested(VehicleDataSchema, allow_none=True)
    document = fields.Nested(DocumentDataSchema, required=True)
    third_party = fields.Nested(ThirdPartyDataSchema, allow_none=True)
    payment = fields.Nested(PaymentDataSchema, allow_none=True)
    
    @validates_schema
    def validate_template_requirements(self, data, **kwargs):
        if not data.get("client"):
            raise ValidationError("Dados do cliente são obrigatórios")


class FileUploadSchema(Schema):
    
    filename = fields.String(required=True)
    content_type = fields.String(allow_none=True)
    size = fields.Integer(validate=validate.Range(min=1, max=16*1024*1024))
    
    @validates("filename")
    def validate_filename(self, value):
        if not value or '..' in value or '/' in value or '\\' in value:
            raise ValidationError("Nome de arquivo inválido")
        
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.docx'}
        file_extension = value.lower().split('.')[-1] if '.' in value else ''
        
        if f'.{file_extension}' not in allowed_extensions:
            raise ValidationError(
                f"Tipo de arquivo não permitido. Permitidos: {', '.join(allowed_extensions)}"
            )


class SessionUpdateSchema(Schema):
    
    field = fields.String(
        required=True,
        validate=validate.Regexp(
            regex=r'^(client|vehicle|usedVehicle|newVehicle|document|third|payment)\.[a-zA-Z_]+$',
            error="Campo deve ter formato 'seção.campo'"
        )
    )
    
    value = fields.String(required=True, allow_none=True)
    
    @validates("field")
    def validate_field_path(self, value):
        valid_sections = {
            'client': ['name', 'cpf', 'rg', 'address', 'city', 'cep'],
            'vehicle': ['brand', 'model', 'year_model', 'color', 'plate', 'chassis', 'value'],
            'usedVehicle': ['brand', 'model', 'year', 'color', 'plate', 'chassi', 'value'],
            'newVehicle': ['model', 'yearModel', 'chassi'],
            'document': ['date', 'location', 'proposal_number'],
            'third': ['name', 'cpf', 'rg', 'address', 'city', 'cep'],
            'payment': ['amount', 'amount_written', 'method', 'bank_name', 'account', 'agency']
        }
        
        section, field_name = value.split('.', 1)
        
        if section not in valid_sections:
            raise ValidationError(f"Seção '{section}' não é válida")
        
        if field_name not in valid_sections[section]:
            raise ValidationError(f"Campo '{field_name}' não é válido para seção '{section}'")


class TemplateGenerationSchema(Schema):
    
    template_type = fields.String(
        required=True,
        validate=validate.OneOf([
            'pagamento_terceiro',
            'cessao_credito', 
            'responsabilidade_veiculo'
        ]),
        error_messages={
            "required": "Tipo de template é obrigatório"
        }
    )
    
    format_type = fields.String(
        validate=validate.OneOf(['docx', 'pdf']),
        load_default='docx'
    )
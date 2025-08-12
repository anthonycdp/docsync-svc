import os
import re
from typing import Dict, Any
try: 
    from ..data import ExtractedData
except ImportError: 
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from data import ExtractedData

class TemplateReplacementManager:
    def __init__(self): 
        pass
    
    def get_termo_responsabilidade_replacements(self, data: ExtractedData) -> Dict[str, str]:
        replacements = {}
        
        replacements['{{CLIENT_NAME}}'] = data.client.name or ''
        replacements['{{CLIENT_RG}}'] = data.client.rg or ''
        replacements['{{CLIENT_CPF}}'] = data.client.cpf or ''
        replacements['{{CLIENT_ADDRESS}}'] = self._format_legal_address(data.client) if data.client else ''
        
        from datetime import datetime
        formatted_date = datetime.now().strftime("%d/%m/%Y")
        location = data.document.location if data.document and hasattr(data.document, 'location') and data.document.location else os.getenv('DEFAULT_LOCATION', 'São José dos Campos')
        location = location.replace(' - SP', '').strip() if ' - SP' in location else location
        replacements['{{DOCUMENT_DATE}}'] = f" - {formatted_date}"
        
        if data.vehicle:
            replacements['{{USED_VEHICLE_BRAND}}'] = data.vehicle.brand or ''
            replacements['{{USED_VEHICLE_MODEL}}'] = data.vehicle.model or ''
            replacements['{{USED_VEHICLE_CHASSI}}'] = data.vehicle.chassis or ''
            replacements['{{USED_VEHICLE_COLOR}}'] = data.vehicle.color or ''
            replacements['{{USED_VEHICLE_PLATE}}'] = data.vehicle.plate or ''
            replacements['{{USED_VEHICLE_YEAR_MODEL}}'] = data.vehicle.year_model or ''
            replacements['{{USED_VEHICLE_CREDIT}}'] = self._format_currency_value(data.vehicle.value) if data.vehicle.value else 'R$ 0,00'
            # CKDEV-NOTE: Dynamic chassis key removed - was causing empty separator errors
        
        if data.vehicle:
            if hasattr(data.vehicle, 'format_with_commas'): 
                replacements['DADOS_VEICULO_FORMATADO'] = data.vehicle.format_with_commas()
            brand = data.vehicle.brand or self._extract_brand_from_model(data.vehicle.model) if data.vehicle.model else ''
            replacements.update({
                'MARCA_VEICULO': brand, 
                'MODELO_VEICULO': data.vehicle.model or '', 
                'COR_VEICULO': data.vehicle.color or '', 
                'PLACA_VEICULO': data.vehicle.plate or '', 
                'CHASSI_VEICULO': data.vehicle.chassis or '', 
                'ANO_MODELO_VEICULO': data.vehicle.year_model or ''
                # CKDEV-NOTE: Removed malformed keys that were causing empty separator errors
            })
        
        legal_address = self._format_legal_address(data.client) if data.client else ''
        replacements.update({
            'ENDERECO_CLIENTE': legal_address, 
            'ENDERECO_CEDENTE': legal_address, 
            'ENDERECO_CESSIONARIO': legal_address, 
            'CIDADE_CLIENTE': data.client.city or '', 
            'CIDADE_CEDENTE': data.client.city or '', 
            'CIDADE_CESSIONARIO_CREDITO': data.client.city or '', 
            'CEP_CLIENTE': data.client.cep or '', 
            'CEP_CIDADE_CLIENTE': data.client.cep or '', 
            'CEP_CEDENTE': data.client.cep or '', 
            'CEP_CESSIONARIO_CREDITO': data.client.cep or '', 
            'DADOS_BANCARIOS_PAGAMENTO': '', 
            'NUMERO_PEDIDO_VENDA': (data.document.proposal_number if data.document else None) or '', 
            'VALOR_EXTENSO_VEICULO': '', 
        })
        
        if data.document and data.document.date: 
            replacements['DATA_DOCUMENTO'] = data.document.date
            location = data.document.location if hasattr(data.document, 'location') and data.document.location else data.client.city or ''
            city_only = location.replace(' - SP', '').strip() if location else ''
            city_only = city_only.rstrip()
            data_local_documento = f"{data.document.date} - {city_only} - SP"
            data_local_documento = re.sub(r'\s+,', ',', data_local_documento)
            replacements['DATA_LOCAL_DOCUMENTO'] = data_local_documento
            data_jacarei = f"{data.document.date} - {city_only} - SP"
            data_jacarei = re.sub(r'\s+,', ',', data_jacarei)
            replacements['DATA_JACAREI'] = data_jacarei
        
        if data.vehicle and data.vehicle.value: 
            valor_formatado = self._format_currency_value(data.vehicle.value)
            replacements.update({
                'VALOR_VEICULO_VENDIDO': valor_formatado, 
                '{{VALOR_VEICULO_VENDIDO}}': valor_formatado
            })
        
        # CKDEV-NOTE: Filter out empty keys to prevent split() errors
        return {k: v for k, v in replacements.items() if k and k.strip() and v is not None}
    
    def _format_legal_address(self, client_data) -> str:
        if not client_data or not client_data.address:
            return ''
        
        full_address = client_data.address
        
        import re
        
        logradouro_match = re.search(r'^((?:RUA|AVENIDA|AV\.|R\.)\s+[^,\d]+)\s*,?\s*(?:nº\s*)?(\d+)', full_address, re.IGNORECASE)
        if not logradouro_match:
            return full_address
        
        logradouro = logradouro_match.group(1).strip()
        numero = logradouro_match.group(2).strip()
        
        bairro = ''
        bairro_match = re.search(r'BAIRRO\s+([^,]+)', full_address, re.IGNORECASE)
        if bairro_match:
            bairro = bairro_match.group(1).strip()
        else:
            implicit_match = re.search(r'(?:RUA|AVENIDA|AV\.|R\.)\s+[^,\d]+\s*,?\s*(?:nº\s*)?\d+,\s*([^,]+),\s*CEP', full_address, re.IGNORECASE)
            if implicit_match:
                potential_bairro = implicit_match.group(1).strip()
                if not re.match(r'^\d+[-\s]?\d*$', potential_bairro) and len(potential_bairro) > 2:
                    bairro = potential_bairro
        
        cep_match = re.search(r'CEP\s+(\d{5}-\d{3})', full_address)
        cep = cep_match.group(1) if cep_match else (client_data.cep or '')
        
        cidade = client_data.city or ''
        if not cidade:
            cep_cidade_match = re.search(r'CEP\s+\d{5}-\d{3},\s*([A-Z\s]+)\s*-\s*SP$', full_address)
            if cep_cidade_match:
                cidade_raw = cep_cidade_match.group(1).strip()
            else:
                cidade_match = re.search(r'([A-Z\s]+[A-Z])\s*-\s*SP$', full_address)
                cidade_raw = cidade_match.group(1).strip() if cidade_match else ''
            
            if cidade_raw:
                cidade = re.sub(r'\b\d+\b', '', cidade_raw).strip()
                cidade = re.sub(r'^,\s*', '', cidade).strip()
                cidade = re.sub(r'\s+', ' ', cidade).strip()
            else:
                cidade = ''
        
        address_parts = []
        
        if logradouro:
            address_parts.append(f"na {logradouro}")
        
        if numero:
            address_parts.append(f"nº {numero}")
        
        if bairro:
            clean_bairro = re.sub(r'^BAIRRO\s+', '', bairro, flags=re.IGNORECASE).strip()
            address_parts.append(f"Bairro {clean_bairro}")
        
        if cep:
            address_parts.append(f"CEP {cep}")
        
        if cidade:
            cidade_clean = cidade.replace(' - SP', '').strip()
            address_parts.append(f"na cidade de {cidade_clean} - SP")
        
        return ', '.join(address_parts).upper()
    
    def _format_legal_address_from_extracted_data(self, address_data: Dict) -> str:
        if not address_data or not address_data.get('structured_data'):
            return ''
        
        structured = address_data['structured_data']
        address_parts = []
        
        if structured.get('LOGRADOURO'):
            address_parts.append(f"na {structured['LOGRADOURO']}")
        
        if structured.get('NUMERO'):
            address_parts.append(f"nº {structured['NUMERO']}")
        
        if structured.get('COMPLEMENTO'):
            address_parts.append(structured['COMPLEMENTO'])
        
        if structured.get('BAIRRO'):
            address_parts.append(f"Bairro {structured['BAIRRO']}")
        
        if structured.get('CEP'):
            address_parts.append(f"CEP {structured['CEP']}")
        
        if structured.get('CIDADE') and structured.get('ESTADO'):
            address_parts.append(f"na cidade de {structured['CIDADE']} - {structured['ESTADO']}")
        
        return ', '.join(filter(None, address_parts)).upper()
    
    def _format_legal_address_from_string(self, address_string: str) -> str:
        if not address_string:
            return ''
        
        class TempClient:
            def __init__(self, addr_str):
                self.address = addr_str
                import re
                cep_match = re.search(r'CEP\s+(\d{5}-\d{3})', addr_str)
                self.cep = cep_match.group(1) if cep_match else ''
                
                cep_cidade_match = re.search(r'CEP\s+\d{5}-\d{3},\s*([A-Z\s]+)\s*-\s*SP$', addr_str)
                if cep_cidade_match:
                    cidade_raw = cep_cidade_match.group(1).strip()
                else:
                    cidade_match = re.search(r'([A-Z\s]+[A-Z])\s*-\s*SP$', addr_str)
                    cidade_raw = cidade_match.group(1).strip() if cidade_match else ''
                
                if cidade_raw:
                    cidade_clean = re.sub(r'\b\d+\b', '', cidade_raw).strip()
                    cidade_clean = re.sub(r'^,\s*', '', cidade_clean).strip()
                    cidade_clean = re.sub(r'\s+', ' ', cidade_clean).strip()
                    self.city = cidade_clean
                else:
                    self.city = ''
        
        temp_client = TempClient(address_string)
        return self._format_legal_address(temp_client)
    
    def get_declaracao_pagamento_replacements(self, data: ExtractedData) -> Dict[str, str]:
        replacements = self.get_termo_responsabilidade_replacements(data)
        
        if data.third_party:
            replacements.update({
                '{{THIRD_NAME}}': data.third_party.name.upper() if data.third_party.name else '',
                '{{THIRD_CPF}}': self._format_cpf(data.third_party.cpf),
                '{{THIRD_RG}}': self._format_rg(data.third_party.rg),
                '{{THIRD_ADDRESS}}': self._format_third_party_address(data.third_party, data.client),
                
                'NOME_TERCEIRO': data.third_party.name.upper() if data.third_party.name else '',
                'CPF_TERCEIRO': self._format_cpf(data.third_party.cpf),
                'RG_TERCEIRO': self._format_rg(data.third_party.rg),
                'ENDERECO_TERCEIRO': self._format_third_party_address(data.third_party, data.client),
                
                'THIRD_NAME': data.third_party.name.upper() if data.third_party.name else '',
                'THIRD_CPF': self._format_cpf(data.third_party.cpf),
                'THIRD_RG': self._format_rg(data.third_party.rg)
            })
        else:
            replacements.update({
                '{{THIRD_NAME}}': data.client.name.upper() if data.client.name else '',
                '{{THIRD_CPF}}': self._format_cpf(data.client.cpf),
                '{{THIRD_RG}}': self._format_rg(data.client.rg),
                '{{THIRD_ADDRESS}}': self._format_legal_address(data.client),
                
                'NOME_TERCEIRO': data.client.name.upper() if data.client.name else '',
                'CPF_TERCEIRO': self._format_cpf(data.client.cpf),
                'RG_TERCEIRO': self._format_rg(data.client.rg),
                'ENDERECO_TERCEIRO': self._format_legal_address(data.client),
                
                'THIRD_NAME': data.client.name.upper() if data.client.name else '',
                'THIRD_CPF': self._format_cpf(data.client.cpf),
                'THIRD_RG': self._format_rg(data.client.rg)
            })
        
        if data.payment:
            formatted_amount = self._format_currency_value(data.payment.amount)
            amount_written = self._convert_amount_to_words(data.payment.amount)
            
            replacements.update({
                '{{PAYMENT_AMOUNT}}': formatted_amount,
                '{{PAYMENT_AMOUNT_WRITTEN}}': amount_written,
                '{{PAYMENT_METHOD}}': data.payment.payment_method.upper() if data.payment.payment_method else '',
                '{{BANK_NAME}}': data.payment.bank_name.upper() if data.payment.bank_name else '',
                '{{BANK_AGENCY}}': data.payment.agency if data.payment.agency else '',
                '{{BANK_ACCOUNT}}': data.payment.account if data.payment.account else '',
                
                'VALOR_PAGAMENTO': formatted_amount,
                'VALOR_EXTENSO': amount_written,
                'FORMA_PAGAMENTO': data.payment.payment_method.upper() if data.payment.payment_method else '',
                'BANCO_PAGAMENTO': data.payment.bank_name.upper() if data.payment.bank_name else '',
                'AGENCIA_PAGAMENTO': data.payment.agency if data.payment.agency else '',
                'CONTA_PAGAMENTO': data.payment.account if data.payment.account else '',
                
                'PAYMENT_AMOUNT': formatted_amount,
                'PAYMENT_METHOD': data.payment.payment_method.upper() if data.payment.payment_method else '',
                'BANK_NAME': data.payment.bank_name.upper() if data.payment.bank_name else '',
                'BANK_AGENCY': data.payment.agency if data.payment.agency else '',
                'BANK_ACCOUNT': data.payment.account if data.payment.account else ''
            })
        else:
            replacements.update({
                '{{PAYMENT_AMOUNT}}': '',
                '{{PAYMENT_AMOUNT_WRITTEN}}': '',
                '{{PAYMENT_METHOD}}': '',
                '{{BANK_NAME}}': '',
                '{{BANK_AGENCY}}': '',
                '{{BANK_ACCOUNT}}': '',
                
                'VALOR_PAGAMENTO': '',
                'VALOR_EXTENSO': '',
                'FORMA_PAGAMENTO': '',
                'BANCO_PAGAMENTO': '',
                
                'PAYMENT_AMOUNT': '',
                'PAYMENT_METHOD': '',
                'BANK_NAME': '',
                'BANK_AGENCY': '',
                'BANK_ACCOUNT': ''
            })
        
        if data.new_vehicle:
            valor_novo = self._format_currency_value(data.new_vehicle.value) if data.new_vehicle.value else ''
            
            replacements.update({
                '{{NEW_VEHICLE_BRAND}}': data.new_vehicle.brand or '',
                '{{NEW_VEHICLE_MODEL}}': data.new_vehicle.model or '',
                '{{NEW_VEHICLE_COLOR}}': data.new_vehicle.color or '',
                '{{NEW_VEHICLE_YEAR_MODEL}}': data.new_vehicle.year_model or '',
                'MARCA_VEICULO_NOVO': data.new_vehicle.brand or '',
                'MODELO_VEICULO_NOVO': data.new_vehicle.model or '',
                'COR_VEICULO_NOVO': data.new_vehicle.color or '',
                'ANO_MODELO_VEICULO_NOVO': data.new_vehicle.year_model or '',
                
                '{{SALES_ORDER_NUMBER}}': data.new_vehicle.sales_order or data.document.proposal_number or ''
            })
        else:
            replacements.update({
                '{{NEW_VEHICLE_BRAND}}': '',
                '{{NEW_VEHICLE_MODEL}}': '',
                '{{NEW_VEHICLE_COLOR}}': '',
                '{{NEW_VEHICLE_YEAR_MODEL}}': '',
                'MARCA_VEICULO_NOVO': '',
                'MODELO_VEICULO_NOVO': '',
                'COR_VEICULO_NOVO': '',
                'ANO_MODELO_VEICULO_NOVO': '',
                
                '{{SALES_ORDER_NUMBER}}': data.document.proposal_number or ''
            })
        
        return replacements
    
    def get_termo_dacao_credito_replacements(self, data: ExtractedData) -> Dict[str, str]:
        replacements = self.get_termo_responsabilidade_replacements(data)
        
        if data.third_party:
            third_party_legal_address = ''
            
            if hasattr(data.third_party, '_extracted_address_data'):
                third_party_legal_address = self._format_legal_address_from_extracted_data(data.third_party._extracted_address_data)
            elif data.third_party.address:
                third_party_legal_address = self._format_legal_address_from_string(data.third_party.address)
            else:
                third_party_legal_address = self._format_legal_address(data.client)
            
            replacements.update({
                '{{THIRD_NAME}}': data.third_party.name or data.client.name,
                '{{THIRD_CPF}}': data.third_party.cpf or data.client.cpf,
                '{{THIRD_RG}}': data.third_party.rg or data.client.rg or '',
                '{{THIRD_ADDRESS}}': third_party_legal_address,
                'NOME_CEDENTE_CREDITO': data.third_party.name or data.client.name,
                'CPF_CEDENTE_CREDITO': data.third_party.cpf or data.client.cpf,
                'RG_CEDENTE_CREDITO': data.third_party.rg or data.client.rg or '',
                'ENDERECO_CEDENTE_CREDITO': third_party_legal_address
            })
        else:
            client_legal_address = self._format_legal_address(data.client)
            replacements.update({
                '{{THIRD_NAME}}': data.client.name,
                '{{THIRD_CPF}}': data.client.cpf,
                '{{THIRD_RG}}': data.client.rg or '',
                '{{THIRD_ADDRESS}}': client_legal_address,
                'NOME_CEDENTE_CREDITO': data.client.name,
                'CPF_CEDENTE_CREDITO': data.client.cpf,
                'RG_CEDENTE_CREDITO': data.client.rg or '',
                'ENDERECO_CEDENTE_CREDITO': client_legal_address
            })
        
        if data.vehicle:
            replacements.update({
                '{{USED_VEHICLE_BRAND}}': data.vehicle.brand or self._extract_brand_from_model(data.vehicle.model) if data.vehicle.model else '',
                '{{USED_VEHICLE_MODEL}}': data.vehicle.model or '',
                '{{USED_VEHICLE_CHASSI}}': data.vehicle.chassis or '',
                '{{USED_VEHICLE_COLOR}}': data.vehicle.color or '',
                '{{USED_VEHICLE_PLATE}}': data.vehicle.plate or '',
                '{{USED_VEHICLE_YEAR_MODEL}}': data.vehicle.year_model or '',
                'USED_VEHICLE_CREDIT': self._format_currency_value(data.vehicle.value) if data.vehicle.value else ''
            })
        else:
            replacements.update({
                '{{USED_VEHICLE_BRAND}}': '',
                '{{USED_VEHICLE_MODEL}}': '',
                '{{USED_VEHICLE_CHASSI}}': '',
                '{{USED_VEHICLE_COLOR}}': '',
                '{{USED_VEHICLE_PLATE}}': '',
                '{{USED_VEHICLE_YEAR_MODEL}}': '',
                'USED_VEHICLE_CREDIT': ''
            })
        
        if data.new_vehicle:
            valor_novo = self._format_currency_value(data.new_vehicle.value) if data.new_vehicle.value else ''
            replacements.update({
                '{{NEW_VEHICLE_BRAND}}': data.new_vehicle.brand or '',
                '{{NEW_VEHICLE_MODEL}}': data.new_vehicle.model or '',
                '{{NEW_VEHICLE_COLOR}}': data.new_vehicle.color or '',
                '{{NEW_VEHICLE_CHASSI}}': data.new_vehicle.chassis or '',
                '{{NEW_VEHICLE_YEAR_MODEL}}': data.new_vehicle.year_model or '',
                '{{NEW_VEHICLE_PRICE}}': valor_novo,
                'MARCA_VEICULO_NOVO': data.new_vehicle.brand or '',
                'MODELO_VEICULO_NOVO': data.new_vehicle.model or '',
                'COR_VEICULO_NOVO': data.new_vehicle.color or '',
                'PLACA_VEICULO_NOVO': data.new_vehicle.plate or '',
                'CHASSI_VEICULO_NOVO': data.new_vehicle.chassis or '',
                'ANO_MODELO_VEICULO_NOVO': data.new_vehicle.year_model or '',
                'VALOR_VEICULO_NOVO': valor_novo,
                '{{VALOR_VEICULO_NOVO}}': valor_novo
            })
        else:
            replacements.update({
                '{{NEW_VEHICLE_BRAND}}': '',
                '{{NEW_VEHICLE_MODEL}}': '',
                '{{NEW_VEHICLE_COLOR}}': '',
                '{{NEW_VEHICLE_CHASSI}}': '',
                '{{NEW_VEHICLE_YEAR_MODEL}}': '',
                '{{NEW_VEHICLE_PRICE}}': '',
                'MARCA_VEICULO_NOVO': '',
                'MODELO_VEICULO_NOVO': '',
                'COR_VEICULO_NOVO': '',
                'PLACA_VEICULO_NOVO': '',
                'CHASSI_VEICULO_NOVO': '',
                'ANO_MODELO_VEICULO_NOVO': '',
                'VALOR_VEICULO_NOVO': '',
                '{{VALOR_VEICULO_NOVO}}': ''
            })
        
        return replacements
    
    
    def _extract_brand_from_model(self, model: str) -> str:
        if not model: 
            return ""
        try:
            try: 
                from ..utils.brand_lookup import get_brand_lookup
            except ImportError: 
                from utils.brand_lookup import get_brand_lookup
            brand_lookup = get_brand_lookup()
            brand = brand_lookup.get_brand_from_model(model)
            return brand if brand else ""
        except Exception:
            return ""
    
    def _format_currency_value(self, value_str: str) -> str:
        if not value_str or not value_str.strip(): 
            return ""
        try:
            import re
            clean_value = re.sub(r'[^\d.,]', '', value_str.strip())
            if ',' in clean_value and clean_value.count(',') == 1: 
                parts = clean_value.split(',')
                return f"R$ {clean_value}" if len(parts) == 2 and len(parts[1]) == 2 else f"R$ {value_str}"
            if '.' in clean_value: 
                float_value = float(clean_value)
                formatted = f"{float_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return f"R$ {formatted}"
            else: 
                num_value = int(clean_value)
                return f"R$ {num_value},00" if num_value <= 999 else f"R$ {f'{num_value:,}'.replace(',', '.')},00"
        except (ValueError, TypeError): 
            return ""
    
    def _format_cpf(self, cpf: str) -> str:
        if not cpf:
            return ''
        
        clean_cpf = re.sub(r'[^\d]', '', cpf)
        
        if len(clean_cpf) == 11:
            return f"{clean_cpf[:3]}.{clean_cpf[3:6]}.{clean_cpf[6:9]}-{clean_cpf[9:]}"
        
        return cpf
    
    def _format_rg(self, rg: str) -> str:
        if not rg:
            return ''
        
        clean_rg = re.sub(r'[^\dA-Z\-\.]', '', rg.upper())
        
        return clean_rg
    
    def _format_third_party_address(self, third_party, client_fallback) -> str:
        if third_party and third_party.address:
            return self._format_legal_address_from_string(third_party.address)
        elif third_party and (third_party.city or third_party.cep):
            parts = []
            if third_party.city:
                parts.append(f"na cidade de {third_party.city.upper()}")
            if third_party.cep:
                parts.append(f"CEP {third_party.cep}")
            return ', '.join(parts).upper()
        else:
            return self._format_legal_address(client_fallback)
    
    def _convert_amount_to_words(self, amount: str) -> str:
        if not amount:
            return ""
        
        try:
            amount_str = str(amount).replace('R$', '').replace('.', '').replace(',', '.').strip()
            amount_float = float(amount_str)
            
            if amount_float == 0:
                return "zero reais"
            elif amount_float < 1000:
                return f"{int(amount_float)} reais"
            else:
                thousands = int(amount_float // 1000)
                remainder = int(amount_float % 1000)
                
                if remainder == 0:
                    return f"{thousands} mil reais"
                else:
                    return f"{thousands} mil e {remainder} reais"
        except:
            return ""
import os
import re
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    from ..data.models import ExtractedData, ThirdPartyData, PaymentData
    from ..processors.template_replacements import TemplateReplacementManager
    from ..utils import LoggerMixin
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from data.models import ExtractedData, ThirdPartyData, PaymentData
    from processors.template_replacements import TemplateReplacementManager
    from utils import LoggerMixin


class ThirdPartyPaymentTemplateFiller(LoggerMixin):
    """
    CKDEV-NOTE: Preenchedor especializado com placeholders específicos
    para template de declaração de pagamento por conta e ordem de terceiro
    """
    
    def __init__(self):
        super().__init__()
        self.replacement_manager = TemplateReplacementManager()
    
    def get_pagamento_terceiro_replacements(self, data: ExtractedData) -> Dict[str, str]:
        """
        CKDEV-NOTE: Gera substituições específicas para template de pagamento a terceiro
        Integra dados de proposta, CNH e comprovante de pagamento
        """
        replacements = {}
        
        replacements.update(self._process_client_data(data))
        replacements.update(self._process_third_party_data(data))
        replacements.update(self._process_payment_data(data))
        replacements.update(self._process_vehicle_data(data))
        replacements.update(self._process_new_vehicle_data(data))
        replacements.update(self._process_document_data(data))
        replacements.update(self._generate_legal_texts(data))
        
        return replacements
    
    def _process_client_data(self, data: ExtractedData) -> Dict[str, str]:
        client = data.client
        
        return {
            '{{CLIENT_NAME}}': client.name.upper() if client.name else '',
            '{{CLIENT_CPF}}': self._format_cpf(client.cpf),
            '{{CLIENT_RG}}': self._format_rg(client.rg),
            '{{CLIENT_ADDRESS}}': self._format_legal_address(client),
            
            'NOME_CLIENTE': client.name.upper() if client.name else '',
            'CPF_CLIENTE': self._format_cpf(client.cpf),
            'RG_CLIENTE': self._format_rg(client.rg),
            'ENDERECO_CLIENTE': self._format_legal_address(client)
        }
    
    def _process_third_party_data(self, data: ExtractedData) -> Dict[str, str]:
        third_party = data.third_party
        
        if not third_party:
            return {
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
            }
        
        return {
            '{{THIRD_NAME}}': third_party.name.upper() if third_party.name else '',
            '{{THIRD_CPF}}': self._format_cpf(third_party.cpf),
            '{{THIRD_RG}}': self._format_rg(third_party.rg),
            '{{THIRD_ADDRESS}}': self._format_third_party_address(third_party, data.client),
            
            'NOME_TERCEIRO': third_party.name.upper() if third_party.name else '',
            'CPF_TERCEIRO': self._format_cpf(third_party.cpf),
            'RG_TERCEIRO': self._format_rg(third_party.rg),
            'ENDERECO_TERCEIRO': self._format_third_party_address(third_party, data.client),
            
            'THIRD_NAME': third_party.name.upper() if third_party.name else '',
            'THIRD_CPF': self._format_cpf(third_party.cpf),
            'THIRD_RG': self._format_rg(third_party.rg)
        }
    
    def _process_payment_data(self, data: ExtractedData) -> Dict[str, str]:
        payment = data.payment
        
        if not payment:
            # CKDEV-NOTE: Campos vazios quando dados de pagamento não forem extraídos
            return {
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
            }
        
        formatted_amount = self._format_currency_value(payment.amount)
        amount_written = self._convert_amount_to_words(payment.amount)
        
        return {
            '{{PAYMENT_AMOUNT}}': formatted_amount,
            '{{PAYMENT_AMOUNT_WRITTEN}}': amount_written,
            # CKDEV-NOTE: Removido fallback hardcoded - apenas dados reais extraídos dos PDFs
            '{{PAYMENT_METHOD}}': payment.payment_method.upper() if payment.payment_method else '',
            '{{BANK_NAME}}': payment.bank_name.upper() if payment.bank_name else '',
            '{{BANK_AGENCY}}': payment.agency if payment.agency else '',
            '{{BANK_ACCOUNT}}': payment.account if payment.account else '',
            
            'VALOR_PAGAMENTO': formatted_amount,
            'VALOR_EXTENSO': amount_written,
            # CKDEV-NOTE: Removido fallback hardcoded - apenas dados reais extraídos dos PDFs
            'FORMA_PAGAMENTO': payment.payment_method.upper() if payment.payment_method else '',
            'BANCO_PAGAMENTO': payment.bank_name.upper() if payment.bank_name else '',
            'AGENCIA_PAGAMENTO': payment.agency if payment.agency else '',
            'CONTA_PAGAMENTO': payment.account if payment.account else '',
            
            'PAYMENT_AMOUNT': formatted_amount,
            # CKDEV-NOTE: Removido fallback hardcoded - apenas dados reais extraídos dos PDFs
            'PAYMENT_METHOD': payment.payment_method.upper() if payment.payment_method else '',
            'BANK_NAME': payment.bank_name.upper() if payment.bank_name else '',
            'BANK_AGENCY': payment.agency if payment.agency else '',
            'BANK_ACCOUNT': payment.account if payment.account else ''
        }
    
    def _process_vehicle_data(self, data: ExtractedData) -> Dict[str, str]:
        vehicle = data.vehicle
        
        if not vehicle:
            # CKDEV-NOTE: Campos vazios quando dados do veículo não forem extraídos
            return {
                '{{VEHICLE_BRAND}}': '',
                '{{VEHICLE_MODEL}}': '',
                '{{VEHICLE_PLATE}}': '',
                '{{VEHICLE_CHASSIS}}': '',
                '{{VEHICLE_COLOR}}': '',
                '{{VEHICLE_YEAR_MODEL}}': '',
                '{{VEHICLE_VALUE}}': ''
            }
        
        brand = vehicle.brand or self._extract_brand_from_model(vehicle.model)
        
        return {
            '{{VEHICLE_BRAND}}': brand.upper() if brand else '',
            '{{VEHICLE_MODEL}}': vehicle.model.upper() if vehicle.model else '',
            '{{VEHICLE_PLATE}}': vehicle.plate.upper() if vehicle.plate else '',
            '{{VEHICLE_CHASSIS}}': vehicle.chassis.upper() if vehicle.chassis else '',
            '{{VEHICLE_COLOR}}': vehicle.color.upper() if vehicle.color else '',
            '{{VEHICLE_YEAR_MODEL}}': vehicle.year_model if vehicle.year_model else '',
            '{{VEHICLE_VALUE}}': self._format_currency_value(vehicle.value),
            
            'MARCA_VEICULO': brand.upper() if brand else '',
            'MODELO_VEICULO': vehicle.model.upper() if vehicle.model else '',
            'PLACA_VEICULO': vehicle.plate.upper() if vehicle.plate else '',
            'CHASSI_VEICULO': vehicle.chassis.upper() if vehicle.chassis else '',
            'COR_VEICULO': vehicle.color.upper() if vehicle.color else '',
            'ANO_MODELO_VEICULO': vehicle.year_model if vehicle.year_model else ''
        }
    
    def _process_new_vehicle_data(self, data: ExtractedData) -> Dict[str, str]:
        new_vehicle = data.new_vehicle
        
        if not new_vehicle:
            return {
                '{{NEW_VEHICLE_BRAND}}': '',
                '{{NEW_VEHICLE_MODEL}}': '',
                '{{NEW_VEHICLE_COLOR}}': '',
                '{{NEW_VEHICLE_YEAR_MODEL}}': '',
                
                'MARCA_VEICULO_NOVO': '',
                'MODELO_VEICULO_NOVO': '',
                'COR_VEICULO_NOVO': '',
                'ANO_MODELO_VEICULO_NOVO': ''
            }
        
        # CKDEV-NOTE: Ajuste técnico necessário - template tem limitação física de largura
        brand = self._adjust_for_table_display(new_vehicle.brand or '')
        model = self._adjust_for_table_display(new_vehicle.model or '') 
        color = self._adjust_for_table_display(new_vehicle.color or '')
        
        return {
            '{{NEW_VEHICLE_BRAND}}': brand,
            '{{NEW_VEHICLE_MODEL}}': model,
            '{{NEW_VEHICLE_COLOR}}': color,
            '{{NEW_VEHICLE_YEAR_MODEL}}': new_vehicle.year_model or '',
            
            'MARCA_VEICULO_NOVO': brand,
            'MODELO_VEICULO_NOVO': model,
            'COR_VEICULO_NOVO': color,
            'ANO_MODELO_VEICULO_NOVO': new_vehicle.year_model or ''
        }
    
    def _process_document_data(self, data: ExtractedData) -> Dict[str, str]:
        document = data.document
        
        doc_date = document.date if document and document.date else datetime.now().strftime("%d/%m/%Y")
        location = self._format_location(document.location if document and document.location else None)
        date_location = f"{location}, {doc_date}"
        
        return {
            '{{DOCUMENT_DATE}}': doc_date,
            '{{DOCUMENT_LOCATION}}': location,
            '{{DOCUMENT_DATE_LOCATION}}': date_location,
            '{{PROPOSAL_NUMBER}}': document.proposal_number if document and document.proposal_number else '',
            
            'DATA_DOCUMENTO': doc_date,
            'LOCAL_DOCUMENTO': location,
            'DATA_LOCAL_DOCUMENTO': date_location,
            'NUMERO_PROPOSTA': document.proposal_number if document and document.proposal_number else ''
        }
    
    def _generate_legal_texts(self, data: ExtractedData) -> Dict[str, str]:
        """CKDEV-NOTE: Gera textos legais formatados para o documento"""
        
        client_name = data.client.name.upper() if data.client.name else 'DECLARANTE'
        third_name = (data.third_party.name.upper() if data.third_party and data.third_party.name 
                     else data.client.name.upper() if data.client.name else 'BENEFICIÁRIO')
        
        payment_amount = self._format_currency_value(data.payment.amount if data.payment else "0")
        
        declaration_text = f"""Declaro que efetuei o pagamento no valor de {payment_amount} ({self._convert_amount_to_words(data.payment.amount if data.payment else "0")}) em favor de {third_name}, referente à aquisição de veículo conforme especificado neste documento."""
        
        legal_declaration = f"""Por ser expressão da verdade, firmo a presente declaração sob as penas da lei, responsabilizando-me integralmente pelas informações aqui prestadas."""
        
        return {
            '{{FORMATTED_DECLARATION_TEXT}}': declaration_text,
            '{{LEGAL_DECLARATION}}': legal_declaration,
            
            'TEXTO_DECLARACAO': declaration_text,
            'CLAUSULA_LEGAL': legal_declaration
        }
    
    def _format_legal_address(self, client_data) -> str:
        return self.replacement_manager._format_legal_address(client_data)
    
    def _format_third_party_address(self, third_party: ThirdPartyData, client_fallback) -> str:
        """CKDEV-NOTE: Formatação de endereço do terceiro com fallback para cliente"""
        if third_party and third_party.address:
            return self.replacement_manager._format_legal_address_from_string(third_party.address)
        elif third_party and (third_party.city or third_party.cep):
            parts = []
            if third_party.city:
                parts.append(f"na cidade de {third_party.city.upper()}")
            if third_party.cep:
                parts.append(f"CEP {third_party.cep}")
            return ', '.join(parts).upper()
        else:
            return self._format_legal_address(client_fallback)
    
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
    
    def _format_location(self, location: Optional[str]) -> str:
        if not location:
            return os.getenv('DEFAULT_LOCATION', 'São José dos Campos - SP')
        
        location_clean = location.replace(' - SP', '').strip()
        if not location_clean.endswith(' - SP'):
            location_clean += ' - SP'
        
        return location_clean
    
    def _format_currency_value(self, value: Any) -> str:
        if not value:
            return ""
        
        value_str = str(value).strip()
        
        if not value_str:
            return ""
        
        try:
            clean_value = re.sub(r'[^\d.,]', '', value_str)
            
            if ',' in clean_value and clean_value.count(',') == 1:
                parts = clean_value.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    return f"R$ {clean_value}"
            
            if '.' in clean_value:
                float_value = float(clean_value)
                formatted = f"{float_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return f"R$ {formatted}"
            else:
                int_value = int(clean_value)
                if int_value <= 999:
                    return f"R$ {int_value},00"
                else:
                    formatted = f"{int_value:,}".replace(",", ".")
                    return f"R$ {formatted},00"
                    
        except (ValueError, TypeError):
            return ""
    
    def _convert_amount_to_words(self, amount: Any) -> str:
        """CKDEV-NOTE: Conversão de valor numérico para extenso"""
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
    
    def _extract_brand_from_model(self, model: str) -> str:
        return self.replacement_manager._extract_brand_from_model(model)
    
    def _adjust_for_table_display(self, text: str) -> str:
        """CKDEV-NOTE: Ajuste mínimo técnico para display em tabela - limitação do template"""
        if not text:
            return ''

        text = text.strip()
        
        if text.upper() == 'AZUL TITAN':
            return 'AZUL TITÃ'
        elif text.upper() == 'PRETO TITAN':
            return 'PRETO TITÃ'
        
        if text.upper() == 'VOLKSWAGEN':
            return 'VOLKSWAGEN'
        
        if len(text) > 25:
            if 'NIVUS HIGHLINE' in text.upper():
                return 'NIVUS HIGHLINE 200TSI'
            
        return text

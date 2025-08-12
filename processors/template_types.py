import os
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class TemplateType(Enum):
    RESPONSABILIDADE_VEICULO = "responsabilidade_veiculo"
    PAGAMENTO_TERCEIRO = "pagamento_terceiro"
    CESSAO_CREDITO = "cessao_credito"

@dataclass
class TemplateConfig:
    name: str
    file_path: str
    description: str
    required_data: List[str]

class TemplateManager:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        self.templates = self._initialize_templates()
        self._validate_templates()
    
    def _initialize_templates(self) -> Dict[TemplateType, TemplateConfig]:
        # CKDEV-NOTE: Lógica de mapeamento entre tipos e configurações de template - configurável via variáveis de ambiente
        return {
            TemplateType.RESPONSABILIDADE_VEICULO: TemplateConfig(
                name=os.getenv('TEMPLATE_RESPONSABILIDADE_NAME', 'Termo de Responsabilidade - Veículos Usados'),
                file_path=f"{self.templates_dir}/{os.getenv('TEMPLATE_RESPONSABILIDADE_FILE', 'template3_responsabilidade_veiculo.docx')}",
                description=os.getenv('TEMPLATE_RESPONSABILIDADE_DESCRIPTION', 'Termo de responsabilidade sobre veículo usado na troca'),
                required_data=["client", "vehicle", "document"]
            ),
            TemplateType.PAGAMENTO_TERCEIRO: TemplateConfig(
                name=os.getenv('TEMPLATE_PAGAMENTO_NAME', 'Declaração de Pagamento por Conta e Ordem de Terceiro'),
                file_path=f"{self.templates_dir}/{os.getenv('TEMPLATE_PAGAMENTO_FILE', 'template1_pagamento_terceiro.docx')}",
                description=os.getenv('TEMPLATE_PAGAMENTO_DESCRIPTION', 'Declaração de pagamento realizado em favor de terceiro'),
                required_data=["client", "payment", "new_vehicle", "document"]
            ),
            TemplateType.CESSAO_CREDITO: TemplateConfig(
                name=os.getenv('TEMPLATE_CESSAO_CREDITO_NAME', 'Termo de Cessão de Crédito em Favor de Terceiros'),
                file_path=f"{self.templates_dir}/{os.getenv('TEMPLATE_CESSAO_CREDITO_FILE', 'template2_cessao_credito.docx')}",
                description=os.getenv('TEMPLATE_CESSAO_CREDITO_DESCRIPTION', 'Termo de transferência de crédito entre partes'),
                required_data=["client", "vehicle", "new_vehicle", "document"]
            )
        }
    
    def get_template_config(self, template_type: TemplateType) -> TemplateConfig:
        # CKDEV-NOTE: Search by value to handle different enum instances from serialization
        for key, config in self.templates.items():
            if key.value == template_type.value:
                return config
        raise KeyError(f"Template type not found: {template_type}")
    
    def get_available_templates(self) -> Dict[str, TemplateConfig]:
        return {template.name: template for template in self.templates.values()}
    
    def get_template_by_name(self, name: str) -> TemplateType:
        for template_type, config in self.templates.items():
            if config.name == name:
                return template_type
        raise ValueError(f"Template não encontrado: {name}")
    
    def _validate_templates(self):
        import os
        missing_files = [
            f"{template_type.value}: {config.file_path}" 
            for template_type, config in self.templates.items() 
            if not os.path.exists(config.file_path)
        ]
        if missing_files:
            raise FileNotFoundError(f"Templates não encontrados:\n{''.join(missing_files)}")
    
    def get_templates_status(self) -> Dict[str, bool]:
        import os
        return {config.name: os.path.exists(config.file_path) for config in self.templates.values()}
import csv
import os
import sys
import re
from pathlib import Path
from typing import Dict, Optional

class BrandLookup:
    
    def __init__(self, csv_path: Optional[str] = None):
        if csv_path is None:
            base_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(__file__).parent.parent
            
            csv_filename = os.getenv('BRAND_LOOKUP_CSV_FILENAME', 'tabela_id_marca_modelo.csv')
            csv_subdir = os.getenv('BRAND_LOOKUP_CSV_SUBDIR', 'shared/assets/dic')
            
            if csv_subdir.startswith('/'):
                csv_path = Path(csv_subdir) / csv_filename
            else:
                csv_path = base_dir / csv_subdir / csv_filename
        
        self.csv_path = csv_path
        self.model_to_brand: Dict[str, str] = {}
        self._load_csv()
    
    def _load_csv(self):
        if not os.path.exists(self.csv_path):
            return
        
        try:
            encoding = os.getenv('BRAND_LOOKUP_CSV_ENCODING', 'utf-8-sig')
            delimiter = os.getenv('BRAND_LOOKUP_CSV_DELIMITER', ';')
            
            with open(self.csv_path, 'r', encoding=encoding) as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                
                marca_column = os.getenv('BRAND_LOOKUP_MARCA_COLUMN', 'MARCA')
                modelo_column = os.getenv('BRAND_LOOKUP_MODELO_COLUMN', 'MODELO')
                
                for row in reader:
                    marca = row.get(marca_column, '').strip().upper()
                    modelo = row.get(modelo_column, '').strip().upper()
                    
                    if marca and modelo:
                        self.model_to_brand[modelo] = marca
                        first_word = modelo.split()[0] if modelo.split() else ""
                        if first_word and len(first_word) > 2:
                            self.model_to_brand[first_word] = marca
        except Exception:
            pass
    
    def get_brand_from_model(self, model: str) -> Optional[str]:
        if not model:
            return None
        
        model_clean = self._clean_model(model)
        
        if model_clean in self.model_to_brand:
            return self.model_to_brand[model_clean]
        
        model_variations = [
            model_clean,
            model_clean.replace(' ', '-'),
            model_clean.replace('-', ' '),
        ]
        
        for variation in model_variations:
            if variation in self.model_to_brand:
                return self.model_to_brand[variation]
        
        words = model_clean.split()
        for word in words:
            if len(word) > 2:
                if word in self.model_to_brand:
                    return self.model_to_brand[word]
                if len(word) >= 3:
                    word_with_hyphen = f"{word[:2]}-{word[2:]}" if len(word) > 2 else word
                    if word_with_hyphen in self.model_to_brand:
                        return self.model_to_brand[word_with_hyphen]
        
        for csv_model, brand in self.model_to_brand.items():
            if model_clean.startswith(csv_model) or csv_model.startswith(model_clean[:10]):
                return brand
            for word in words:
                if len(word) >= 3 and (csv_model.startswith(word) or word.startswith(csv_model)):
                    return brand
        
        for csv_model, brand in self.model_to_brand.items():
            if '-' in csv_model:
                csv_parts = csv_model.split('-')
                model_parts = model_clean.replace('-', ' ').split()
                if len(csv_parts) == 2 and len(model_parts) >= 2:
                    if (csv_parts[0] in model_parts and csv_parts[1] in model_parts):
                        return brand
            
            for word in words:
                if len(word) > 3 and word in csv_model:
                    return brand
        
        return None
    
    def _clean_model(self, model: str) -> str:
        if not model:
            return ""
        
        model_upper = model.upper()
        
        clean_regex = os.getenv('BRAND_LOOKUP_CLEAN_REGEX', r'[^\w\s\-]')
        cleaned = re.sub(clean_regex, ' ', model_upper)
        
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def get_fallback_brand(self, model: str) -> str:
        return self.get_brand_from_model(model) or ""

_brand_lookup_instance = None

def get_brand_lookup() -> BrandLookup:
    global _brand_lookup_instance
    if _brand_lookup_instance is None:
        _brand_lookup_instance = BrandLookup()
    return _brand_lookup_instance
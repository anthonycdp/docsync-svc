#!/usr/bin/env python3
"""Test script to verify PDF conversion is working"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_root))

from api.config import get_config
from api.services.pdf_conversion_service import PDFConversionService

def test_pdf_conversion():
    print("Testing PDF conversion...")
    
    # Check if test DOCX exists
    output_dir = Path("backend/shared/output")
    docx_files = list(output_dir.glob("*.docx"))
    
    print(f"Found DOCX files: {[f.name for f in docx_files]}")
    
    if not docx_files:
        print("No DOCX files found to test!")
        return
    
    # Test with first DOCX file
    test_docx = docx_files[0]
    print(f"Testing conversion with: {test_docx}")
    
    # Initialize PDF service
    try:
        config = get_config()
        pdf_service = PDFConversionService(config)
        print("PDF service initialized successfully")
    except Exception as e:
        print(f"Failed to initialize PDF service: {e}")
        return
    
    # Try conversion
    try:
        result_path = pdf_service.convert_docx_to_pdf(test_docx)
        
        if result_path and result_path.exists():
            file_size = result_path.stat().st_size
            print(f"SUCCESS: PDF created at {result_path} ({file_size} bytes)")
            
            # Test if file is accessible
            with open(result_path, 'rb') as f:
                header = f.read(4)
                if header.startswith(b'%PDF'):
                    print("PDF header validation: PASSED")
                else:
                    print(f"PDF header validation: FAILED (header: {header})")
        else:
            print("FAILED: No PDF file created")
            
    except Exception as e:
        print(f"Conversion failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_conversion()
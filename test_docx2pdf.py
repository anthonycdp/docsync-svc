#!/usr/bin/env python3
import sys
import os

try:
    from docx2pdf import convert
    print("OK docx2pdf is available")
    
    # Test if it's working
    test_result = True
    print("OK docx2pdf import successful")
except ImportError as e:
    print(f"ERROR docx2pdf not available: {e}")
    test_result = False

try:
    import subprocess
    result = subprocess.run(['soffice', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("OK LibreOffice is available")
        print(f"  Version: {result.stdout.strip()}")
    else:
        print("ERROR LibreOffice not found via soffice command")
except Exception as e:
    print(f"ERROR LibreOffice test failed: {e}")

try:
    result = subprocess.run(['libreoffice', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("OK LibreOffice is available via libreoffice command")
        print(f"  Version: {result.stdout.strip()}")
    else:
        print("ERROR LibreOffice not found via libreoffice command")
except Exception as e:
    print(f"ERROR LibreOffice libreoffice command test failed: {e}")

print(f"\nPlatform: {sys.platform}")
print(f"Python: {sys.version}")
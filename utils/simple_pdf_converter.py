import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import logging

def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system().lower() == 'linux'

def convert_with_libreoffice(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Convert DOCX to PDF using LibreOffice headless mode
    Preserves exact formatting using LibreOffice's rendering engine
    
    Args:
        docx_path: Path to the .docx file
        pdf_path: Output path for PDF (optional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(docx_path):
        return False, f"DOCX file not found: {docx_path}", None
    
    if pdf_path is None:
        pdf_path = str(Path(docx_path).with_suffix('.pdf'))
    
    output_dir = os.path.dirname(pdf_path)
    if not output_dir:
        output_dir = os.path.dirname(docx_path)
    
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        # CKDEV-NOTE: Use unique temp profile to avoid conflicts with running instances
        temp_profile = f"/tmp/LibreOffice_Conversion_{os.getpid()}"
        
        # CKDEV-NOTE: Try different LibreOffice executable locations
        libreoffice_commands = [
            'libreoffice',
            'soffice',
            '/usr/bin/libreoffice',
            '/usr/bin/soffice',
            '/opt/libreoffice/program/soffice'
        ]
        
        cmd_found = None
        for cmd in libreoffice_commands:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    cmd_found = cmd
                    logger.info(f"Found LibreOffice at: {cmd}")
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        if not cmd_found:
            return False, "LibreOffice not found. Install with: apt-get install libreoffice", None
        
        # CKDEV-NOTE: Build conversion command with exact formatting preservation
        cmd = [
            cmd_found,
            '--headless',
            '--invisible',
            '--nologo',
            '--nolockcheck',
            '--nodefault',
            '--norestore',
            f'-env:UserInstallation=file://{temp_profile}',
            '--convert-to', 'pdf:writer_pdf_Export',
            '--outdir', output_dir,
            docx_path
        ]
        
        logger.info(f"Converting {docx_path} to PDF using LibreOffice")
        
        # CKDEV-NOTE: Run conversion with timeout
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # CKDEV-NOTE: LibreOffice outputs to original filename with .pdf extension
            expected_pdf = os.path.join(output_dir, Path(docx_path).stem + '.pdf')
            
            if os.path.exists(expected_pdf):
                # Move to desired location if different
                if expected_pdf != pdf_path:
                    os.rename(expected_pdf, pdf_path)
                
                if os.path.getsize(pdf_path) > 0:
                    logger.info(f"PDF conversion successful: {pdf_path}")
                    return True, "PDF generated successfully with LibreOffice", pdf_path
                else:
                    return False, "LibreOffice generated empty PDF file", None
            else:
                return False, f"LibreOffice conversion completed but PDF not found at {expected_pdf}", None
        else:
            error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
            return False, f"LibreOffice conversion failed: {error_msg}", None
            
    except subprocess.TimeoutExpired:
        return False, "LibreOffice conversion timed out after 60 seconds", None
    except Exception as e:
        logger.error(f"LibreOffice conversion error: {e}")
        return False, f"LibreOffice conversion error: {str(e)}", None
    finally:
        # CKDEV-NOTE: Clean up temporary profile
        if 'temp_profile' in locals():
            try:
                import shutil
                if os.path.exists(temp_profile):
                    shutil.rmtree(temp_profile, ignore_errors=True)
            except:
                pass
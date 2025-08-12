import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import logging


class LibreOfficeConverter:
    """LibreOffice-only PDF converter with high fidelity layout preservation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._timeout = 60  # seconds
    
    def convert_docx_to_pdf(
        self, 
        docx_path: str, 
        pdf_path: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Convert DOCX to PDF using LibreOffice headless mode only.
        
        Args:
            docx_path: Path to the .docx file
            pdf_path: Output path for PDF (optional)
        
        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
        """
        # CKDEV-NOTE: Validate DOCX file exists and is accessible before conversion attempt
        if not self._validate_docx_file(docx_path):
            return False, f"DOCX file not found or not accessible: {docx_path}", None
        
        # CKDEV-NOTE: Generate output path if not provided
        if pdf_path is None:
            pdf_path = str(Path(docx_path).with_suffix('.pdf'))
        
        # CKDEV-NOTE: Ensure output directory exists
        output_dir = os.path.dirname(pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # CKDEV-NOTE: Discover LibreOffice binary path
        soffice_path = self._find_libreoffice_binary()
        if not soffice_path:
            return False, "LibreOffice not found. Install LibreOffice or set LIBREOFFICE_PATH", None
        
        return self._perform_conversion(soffice_path, docx_path, pdf_path, output_dir)
    
    def _validate_docx_file(self, docx_path: str) -> bool:
        """Validate DOCX file is accessible and lock-free"""
        try:
            if not os.path.exists(docx_path):
                return False
            
            if not docx_path.lower().endswith('.docx'):
                return False
            
            # CKDEV-NOTE: Test file accessibility to ensure it's not locked
            with open(docx_path, 'rb') as f:
                f.read(1)
            
            return True
        except (OSError, PermissionError):
            return False
    
    def _find_libreoffice_binary(self) -> Optional[str]:
        """Discover LibreOffice binary path via environment or PATH"""
        # CKDEV-NOTE: Check for explicit LIBREOFFICE_PATH environment variable
        env_path = os.environ.get('LIBREOFFICE_PATH')
        if env_path and self._test_libreoffice_binary(env_path):
            return env_path
        
        # CKDEV-NOTE: Standard binary names and locations
        binary_candidates = [
            'soffice',
            'libreoffice',
            '/usr/bin/soffice',
            '/usr/bin/libreoffice',
            '/opt/libreoffice/program/soffice',
            '/snap/bin/libreoffice'
        ]
        
        for binary in binary_candidates:
            if self._test_libreoffice_binary(binary):
                return binary
        
        return None
    
    def _test_libreoffice_binary(self, binary_path: str) -> bool:
        """Test if binary is valid LibreOffice executable"""
        try:
            result = subprocess.run(
                [binary_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def _perform_conversion(
        self, 
        soffice_path: str, 
        docx_path: str, 
        pdf_path: str, 
        output_dir: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Execute LibreOffice conversion with high fidelity settings"""
        try:
            # CKDEV-NOTE: Create unique temp profile to avoid conflicts
            temp_profile = tempfile.mkdtemp(prefix='libreoffice_')
            
            # CKDEV-NOTE: Build command with exact specifications for fidelity
            cmd = [
                soffice_path,
                '--headless',
                '--norestore',
                '--nolockcheck',
                '--nodefault',
                '--nofirststartwizard',
                f'-env:UserInstallation=file://{temp_profile}',
                '--convert-to', 'pdf:writer_pdf_Export:{"EmbedStandardFonts":true,"ExportFormFields":false}',
                '--outdir', output_dir,
                docx_path
            ]
            
            self.logger.info(f"Converting {docx_path} to PDF using LibreOffice")
            
            # CKDEV-NOTE: Execute with timeout and capture all output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout
            )
            
            return self._validate_conversion_result(result, docx_path, pdf_path, temp_profile)
            
        except subprocess.TimeoutExpired:
            return False, f"LibreOffice conversion timed out after {self._timeout} seconds", None
        except Exception as e:
            self.logger.error(f"LibreOffice conversion error: {e}")
            return False, f"LibreOffice conversion error: {str(e)}", None
    
    def _validate_conversion_result(
        self, 
        result: subprocess.CompletedProcess, 
        docx_path: str, 
        pdf_path: str, 
        temp_profile: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Validate conversion success with comprehensive checks"""
        try:
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
                return False, f"LibreOffice conversion failed: {error_msg}", None
            
            # CKDEV-NOTE: LibreOffice outputs to basename + .pdf in output dir
            expected_pdf = os.path.join(
                os.path.dirname(pdf_path),
                Path(docx_path).stem + '.pdf'
            )
            
            if not os.path.exists(expected_pdf):
                return False, f"LibreOffice completed but PDF not found at {expected_pdf}", None
            
            # CKDEV-NOTE: Move to desired location if different
            if expected_pdf != pdf_path:
                os.rename(expected_pdf, pdf_path)
            
            # CKDEV-NOTE: Validate PDF file integrity
            file_size = os.path.getsize(pdf_path)
            if file_size == 0:
                os.remove(pdf_path)
                return False, "LibreOffice generated empty PDF file", None
            
            if file_size < 100:  # PDFs should be at least 100 bytes
                os.remove(pdf_path)
                return False, f"LibreOffice generated suspiciously small PDF ({file_size} bytes)", None
            
            # CKDEV-NOTE: Validate PDF header
            try:
                with open(pdf_path, 'rb') as f:
                    header = f.read(4)
                    if not header.startswith(b'%PDF'):
                        os.remove(pdf_path)
                        return False, "LibreOffice generated invalid PDF (bad header)", None
            except Exception as header_error:
                self.logger.warning(f"Could not validate PDF header: {header_error}")
            
            self.logger.info(f"LibreOffice conversion successful: {pdf_path} ({file_size} bytes)")
            return True, f"PDF generated successfully ({file_size} bytes)", pdf_path
            
        finally:
            # CKDEV-NOTE: Clean up temporary profile directory
            self._cleanup_temp_profile(temp_profile)
    
    def _cleanup_temp_profile(self, temp_profile: str):
        """Clean up temporary LibreOffice profile directory"""
        try:
            import shutil
            if os.path.exists(temp_profile):
                shutil.rmtree(temp_profile, ignore_errors=True)
        except Exception as e:
            self.logger.warning(f"Could not clean up temp profile {temp_profile}: {e}")


def convert_docx_to_pdf_libreoffice(
    docx_path: str, 
    pdf_path: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Convenience function for LibreOffice-only DOCX to PDF conversion.
    
    Args:
        docx_path: Path to the .docx file
        pdf_path: Output path for PDF (optional)
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success, message, pdf_path)
    """
    converter = LibreOfficeConverter()
    return converter.convert_docx_to_pdf(docx_path, pdf_path)
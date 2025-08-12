import os
import platform
from pathlib import Path
from typing import Tuple, Optional
import logging
import subprocess
import tempfile
import shutil

def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system().lower() == 'linux'

def convert_docx_to_pdf_linux(docx_path: str, pdf_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Convert DOCX to PDF using Linux-compatible methods with exact formatting preservation
    
    This function tries multiple Linux-compatible conversion methods in order:
    1. unoconv (most reliable for preserving formatting)
    2. LibreOffice headless with advanced parameters
    3. pandoc (excellent formatting preservation)
    4. Python-docx + ReportLab (improved fallback)
    
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
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Method 1: Try unoconv (most reliable)
    success, message, result_path = _try_unoconv_conversion(docx_path, pdf_path, logger)
    if success and result_path and _validate_pdf_quality(result_path, docx_path, logger):
        return success, message, result_path
    
    logger.warning(f"unoconv conversion failed or quality check failed: {message}")
    
    # Method 2: Try enhanced LibreOffice conversion
    success, message, result_path = _try_enhanced_libreoffice_conversion(docx_path, pdf_path, logger)
    if success and result_path and _validate_pdf_quality(result_path, docx_path, logger):
        return success, message, result_path
    
    logger.warning(f"Enhanced LibreOffice conversion failed: {message}")
    
    # Method 3: Try pandoc conversion
    success, message, result_path = _try_pandoc_conversion(docx_path, pdf_path, logger)
    if success and result_path and _validate_pdf_quality(result_path, docx_path, logger):
        return success, message, result_path
    
    logger.warning(f"Pandoc conversion failed: {message}")
    
    # Method 4: Try improved ReportLab conversion
    success, message, result_path = _try_improved_reportlab_conversion(docx_path, pdf_path, logger)
    if success and result_path:
        return success, message, result_path
    
    logger.error(f"All Linux conversion methods failed")
    return False, f"DOCX to PDF conversion failed on Linux. Last error: {message}", None

def _try_unoconv_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Try unoconv - most reliable for exact formatting preservation
    """
    try:
        # Check if unoconv is available
        result = subprocess.run(['which', 'unoconv'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "unoconv not found in system PATH", None
        
        logger.info(f"Attempting unoconv conversion for {docx_path}")
        
        # Use temporary directory to avoid conflicts
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = os.path.join(temp_dir, 'output.pdf')
            
            cmd = [
                'unoconv', 
                '-f', 'pdf',
                '-o', temp_output,
                docx_path
            ]
            
            logger.info(f"Running unoconv conversion: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(temp_output):
                if os.path.getsize(temp_output) > 0:
                    # Copy to final destination
                    shutil.copy2(temp_output, pdf_path)
                    logger.info(f"unoconv PDF conversion successful: {pdf_path}")
                    return True, "PDF generated successfully with unoconv", pdf_path
                else:
                    return False, "unoconv generated empty PDF file", None
            else:
                error_msg = result.stderr or result.stdout or "Unknown unoconv error"
                return False, f"unoconv conversion failed: {error_msg}", None
                
    except subprocess.TimeoutExpired:
        return False, "unoconv conversion timed out", None
    except Exception as e:
        logger.error(f"unoconv conversion error: {e}")
        return False, f"unoconv conversion error: {str(e)}", None

def _try_enhanced_libreoffice_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Enhanced LibreOffice conversion with advanced parameters for exact formatting
    """
    try:
        # Check if LibreOffice is available
        result = subprocess.run(['which', 'libreoffice'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "LibreOffice not found in system PATH", None
        
        logger.info(f"Attempting enhanced LibreOffice conversion for {docx_path}")
        
        # Use temporary directory to avoid conflicts and naming issues
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy input file to temp directory with clean name
            temp_input = os.path.join(temp_dir, 'input.docx')
            shutil.copy2(docx_path, temp_input)
            
            # CKDEV-NOTE: Enhanced LibreOffice command with quality parameters
            cmd = [
                'libreoffice', 
                '--headless',
                '--invisible',
                '--nologo',
                '--nolockcheck',
                '--nodefault',
                '--norestore',
                '--convert-to', 'pdf:writer_pdf_Export:{"ExportFormFields":false,"FormsType":0,"AllowDuplicateFieldNames":false,"ExportNotes":false,"ExportNotesPages":false,"ExportOnlyNotesPages":false,"UseTransitionEffects":false,"IsSkipEmptyPages":false,"IsAddStream":false,"EmbedStandardFonts":false,"UseTaggedPDF":false,"SelectPdfVersion":0,"ExportBookmarks":false,"ExportBookmarksToNamedDestinations":false,"ExportHiddenSlides":false,"SinglePageSheets":false}',
                '--outdir', temp_dir,
                temp_input
            ]
            
            logger.info(f"Running enhanced LibreOffice conversion: {' '.join(cmd[:8])}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                expected_pdf = os.path.join(temp_dir, 'input.pdf')
                
                if os.path.exists(expected_pdf) and os.path.getsize(expected_pdf) > 0:
                    # Copy to final destination
                    shutil.copy2(expected_pdf, pdf_path)
                    logger.info(f"Enhanced LibreOffice PDF conversion successful: {pdf_path}")
                    return True, "PDF generated successfully with enhanced LibreOffice", pdf_path
                else:
                    return False, "Enhanced LibreOffice generated empty or missing PDF file", None
            else:
                error_msg = result.stderr or result.stdout or "Unknown LibreOffice error"
                return False, f"Enhanced LibreOffice conversion failed: {error_msg}", None
                
    except subprocess.TimeoutExpired:
        return False, "Enhanced LibreOffice conversion timed out", None
    except Exception as e:
        logger.error(f"Enhanced LibreOffice conversion error: {e}")
        return False, f"Enhanced LibreOffice conversion error: {str(e)}", None

def _try_pandoc_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Pandoc conversion - excellent for preserving document structure
    """
    try:
        # Check if pandoc is available
        result = subprocess.run(['which', 'pandoc'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, "pandoc not found in system PATH", None
        
        logger.info(f"Attempting pandoc conversion for {docx_path}")
        
        cmd = [
            'pandoc',
            docx_path,
            '-o', pdf_path,
            '--pdf-engine=wkhtmltopdf',
            '--variable', 'geometry:margin=1in'
        ]
        
        logger.info(f"Running pandoc conversion: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(pdf_path):
            if os.path.getsize(pdf_path) > 0:
                logger.info(f"Pandoc PDF conversion successful: {pdf_path}")
                return True, "PDF generated successfully with pandoc", pdf_path
            else:
                return False, "Pandoc generated empty PDF file", None
        else:
            error_msg = result.stderr or result.stdout or "Unknown pandoc error"
            return False, f"Pandoc conversion failed: {error_msg}", None
            
    except subprocess.TimeoutExpired:
        return False, "Pandoc conversion timed out", None
    except Exception as e:
        logger.error(f"Pandoc conversion error: {e}")
        return False, f"Pandoc conversion error: {str(e)}", None

def _try_improved_reportlab_conversion(docx_path: str, pdf_path: str, logger) -> Tuple[bool, str, Optional[str]]:
    """
    CKDEV-NOTE: Improved ReportLab fallback with better formatting preservation
    """
    try:
        from docx import Document
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
        
        logger.info(f"Attempting improved ReportLab conversion for {docx_path}")
        
        # Load DOCX document
        doc = Document(docx_path)
        
        # Create PDF with proper document structure
        pdf_doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                  rightMargin=inch, leftMargin=inch,
                                  topMargin=inch, bottomMargin=inch)
        
        styles = getSampleStyleSheet()
        story = []
        
        # CKDEV-NOTE: Process each paragraph with proper styling
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        )
        
        processed_paragraphs = set()  # CKDEV-NOTE: Prevent duplicates
        
        for i, paragraph in enumerate(doc.paragraphs):
            text = paragraph.text.strip()
            if text and text not in processed_paragraphs:
                processed_paragraphs.add(text)
                
                # Determine if it's a title (first paragraph or short text)
                if i == 0 or len(text) < 100:
                    style = title_style
                else:
                    style = normal_style
                
                # Create paragraph and add to story
                para = Paragraph(text.replace('\n', '<br/>'), style)
                story.append(para)
                story.append(Spacer(1, 6))
        
        # Build PDF
        pdf_doc.build(story)
        
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            logger.info(f"Improved ReportLab PDF conversion successful: {pdf_path}")
            return True, "PDF generated successfully with improved ReportLab", pdf_path
        else:
            return False, "Improved ReportLab generated empty or invalid PDF", None
            
    except ImportError as e:
        missing_lib = str(e).split()[-1] if 'reportlab' in str(e) else 'python-docx'
        return False, f"Missing library for ReportLab conversion: {missing_lib}", None
    except Exception as e:
        logger.error(f"Improved ReportLab conversion error: {e}")
        return False, f"Improved ReportLab conversion error: {str(e)}", None

def _validate_pdf_quality(pdf_path: str, original_docx: str, logger) -> bool:
    """
    CKDEV-NOTE: Validate PDF quality to ensure no duplicates or formatting issues
    """
    try:
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            logger.warning("PDF validation failed: file doesn't exist or is empty")
            return False
        
        # Basic size check - PDF should be reasonable size
        pdf_size = os.path.getsize(pdf_path)
        docx_size = os.path.getsize(original_docx)
        
        # PDF should not be too small or suspiciously large
        if pdf_size < 1000:  # Less than 1KB is suspicious
            logger.warning(f"PDF validation failed: file too small ({pdf_size} bytes)")
            return False
        
        if pdf_size > docx_size * 50:  # More than 50x original size is suspicious
            logger.warning(f"PDF validation failed: file suspiciously large ({pdf_size} vs {docx_size} bytes)")
            return False
        
        # Try to read PDF header
        try:
            with open(pdf_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF-'):
                    logger.warning("PDF validation failed: invalid PDF header")
                    return False
        except Exception as e:
            logger.warning(f"PDF validation failed: cannot read header: {e}")
            return False
        
        logger.info(f"PDF validation successful: {pdf_path} ({pdf_size} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"PDF validation error: {e}")
        return False

def install_linux_requirements():
    """
    CKDEV-NOTE: Install required packages for Linux PDF conversion
    """
    requirements = [
        "python-docx",
        "reportlab"
    ]
    
    logger = logging.getLogger(__name__)
    
    for package in requirements:
        try:
            __import__(package.replace('-', '_'))
            logger.info(f"Package {package} is already installed")
        except ImportError:
            logger.warning(f"Package {package} not found - install with: pip install {package}")
    
    # Check system packages
    system_packages = ['unoconv', 'pandoc', 'libreoffice', 'wkhtmltopdf']
    for package in system_packages:
        result = subprocess.run(['which', package], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"System package {package} is available")
        else:
            logger.warning(f"System package {package} not found - install with: sudo apt-get install {package}")
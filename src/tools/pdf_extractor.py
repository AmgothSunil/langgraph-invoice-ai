"""
PDF text extraction with OCR fallback.
Handles missing dependencies gracefully for production environments.
"""

import pdfplumber
from PIL import Image
import numpy as np
from typing import Tuple, List, Optional
import warnings

# Check for optional OCR dependencies
OCR_AVAILABLE = False
POPPLER_ERROR = None
TESSERACT_ERROR = None

try:
    from pdf2image import convert_from_path
    # Test if poppler is actually available
    OCR_AVAILABLE = True
except ImportError as e:
    POPPLER_ERROR = "pdf2image not installed. Install with: pip install pdf2image"
except Exception as e:
    POPPLER_ERROR = str(e)

try:
    import pytesseract
except ImportError:
    TESSERACT_ERROR = "pytesseract not installed. Install with: pip install pytesseract"
except Exception as e:
    TESSERACT_ERROR = str(e)

try:
    import cv2
except ImportError:
    cv2 = None


class PDFExtractor:
    """
    Handles PDF text extraction with fallback to OCR.
    
    OCR requires optional system dependencies:
    - Poppler: https://github.com/osber/poppler-windows/releases (Windows)
    - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
    
    If these are not installed, scanned PDFs will return an error message
    but digital PDFs will still work via pdfplumber.
    """
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self._ocr_warning_shown = False
    
    def extract_text(self, pdf_path: str) -> Tuple[str, float, str]:
        """
        Extract text from PDF with OCR fallback.
        
        Returns: 
            Tuple of (text, confidence, quality)
            - text: Extracted text content
            - confidence: 0.0-1.0 confidence score
            - quality: "excellent", "good", "acceptable", "poor", or "ocr_unavailable"
        """
        try:
            # Try direct text extraction first (works for digital PDFs)
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if text.strip():
                    return text.strip(), 0.95, "excellent"
        except Exception as e:
            print(f"⚠️  Direct PDF extraction failed: {e}")
        
        # Fallback to OCR for scanned documents
        return self._ocr_extraction(pdf_path)
    
    def _ocr_extraction(self, pdf_path: str) -> Tuple[str, float, str]:
        """
        OCR-based extraction with preprocessing.
        Returns helpful error if dependencies are missing.
        """
        # Check for missing dependencies
        if POPPLER_ERROR or not OCR_AVAILABLE:
            error_msg = self._get_ocr_dependency_message()
            if not self._ocr_warning_shown:
                print(f"⚠️  OCR unavailable: {error_msg}")
                self._ocr_warning_shown = True
            return (
                f"[OCR EXTRACTION FAILED]\n"
                f"This appears to be a scanned document requiring OCR.\n"
                f"Error: {error_msg}\n\n"
                f"To enable OCR processing, install:\n"
                f"1. Poppler: https://github.com/osber/poppler-windows/releases\n"
                f"2. Tesseract: https://github.com/UB-Mannheim/tesseract/wiki\n"
                f"3. Add both to your system PATH",
                0.0,
                "ocr_unavailable"
            )
        
        if TESSERACT_ERROR:
            return (
                f"[OCR EXTRACTION FAILED]\n"
                f"Tesseract OCR not available: {TESSERACT_ERROR}",
                0.0,
                "ocr_unavailable"
            )
        
        # Attempt OCR extraction
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            images = convert_from_path(pdf_path)
            full_text = ""
            confidences = []
            
            for img in images:
                # Preprocess image if OpenCV is available
                if cv2 is not None:
                    processed_img = self._preprocess_image(img)
                else:
                    processed_img = img
                
                # OCR with confidence
                data = pytesseract.image_to_data(
                    processed_img, 
                    output_type=pytesseract.Output.DICT
                )
                
                text = " ".join([
                    data['text'][i] 
                    for i in range(len(data['text'])) 
                    if int(data['conf'][i]) > 0
                ])
                
                valid_confs = [
                    int(data['conf'][i]) 
                    for i in range(len(data['conf'])) 
                    if int(data['conf'][i]) > 0
                ]
                
                if valid_confs:
                    conf = np.mean(valid_confs) / 100.0
                else:
                    conf = 0.0
                
                full_text += text + "\n"
                confidences.append(conf)
            
            avg_conf = np.mean(confidences) if confidences else 0.0
            quality = self._assess_quality(avg_conf)
            
            return full_text.strip(), avg_conf, quality
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide helpful messages for common errors
            if "poppler" in error_msg.lower() or "Unable to get page count" in error_msg:
                return (
                    f"[OCR EXTRACTION FAILED]\n"
                    f"Poppler is not installed or not in PATH.\n\n"
                    f"Install Poppler:\n"
                    f"- Windows: https://github.com/osber/poppler-windows/releases\n"
                    f"- Add the 'bin' folder to your system PATH\n"
                    f"- Restart your terminal/IDE after installation",
                    0.0,
                    "ocr_unavailable"
                )
            elif "tesseract" in error_msg.lower():
                return (
                    f"[OCR EXTRACTION FAILED]\n"
                    f"Tesseract OCR is not installed or not in PATH.\n\n"
                    f"Install Tesseract:\n"
                    f"- Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    f"- Add installation folder to your system PATH",
                    0.0,
                    "ocr_unavailable"
                )
            else:
                return (
                    f"[OCR EXTRACTION FAILED]\n"
                    f"Unexpected error during OCR: {error_msg}",
                    0.0,
                    "ocr_unavailable"
                )
    
    def _get_ocr_dependency_message(self) -> str:
        """Get a helpful message about missing OCR dependencies"""
        messages = []
        if POPPLER_ERROR:
            messages.append(f"Poppler: {POPPLER_ERROR}")
        if TESSERACT_ERROR:
            messages.append(f"Tesseract: {TESSERACT_ERROR}")
        return "; ".join(messages) if messages else "OCR dependencies not available"
    
    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """Image preprocessing for better OCR"""
        # Convert to numpy array
        img_array = np.array(img)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Deskew
        gray = self._deskew(gray)
        
        # Denoise
        gray = cv2.fastNlMeansDenoising(gray)
        
        # Binarization
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        return Image.fromarray(binary)
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct image rotation"""
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    
    def _assess_quality(self, confidence: float) -> str:
        """Assess document quality based on confidence"""
        if confidence >= 0.9:
            return "excellent"
        elif confidence >= 0.75:
            return "good"
        elif confidence >= 0.6:
            return "acceptable"
        else:
            return "poor"
    
    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
        """Extract tables from PDF"""
        with pdfplumber.open(pdf_path) as pdf:
            tables = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
            return tables

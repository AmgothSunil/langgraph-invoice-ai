"""
PDF text extraction with OCR fallback.
Uses PyMuPDF + EasyOCR for zero system dependency OCR.
Falls back gracefully if OCR libraries are not available.
"""

import pdfplumber
from PIL import Image
import numpy as np
from typing import Tuple, List
import io

# Check for optional OCR dependencies (PyMuPDF + EasyOCR - no system deps needed!)
PYMUPDF_AVAILABLE = False
EASYOCR_AVAILABLE = False
EASYOCR_READER = None

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    pass

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    pass


class PDFExtractor:
    """
    Handles PDF text extraction with OCR fallback.
    
    Uses PyMuPDF + EasyOCR for scanned documents.
    No system dependencies required (no Poppler, no Tesseract).
    
    For digital PDFs: Uses pdfplumber (fast, accurate)
    For scanned PDFs: Uses PyMuPDF to render images + EasyOCR for text recognition
    """
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self._ocr_reader = None
        self._ocr_init_attempted = False
    
    def _get_ocr_reader(self):
        """Lazy initialization of EasyOCR reader (downloads models on first use)"""
        if self._ocr_reader is None and not self._ocr_init_attempted:
            self._ocr_init_attempted = True
            if EASYOCR_AVAILABLE:
                try:
                    import easyocr
                    print("🔄 Initializing EasyOCR (first run may download models)...")
                    self._ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                    print("✅ EasyOCR initialized successfully")
                except Exception as e:
                    print(f"⚠️  Failed to initialize EasyOCR: {e}")
        return self._ocr_reader
    
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
        OCR-based extraction using PyMuPDF + EasyOCR.
        No system dependencies required!
        """
        # Check for PyMuPDF
        if not PYMUPDF_AVAILABLE:
            return (
                "[OCR EXTRACTION FAILED]\n"
                "PyMuPDF not installed.\n\n"
                "Install with: pip install pymupdf",
                0.0,
                "ocr_unavailable"
            )
        
        # Check for EasyOCR
        if not EASYOCR_AVAILABLE:
            return (
                "[OCR EXTRACTION FAILED]\n"
                "EasyOCR not installed.\n\n"
                "Install with: pip install easyocr",
                0.0,
                "ocr_unavailable"
            )
        
        # Get or initialize OCR reader
        reader = self._get_ocr_reader()
        if reader is None:
            return (
                "[OCR EXTRACTION FAILED]\n"
                "Failed to initialize EasyOCR reader.",
                0.0,
                "ocr_unavailable"
            )
        
        try:
            import fitz  # PyMuPDF
            
            full_text = ""
            confidences = []
            
            # Open PDF with PyMuPDF
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Render page to image (300 DPI for good quality)
                mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Convert to numpy array for EasyOCR
                img_array = np.array(img)
                
                # Run OCR
                results = reader.readtext(img_array)
                
                # Extract text and confidence from results
                page_text = ""
                page_confidences = []
                
                for (bbox, text, conf) in results:
                    page_text += text + " "
                    page_confidences.append(conf)
                
                full_text += f"{page_text.strip()}\n"
                
                if page_confidences:
                    confidences.append(np.mean(page_confidences))
            
            doc.close()
            
            avg_conf = np.mean(confidences) if confidences else 0.0
            quality = self._assess_quality(avg_conf)
            
            if not full_text.strip():
                return (
                    "[OCR EXTRACTION FAILED]\n"
                    "No text could be extracted from the scanned document.",
                    0.0,
                    "poor"
                )
            
            return full_text.strip(), avg_conf, quality
            
        except Exception as e:
            return (
                f"[OCR EXTRACTION FAILED]\n"
                f"Error during OCR processing: {str(e)}",
                0.0,
                "ocr_unavailable"
            )
    
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
        """Extract tables from PDF using pdfplumber"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                tables = []
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
                return tables
        except Exception as e:
            print(f"⚠️  Table extraction failed: {e}")
            return []

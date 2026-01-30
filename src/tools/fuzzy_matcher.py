"""
Fuzzy matching utilities for invoice-to-PO reconciliation.
Uses rapidfuzz for high-performance string matching.
"""

from rapidfuzz import fuzz, process
from typing import List, Dict, Tuple, Optional
import re

from src.config.logger import setup_logger

# Initialize logger
logger = setup_logger("FuzzyMatcher", "fuzzy_matcher.log")


class FuzzyMatcher:
    """Fuzzy matching for suppliers, products, and PO matching"""
    
    def __init__(self, threshold: float = 70.0):
        """
        Initialize fuzzy matcher.
        
        Args:
            threshold: Minimum similarity score (0-100) to consider a match
        """
        self.threshold = threshold
        logger.debug(f"Initialized FuzzyMatcher with threshold: {threshold}")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        # Lowercase, remove extra whitespace, remove common suffixes
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        # Remove common business suffixes
        suffixes = [' ltd', ' limited', ' inc', ' plc', ' corp', ' co.', ' llc', ' gmbh', ' ab']
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)]
        return text.strip()
    
    def match_supplier(
        self, 
        invoice_supplier: str, 
        po_supplier: str
    ) -> Tuple[bool, float]:
        """
        Match supplier names with fuzzy logic.
        
        Args:
            invoice_supplier: Supplier name from invoice
            po_supplier: Supplier name from PO
            
        Returns:
            Tuple of (is_match, confidence_score)
        """
        if not invoice_supplier or not po_supplier:
            return False, 0.0
        
        norm_inv = self._normalize_text(invoice_supplier)
        norm_po = self._normalize_text(po_supplier)
        
        # Try multiple matching strategies
        scores = [
            fuzz.ratio(norm_inv, norm_po),
            fuzz.partial_ratio(norm_inv, norm_po),
            fuzz.token_sort_ratio(norm_inv, norm_po),
            fuzz.token_set_ratio(norm_inv, norm_po)
        ]
        
        # Use the highest score
        best_score = max(scores)
        confidence = best_score / 100.0
        
        is_match = best_score >= self.threshold
        logger.debug(f"Supplier match: '{invoice_supplier}' vs '{po_supplier}' -> {is_match} (score: {best_score})")
        
        return is_match, confidence
    
    def match_product_description(
        self, 
        invoice_desc: str, 
        po_desc: str
    ) -> Tuple[bool, float]:
        """
        Match product descriptions with fuzzy logic.
        
        Args:
            invoice_desc: Product description from invoice
            po_desc: Product description from PO
            
        Returns:
            Tuple of (is_match, confidence_score)
        """
        if not invoice_desc or not po_desc:
            return False, 0.0
        
        norm_inv = self._normalize_text(invoice_desc)
        norm_po = self._normalize_text(po_desc)
        
        # Token-based matching works better for product descriptions
        scores = [
            fuzz.token_set_ratio(norm_inv, norm_po),
            fuzz.partial_ratio(norm_inv, norm_po),
            fuzz.token_sort_ratio(norm_inv, norm_po)
        ]
        
        best_score = max(scores)
        confidence = best_score / 100.0
        
        is_match = best_score >= self.threshold
        logger.debug(f"Product match: '{invoice_desc[:30]}...' vs '{po_desc[:30]}...' -> {is_match} (score: {best_score})")
        
        return is_match, confidence
    
    def find_best_po_match(
        self, 
        invoice_data: Dict, 
        all_pos: List[Dict]
    ) -> List[Tuple[str, float, str]]:
        """
        Find the best matching PO(s) for an invoice.
        
        Args:
            invoice_data: Dict with 'supplier_name', 'invoice_date', 'line_items'
            all_pos: List of PO dictionaries
            
        Returns:
            List of (po_number, confidence, match_reason) sorted by confidence
        """
        if not all_pos:
            logger.debug("No POs available for matching")
            return []
        
        logger.debug(f"Finding best PO match among {len(all_pos)} POs")
        
        matches = []
        inv_supplier = invoice_data.get('supplier_name', '')
        inv_items = invoice_data.get('line_items', [])
        
        for po in all_pos:
            po_number = po.get('po_number', '')
            po_supplier = po.get('supplier', '')
            po_items = po.get('line_items', [])
            
            # Calculate supplier match score
            supplier_match, supplier_conf = self.match_supplier(inv_supplier, po_supplier)
            
            # Calculate line item match score
            item_matches = 0
            total_item_conf = 0.0
            
            for inv_item in inv_items:
                inv_desc = inv_item.get('description', '')
                best_item_conf = 0.0
                
                for po_item in po_items:
                    po_desc = po_item.get('description', '')
                    is_match, conf = self.match_product_description(inv_desc, po_desc)
                    if conf > best_item_conf:
                        best_item_conf = conf
                
                if best_item_conf >= self.threshold / 100.0:
                    item_matches += 1
                total_item_conf += best_item_conf
            
            # Calculate overall confidence
            item_match_rate = item_matches / len(inv_items) if inv_items else 0.0
            avg_item_conf = total_item_conf / len(inv_items) if inv_items else 0.0
            
            # Weighted combination: 40% supplier, 60% items
            overall_conf = (supplier_conf * 0.4) + (avg_item_conf * 0.6)
            
            # Build match reason
            reasons = []
            if supplier_match:
                reasons.append(f"supplier match ({supplier_conf:.0%})")
            if item_match_rate > 0:
                reasons.append(f"{item_matches}/{len(inv_items)} items matched")
            
            match_reason = ", ".join(reasons) if reasons else "weak match"
            
            # Only include if above minimum threshold
            if overall_conf >= self.threshold / 100.0:
                matches.append((po_number, overall_conf, match_reason))
        
        # Sort by confidence descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        logger.debug(f"Found {len(matches)} potential PO matches")
        return matches
    
    def match_item_code(
        self, 
        invoice_code: str, 
        po_code: str
    ) -> Tuple[bool, float]:
        """
        Match item codes (exact or near-exact).
        
        Args:
            invoice_code: Item code from invoice
            po_code: Item code from PO
            
        Returns:
            Tuple of (is_match, confidence_score)
        """
        if not invoice_code or not po_code:
            return False, 0.0
        
        # Normalize codes
        norm_inv = invoice_code.upper().strip()
        norm_po = po_code.upper().strip()
        
        # Exact match
        if norm_inv == norm_po:
            logger.debug(f"Exact item code match: {invoice_code}")
            return True, 1.0
        
        # High-threshold fuzzy match for codes
        score = fuzz.ratio(norm_inv, norm_po)
        confidence = score / 100.0
        
        is_match = score >= 90
        logger.debug(f"Item code match: '{invoice_code}' vs '{po_code}' -> {is_match} (score: {score})")
        
        # Codes should match very closely (90%+)
        return is_match, confidence


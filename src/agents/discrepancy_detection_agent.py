# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from src.graph.state import AgentState, Discrepancy
from src.config.logger import setup_logger
from src.config.exception import AppException
from typing import List, Dict, Optional
from dotenv import load_dotenv
import sys
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize logger
logger = setup_logger("DiscrepancyDetectionAgent", "discrepancy_detection_agent.log")

class DiscrepancyDetectionAgent:
    """Detects discrepancies between invoice and PO"""
    
    def __init__(self):
        try:
            logger.info("Initializing DiscrepancyDetectionAgent")
            self.llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0, groq_api_key=groq_api_key)
            self.price_tolerance = 0.02  # 2%
            self.total_tolerance_pct = 0.01  # 1%
            self.total_tolerance_abs = 5.0  # £5
            logger.info("DiscrepancyDetectionAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DiscrepancyDetectionAgent: {e}")
            raise AppException(e, sys)
    
    def run(self, state: AgentState) -> AgentState:
        """Execute discrepancy detection"""
        logger.info("Discrepancy Detection Agent: Analyzing...")
        
        try:
            extracted = state['extracted_data']
            matched_po = state['matched_po_data']
            
            if not matched_po:
                logger.warning("No PO to compare against")
                state['discrepancies'] = []
                state['next_step'] = 'resolution'
                return state
            
            discrepancies = []
            
            # Check price variances
            price_discrepancies = self._check_price_variances(
                extracted, matched_po
            )
            discrepancies.extend(price_discrepancies)
            logger.debug(f"Found {len(price_discrepancies)} price discrepancies")
            
            # Check quantity variances
            qty_discrepancies = self._check_quantity_variances(
                extracted, matched_po
            )
            discrepancies.extend(qty_discrepancies)
            logger.debug(f"Found {len(qty_discrepancies)} quantity discrepancies")
            
            # Check total variance
            total_disc = self._check_total_variance(
                extracted, matched_po
            )
            if total_disc:
                discrepancies.append(total_disc)
                logger.debug("Found total variance discrepancy")
            
            # Check missing PO reference
            if not extracted.po_reference:
                discrepancies.append(Discrepancy(
                    type="missing_po_reference",
                    severity="medium",
                    field="po_reference",
                    invoice_value=None,
                    details=f"Invoice missing PO reference. Matched to {matched_po['po_number']} via fuzzy matching.",
                    recommended_action="flag_for_review",
                    confidence=state['matching_results'].po_match_confidence
                ))
                logger.debug("Added missing PO reference discrepancy")
            
            state['discrepancies'] = discrepancies
            state['current_agent'] = 'discrepancy_detection'
            state['next_step'] = 'resolution'
            
            logger.info(f"Found {len(discrepancies)} total discrepancies")
            
            return state
            
        except Exception as e:
            logger.error(f"Discrepancy detection failed: {e}")
            state['discrepancies'] = []
            state['current_agent'] = 'discrepancy_detection'
            state['next_step'] = 'resolution'
            return state
    
    def _check_price_variances(
        self, 
        invoice_data, 
        po_data: Dict
    ) -> List[Discrepancy]:
        """Check for price mismatches"""
        discrepancies = []
        
        try:
            for i, inv_item in enumerate(invoice_data.line_items):
                # Find matching PO item
                po_item = self._find_matching_po_item(
                    inv_item, po_data['line_items']
                )
                
                if po_item:
                    inv_price = inv_item.unit_price
                    po_price = po_item['unit_price']
                    
                    variance_pct = abs(inv_price - po_price) / po_price if po_price > 0 else 0
                    
                    if variance_pct > self.price_tolerance:
                        severity = "high" if variance_pct > 0.15 else "medium"
                        
                        discrepancies.append(Discrepancy(
                            type="price_mismatch",
                            severity=severity,
                            line_item_index=i,
                            field="unit_price",
                            invoice_value=inv_price,
                            po_value=po_price,
                            variance_percentage=variance_pct * 100,
                            details=f"{inv_item.description}: Invoice £{inv_price:.2f} vs PO £{po_price:.2f} ({variance_pct*100:.1f}% difference)",
                            recommended_action="escalate_to_human" if variance_pct > 0.15 else "flag_for_review",
                            confidence=0.99
                        ))
        except Exception as e:
            logger.error(f"Error checking price variances: {e}")
        
        return discrepancies
    
    def _check_quantity_variances(
        self, 
        invoice_data, 
        po_data: Dict
    ) -> List[Discrepancy]:
        """Check for quantity mismatches"""
        discrepancies = []
        
        try:
            for i, inv_item in enumerate(invoice_data.line_items):
                po_item = self._find_matching_po_item(
                    inv_item, po_data['line_items']
                )
                
                if po_item:
                    inv_qty = inv_item.quantity
                    po_qty = po_item['quantity']
                    
                    if inv_qty != po_qty:
                        discrepancies.append(Discrepancy(
                            type="quantity_mismatch",
                            severity="medium",
                            line_item_index=i,
                            field="quantity",
                            invoice_value=inv_qty,
                            po_value=po_qty,
                            details=f"{inv_item.description}: Invoice qty {inv_qty} vs PO qty {po_qty}",
                            recommended_action="flag_for_review",
                            confidence=0.95
                        ))
        except Exception as e:
            logger.error(f"Error checking quantity variances: {e}")
        
        return discrepancies
    
    def _check_total_variance(
        self, 
        invoice_data, 
        po_data: Dict
    ) -> Optional[Discrepancy]:
        """Check total amount variance"""
        try:
            inv_total = invoice_data.total
            po_total = po_data['total']
            
            variance_abs = abs(inv_total - po_total)
            variance_pct = variance_abs / po_total if po_total > 0 else 0
            
            tolerance = min(self.total_tolerance_abs, po_total * self.total_tolerance_pct)
            
            if variance_abs > tolerance:
                severity = "high" if variance_pct > 0.10 else "medium"
                
                return Discrepancy(
                    type="total_variance",
                    severity=severity,
                    field="total",
                    invoice_value=inv_total,
                    po_value=po_total,
                    variance_percentage=variance_pct * 100,
                    details=f"Total variance: Invoice £{inv_total:.2f} vs PO £{po_total:.2f} (£{variance_abs:.2f} difference)",
                    recommended_action="escalate_to_human" if variance_pct > 0.10 else "flag_for_review",
                    confidence=0.99
                )
        except Exception as e:
            logger.error(f"Error checking total variance: {e}")
        
        return None
    
    def _find_matching_po_item(self, inv_item, po_items: List[Dict]) -> Optional[Dict]:
        """Find matching PO line item"""
        try:
            from src.tools.fuzzy_matcher import FuzzyMatcher
            matcher = FuzzyMatcher()
            
            for po_item in po_items:
                is_match, conf = matcher.match_product_description(
                    inv_item.description,
                    po_item['description']
                )
                if is_match:
                    return po_item
        except Exception as e:
            logger.error(f"Error finding matching PO item: {e}")
        
        return None


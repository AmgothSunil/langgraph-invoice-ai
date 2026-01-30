# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from src.tools.fuzzy_matcher import FuzzyMatcher
from src.tools.po_database import PODatabase
from src.graph.state import AgentState, MatchingResult
from src.config.logger import setup_logger
from src.config.exception import AppException
from typing import Dict, Optional
from dotenv import load_dotenv
import sys
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize logger
logger = setup_logger("MatchingAgent", "matching_agent.log")

class MatchingAgent:
    """Matches invoices to purchase orders"""
    
    def __init__(self):
        try:
            logger.info("Initializing MatchingAgent")
            self.llm = ChatGroq(
                model="openai/gpt-oss-120b", 
                temperature=0,
                groq_api_key=groq_api_key
            )
            self.fuzzy_matcher = FuzzyMatcher(threshold=70.0)
            logger.info("MatchingAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MatchingAgent: {e}")
            raise AppException(e, sys)
    
    def run(self, state: AgentState) -> AgentState:
        """Execute matching agent"""
        logger.info("Matching Agent: Finding PO match...")
        
        try:
            po_db = PODatabase(state['po_database_path'])
            extracted = state['extracted_data']
            
            if not extracted:
                logger.warning("No extracted data available for matching")
                state['next_step'] = 'escalate'
                return state
            
            # Primary matching: exact PO reference
            matched_po, method, confidence = self._match_by_po_reference(
                extracted, po_db
            )
            logger.debug(f"PO reference match result: method={method}, confidence={confidence}")
            
            # Fallback: fuzzy matching
            if confidence < 0.95:
                fuzzy_match, fuzzy_conf = self._fuzzy_match(
                    extracted, po_db
                )
                logger.debug(f"Fuzzy match result: confidence={fuzzy_conf}")
                if fuzzy_conf > confidence:
                    matched_po = fuzzy_match
                    confidence = fuzzy_conf
                    method = "fuzzy_matching"
            
            if matched_po:
                # Calculate detailed matching metrics
                matching_result = self._calculate_match_metrics(
                    extracted, matched_po, method, confidence
                )
                
                state['matching_results'] = matching_result
                state['matched_po_data'] = matched_po
                logger.info(f"Matched to {matched_po['po_number']} ({confidence:.2%} confidence)")
            else:
                state['matching_results'] = MatchingResult(
                    po_match_confidence=0.0,
                    matched_po=None,
                    match_method="no_match",
                    match_rate=0.0
                )
                logger.warning("No PO match found")
            
            state['current_agent'] = 'matching'
            state['next_step'] = 'discrepancy_detection'
            
            return state
            
        except Exception as e:
            logger.error(f"Matching agent failed: {e}")
            state['matching_results'] = MatchingResult(
                po_match_confidence=0.0,
                matched_po=None,
                match_method="error",
                match_rate=0.0
            )
            state['current_agent'] = 'matching'
            state['next_step'] = 'discrepancy_detection'
            return state
    
    def _match_by_po_reference(
        self, 
        invoice_data, 
        po_db: PODatabase
    ) -> tuple:
        """Match by exact PO reference"""
        po_ref = invoice_data.po_reference
        
        if po_ref:
            logger.debug(f"Attempting exact match for PO reference: {po_ref}")
            matched_po = po_db.get_po_by_number(po_ref)
            if matched_po:
                logger.debug(f"Exact match found for PO: {po_ref}")
                return matched_po, "exact_po_reference", 0.99
        
        return None, "none", 0.0
    
    def _fuzzy_match(
        self, 
        invoice_data, 
        po_db: PODatabase
    ) -> tuple:
        """Fuzzy matching fallback"""
        try:
            all_pos = po_db.get_all_pos()
            
            inv_dict = {
                'supplier_name': invoice_data.supplier_name,
                'invoice_date': invoice_data.invoice_date,
                'line_items': [
                    {'description': item.description}
                    for item in invoice_data.line_items
                ]
            }
            
            matches = self.fuzzy_matcher.find_best_po_match(
                inv_dict, all_pos
            )
            
            if matches:
                best_po_number, best_conf, reason = matches[0]
                logger.debug(f"Best fuzzy match: {best_po_number} with confidence {best_conf}")
                matched_po = po_db.get_po_by_number(best_po_number)
                return matched_po, best_conf
            
            return None, 0.0
        except Exception as e:
            logger.error(f"Fuzzy matching failed: {e}")
            return None, 0.0
    
    def _calculate_match_metrics(
        self,
        invoice_data,
        matched_po: Dict,
        method: str,
        confidence: float
    ) -> MatchingResult:
        """Calculate detailed matching metrics"""
        try:
            # Check supplier match
            supplier_match, _ = self.fuzzy_matcher.match_supplier(
                invoice_data.supplier_name or "",
                matched_po['supplier']
            )
            
            # Count line item matches
            inv_items = invoice_data.line_items
            po_items = matched_po['line_items']
            
            matched_count = 0
            for inv_item in inv_items:
                for po_item in po_items:
                    is_match, _ = self.fuzzy_matcher.match_product_description(
                        inv_item.description,
                        po_item['description']
                    )
                    if is_match:
                        matched_count += 1
                        break
            
            match_rate = matched_count / len(inv_items) if inv_items else 0.0
            logger.debug(f"Match metrics: supplier_match={supplier_match}, matched_items={matched_count}/{len(inv_items)}")
            
            return MatchingResult(
                po_match_confidence=confidence,
                matched_po=matched_po['po_number'],
                match_method=method,
                supplier_match=supplier_match,
                line_items_matched=matched_count,
                line_items_total=len(inv_items),
                match_rate=match_rate
            )
        except Exception as e:
            logger.error(f"Failed to calculate match metrics: {e}")
            raise AppException(e, sys)


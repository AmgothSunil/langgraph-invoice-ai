from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class LineItem(BaseModel):
    item_code: Optional[str] = None
    description: str
    quantity: float
    unit: str
    unit_price: float
    line_total: float
    extraction_confidence: float = 0.0

class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_vat: Optional[str] = None
    po_reference: Optional[str] = None
    payment_terms: Optional[str] = None
    currency: str = "GBP"
    line_items: List[LineItem] = []
    subtotal: float = 0.0
    vat_amount: float = 0.0
    vat_rate: float = 0.0
    total: float = 0.0

class MatchingResult(BaseModel):
    po_match_confidence: float
    matched_po: Optional[str] = None
    match_method: str
    supplier_match: bool = False
    date_variance_days: Optional[int] = None
    line_items_matched: int = 0
    line_items_total: int = 0
    match_rate: float = 0.0
    alternative_matches: List[Dict] = []

class Discrepancy(BaseModel):
    type: str
    severity: str
    line_item_index: Optional[int] = None
    field: str
    invoice_value: Any
    po_value: Any = None
    variance_percentage: Optional[float] = None
    details: str
    recommended_action: str
    confidence: float

class AgentState(TypedDict):
    # Input
    invoice_file_path: str
    po_database_path: str
    
    # Document Intelligence Agent
    raw_document: Optional[bytes]
    document_quality: str
    extracted_data: Optional[InvoiceData]
    extraction_confidence: float
    extraction_errors: List[str]
    
    # Matching Agent
    matching_results: Optional[MatchingResult]
    matched_po_data: Optional[Dict]
    
    # Discrepancy Detection Agent
    discrepancies: List[Discrepancy]
    total_variance: Dict[str, float]
    
    # Resolution Recommendation Agent
    recommended_action: str
    risk_level: str
    confidence: float
    agent_reasoning: str
    
    # Metadata
    processing_timestamp: str
    processing_duration: float
    agent_execution_trace: Dict[str, Any]
    
    # Control Flow
    current_agent: str
    next_step: str
    should_escalate: bool
    human_feedback: Optional[Dict]

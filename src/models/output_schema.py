from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ProcessingOutput(BaseModel):
    invoice_id: str
    processing_timestamp: str
    processing_duration_seconds: float
    document_info: Dict[str, Any]
    processing_results: Dict[str, Any]
    agent_execution_trace: Dict[str, Dict[str, Any]]

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": "INV-2024-1001",
                "processing_timestamp": "2024-01-29T10:15:32Z",
                "processing_duration_seconds": 12.4,
                "document_info": {
                    "filename": "Invoice_1_Baseline.pdf",
                    "file_size_kb": 45.2,
                    "page_count": 1,
                    "document_quality": "excellent"
                },
                "processing_results": {
                    "extraction_confidence": 0.97,
                    "extracted_data": {},
                    "matching_results": {},
                    "discrepancies": [],
                    "recommended_action": "auto_approve",
                    "agent_reasoning": "..."
                }
            }
        }

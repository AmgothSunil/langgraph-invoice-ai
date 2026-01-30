"""
FastAPI Backend for Invoice Reconciliation System

Provides REST API endpoints for:
- Processing invoices against purchase orders
- Uploading and managing PO database
- Health checks and status
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import tempfile
import shutil
import os
import json
from pathlib import Path
from datetime import datetime
import uuid

from src.graph.workflow import InvoiceReconciliationWorkflow
from src.tools.po_database import PODatabase
from src.config.logger import setup_logger
from src.config.exception import AppException

# Initialize logger
logger = setup_logger("FastAPIApp", "fastapi_app.log")

# Initialize FastAPI app
app = FastAPI(
    title="LangGraph Invoice AI",
    description="AI-powered Invoice Reconciliation System",
    version="1.0.0"
)

# Add CORS middleware for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize workflow (singleton)
workflow = None

# Temp storage for uploaded files
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Results storage
RESULTS_DIR = Path("data/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# Response Models
class ProcessingResult(BaseModel):
    job_id: str
    status: str  # "passed", "review", "escalate", "error"
    invoice_id: Optional[str] = None
    confidence: float = 0.0
    risk_level: str = ""
    recommended_action: str = ""
    discrepancies_count: int = 0
    processing_time_seconds: float = 0.0
    agent_reasoning: str = ""
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


class POUploadResponse(BaseModel):
    message: str
    po_count: int
    file_path: str


# Helper Functions
def get_workflow():
    """Get or create workflow instance"""
    global workflow
    if workflow is None:
        logger.info("Initializing workflow...")
        workflow = InvoiceReconciliationWorkflow()
    return workflow


def determine_status(recommended_action: str, risk_level: str) -> str:
    """Convert recommended action to simple status"""
    if recommended_action == "auto_approve":
        return "passed"
    elif recommended_action == "escalate_to_human" or risk_level == "high":
        return "escalate"
    else:
        return "review"


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.post("/api/upload-po", response_model=POUploadResponse)
async def upload_purchase_orders(file: UploadFile = File(...)):
    """
    Upload a purchase orders JSON file.
    This will be used for matching invoices.
    """
    logger.info(f"Uploading PO file: {file.filename}")
    
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")
    
    try:
        # Save to uploads directory
        po_path = UPLOAD_DIR / "purchase_orders.json"
        
        with open(po_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Validate JSON
        with open(po_path, "r") as f:
            data = json.load(f)
        
        po_count = len(data.get("purchase_orders", []))
        
        logger.info(f"PO file uploaded successfully with {po_count} purchase orders")
        
        return POUploadResponse(
            message="Purchase orders uploaded successfully",
            po_count=po_count,
            file_path=str(po_path)
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error uploading PO file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process-invoice", response_model=ProcessingResult)
async def process_invoice(
    invoice: UploadFile = File(...),
    po_file: Optional[UploadFile] = File(None)
):
    """
    Process an invoice PDF against purchase orders.
    
    - invoice: PDF file of the invoice to process
    - po_file: Optional JSON file with purchase orders (uses default if not provided)
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"[Job {job_id}] Processing invoice: {invoice.filename}")
    
    if not invoice.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invoice must be a PDF file")
    
    try:
        # Save invoice to temp file
        invoice_path = UPLOAD_DIR / f"{job_id}_{invoice.filename}"
        with open(invoice_path, "wb") as buffer:
            content = await invoice.read()
            buffer.write(content)
        
        # Determine PO database path
        if po_file:
            po_path = UPLOAD_DIR / f"{job_id}_po.json"
            with open(po_path, "wb") as buffer:
                po_content = await po_file.read()
                buffer.write(po_content)
        else:
            # Use default or previously uploaded PO file
            po_path = UPLOAD_DIR / "purchase_orders.json"
            if not po_path.exists():
                po_path = Path("data/purchase_orders.json")
        
        if not po_path.exists():
            raise HTTPException(
                status_code=400, 
                detail="No purchase orders available. Please upload a PO file first."
            )
        
        # Run workflow
        wf = get_workflow()
        result = wf.run(str(invoice_path), str(po_path))
        
        # Save result
        result_path = RESULTS_DIR / f"{job_id}_result.json"
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2)
        
        # Determine status
        recommended_action = result.get("processing_results", {}).get("recommended_action", "")
        risk_level = result.get("processing_results", {}).get("risk_level", "")
        status = determine_status(recommended_action, risk_level)
        
        # Count discrepancies
        discrepancies = result.get("processing_results", {}).get("discrepancies", [])
        
        logger.info(f"[Job {job_id}] Processing complete - Status: {status}")
        
        return ProcessingResult(
            job_id=job_id,
            status=status,
            invoice_id=result.get("invoice_id", "UNKNOWN"),
            confidence=result.get("processing_results", {}).get("confidence", 0.0),
            risk_level=risk_level,
            recommended_action=recommended_action,
            discrepancies_count=len(discrepancies),
            processing_time_seconds=result.get("processing_duration_seconds", 0.0),
            agent_reasoning=result.get("processing_results", {}).get("agent_reasoning", ""),
            details=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Job {job_id}] Error processing invoice: {e}")
        return ProcessingResult(
            job_id=job_id,
            status="error",
            agent_reasoning=str(e),
            details={"error": str(e)}
        )


@app.get("/api/purchase-orders")
async def get_purchase_orders():
    """Get all purchase orders from the database"""
    try:
        po_path = UPLOAD_DIR / "purchase_orders.json"
        if not po_path.exists():
            po_path = Path("data/purchase_orders.json")
        
        if not po_path.exists():
            raise HTTPException(status_code=404, detail="No purchase orders found")
        
        db = PODatabase(str(po_path))
        return {"purchase_orders": db.get_all_pos()}
        
    except Exception as e:
        logger.error(f"Error fetching POs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/{job_id}")
async def get_result(job_id: str):
    """Get processing result by job ID"""
    result_path = RESULTS_DIR / f"{job_id}_result.json"
    
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    
    with open(result_path, "r") as f:
        return json.load(f)


@app.delete("/api/cleanup")
async def cleanup_uploads():
    """Clean up all uploaded files"""
    try:
        for file in UPLOAD_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        logger.info("Cleaned up upload directory")
        return {"message": "Cleanup successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn app:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import pytest
from src.graph.workflow import InvoiceReconciliationWorkflow

def test_invoice_1_baseline():
    """Test clean invoice with perfect match"""
    workflow = InvoiceReconciliationWorkflow()
    result = workflow.run(
        "data/invoices/Invoice_1_Baseline.pdf",
        "data/purchase_orders.json"
    )
    
    assert result['processing_results']['extraction_confidence'] >= 0.9
    assert result['processing_results']['recommended_action'] == 'auto_approve'
    assert len(result['processing_results']['discrepancies']) == 0

def test_invoice_4_price_trap():
    """Test invoice with 10% price discrepancy"""
    workflow = InvoiceReconciliationWorkflow()
    result = workflow.run(
        "data/invoices/Invoice_4_Price_Trap.pdf",
        "data/purchase_orders.json"
    )
    
    discrepancies = result['processing_results']['discrepancies']
    assert any(d['type'] == 'price_mismatch' for d in discrepancies)
    assert result['processing_results']['recommended_action'] != 'auto_approve'

def test_invoice_5_missing_po():
    """Test invoice with missing PO reference"""
    workflow = InvoiceReconciliationWorkflow()
    result = workflow.run(
        "data/invoices/Invoice_5_Missing_PO.pdf",
        "data/purchase_orders.json"
    )
    
    # Should fuzzy match to PO-2024-005
    matching = result['processing_results']['matching_results']
    assert matching['matched_po'] == 'PO-2024-005'
    assert matching['match_method'] == 'fuzzy_matching'

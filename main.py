import os
import json
from pathlib import Path
from src.graph.workflow import InvoiceReconciliationWorkflow
from dotenv import load_dotenv

def main():
    """Main execution function"""
    
    # Load environment variables
    load_dotenv()
    
    # Setup
    workflow = InvoiceReconciliationWorkflow()
    
    invoice_dir = Path("data/invoices")
    po_db_path = "data/purchase_orders.json"
    output_dir = Path("data/outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Process all invoices
    invoice_files = sorted(invoice_dir.glob("*.pdf"))
    
    for invoice_file in invoice_files:
        try:
            # Run workflow
            result = workflow.run(
                str(invoice_file),
                po_db_path
            )
            
            # Save output
            output_file = output_dir / f"{invoice_file.stem}_result.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"✅ Saved results to {output_file}\n")
            
        except Exception as e:
            print(f"❌ Error processing {invoice_file}: {e}\n")
            continue

if __name__ == "__main__":
    main()

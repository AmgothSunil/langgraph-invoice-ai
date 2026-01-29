import json
from typing import List, Dict, Optional

class PODatabase:
    """Purchase Order database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.pos = self._load_database()
    
    def _load_database(self) -> List[Dict]:
        """Load PO database from JSON"""
        with open(self.db_path, 'r') as f:
            data = json.load(f)
            return data.get('purchase_orders', [])
    
    def get_po_by_number(self, po_number: str) -> Optional[Dict]:
        """Get PO by exact number match"""
        for po in self.pos:
            if po['po_number'] == po_number:
                return po
        return None
    
    def get_all_pos(self) -> List[Dict]:
        """Get all purchase orders"""
        return self.pos
    
    def search_by_supplier(self, supplier: str) -> List[Dict]:
        """Search POs by supplier name"""
        results = []
        for po in self.pos:
            if supplier.lower() in po['supplier'].lower():
                results.append(po)
        return results

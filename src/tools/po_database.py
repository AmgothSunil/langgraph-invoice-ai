import json
from typing import List, Dict, Optional
import sys

from src.config.logger import setup_logger
from src.config.exception import AppException

# Initialize logger
logger = setup_logger("PODatabase", "po_database.log")

class PODatabase:
    """Purchase Order database manager"""
    
    def __init__(self, db_path: str):
        try:
            logger.info(f"Initializing PODatabase with path: {db_path}")
            self.db_path = db_path
            self.pos = self._load_database()
            logger.info(f"Loaded {len(self.pos)} purchase orders")
        except Exception as e:
            logger.error(f"Failed to initialize PODatabase: {e}")
            raise AppException(e, sys)
    
    def _load_database(self) -> List[Dict]:
        """Load PO database from JSON"""
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                return data.get('purchase_orders', [])
        except FileNotFoundError:
            logger.error(f"PO database file not found: {self.db_path}")
            raise AppException(f"PO database file not found: {self.db_path}", sys)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in PO database: {e}")
            raise AppException(e, sys)
    
    def get_po_by_number(self, po_number: str) -> Optional[Dict]:
        """Get PO by exact number match"""
        logger.debug(f"Looking up PO number: {po_number}")
        for po in self.pos:
            if po['po_number'] == po_number:
                logger.debug(f"Found PO: {po_number}")
                return po
        logger.debug(f"PO not found: {po_number}")
        return None
    
    def get_all_pos(self) -> List[Dict]:
        """Get all purchase orders"""
        logger.debug(f"Retrieving all {len(self.pos)} purchase orders")
        return self.pos
    
    def search_by_supplier(self, supplier: str) -> List[Dict]:
        """Search POs by supplier name"""
        logger.debug(f"Searching POs by supplier: {supplier}")
        results = []
        for po in self.pos:
            if supplier.lower() in po['supplier'].lower():
                results.append(po)
        logger.debug(f"Found {len(results)} POs for supplier: {supplier}")
        return results


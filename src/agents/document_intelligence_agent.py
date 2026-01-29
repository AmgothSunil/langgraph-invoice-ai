# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.tools.pdf_extractor import PDFExtractor
from src.graph.state import AgentState, InvoiceData, LineItem
from typing import Dict, List, Optional
from dotenv import load_dotenv
import json
import re
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

class DocumentIntelligenceAgent:
    """Extracts structured data from invoice PDFs"""
    
    def __init__(self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.1,
            groq_api_key=groq_api_key
        )
        self.pdf_extractor = PDFExtractor()
        self.prompt = self._create_prompt()
    
    def _create_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert invoice data extraction agent. 
Your task is to extract structured information from invoice text.

Extract the following fields with HIGH ACCURACY:
- invoice_number
- invoice_date (YYYY-MM-DD format)
- supplier_name
- supplier_address
- supplier_vat
- po_reference (PO number if present)
- payment_terms
- currency
- line_items (array of items with: item_code, description, quantity, unit, unit_price, line_total)
- subtotal
- vat_amount
- vat_rate
- total

For each field, provide a confidence score (0.0-1.0).
If a field is not found, set it to null.
Be CONSERVATIVE with confidence scores - if uncertain, score lower.

Return ONLY valid JSON matching this schema:
{{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "supplier_name": "string or null",
  "po_reference": "string or null",
  "currency": "GBP",
  "line_items": [
    {{
      "item_code": "string or null",
      "description": "string",
      "quantity": float,
      "unit": "string",
      "unit_price": float,
      "line_total": float,
      "extraction_confidence": float
    }}
  ],
  "subtotal": float,
  "vat_amount": float,
  "vat_rate": float,
  "total": float,
  "overall_confidence": float
}}"""),
            ("human", "Extract data from this invoice:\n\n{invoice_text}\n\nTables:\n{tables}")
        ])
    
    def run(self, state: AgentState) -> AgentState:
        """Execute document intelligence agent"""
        print("🔍 Document Intelligence Agent: Starting extraction...")
        
        # Extract text and tables
        text, ocr_conf, quality = self.pdf_extractor.extract_text(
            state['invoice_file_path']
        )
        tables = self.pdf_extractor.extract_tables(
            state['invoice_file_path']
        )
        
        # Format tables as text
        table_text = self._format_tables(tables)
        
        # LLM extraction
        response = self.llm.invoke(
            self.prompt.format_messages(
                invoice_text=text,
                tables=table_text
            )
        )
        
        # Parse JSON response
        try:
            extracted = json.loads(response.content)
            invoice_data = self._parse_extraction(extracted)
            
            # Adjust confidence based on OCR quality
            final_conf = min(
                extracted.get('overall_confidence', 0.8),
                ocr_conf
            )
            
            state['extracted_data'] = invoice_data
            state['extraction_confidence'] = final_conf
            state['document_quality'] = quality
            state['extraction_errors'] = []
            
            print(f"✅ Extraction complete (confidence: {final_conf:.2%})")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            state['extraction_errors'] = [f"JSON parse error: {str(e)}"]
            state['extraction_confidence'] = 0.0
        
        state['current_agent'] = 'document_intelligence'
        state['next_step'] = 'matching'
        
        return state
    
    def _format_tables(self, tables: List) -> str:
        """Format tables as readable text"""
        formatted = ""
        for i, table in enumerate(tables):
            formatted += f"\n--- Table {i+1} ---\n"
            for row in table:
                formatted += " | ".join([str(cell) for cell in row]) + "\n"
        return formatted
    
    def _parse_extraction(self, data: Dict) -> InvoiceData:
        """Parse extraction result into InvoiceData model"""
        line_items = [
            LineItem(**item) for item in data.get('line_items', [])
        ]
        
        return InvoiceData(
            invoice_number=data.get('invoice_number'),
            invoice_date=data.get('invoice_date'),
            supplier_name=data.get('supplier_name'),
            supplier_address=data.get('supplier_address'),
            supplier_vat=data.get('supplier_vat'),
            po_reference=data.get('po_reference'),
            payment_terms=data.get('payment_terms'),
            currency=data.get('currency', 'GBP'),
            line_items=line_items,
            subtotal=data.get('subtotal', 0.0),
            vat_amount=data.get('vat_amount', 0.0),
            vat_rate=data.get('vat_rate', 0.0),
            total=data.get('total', 0.0)
        )

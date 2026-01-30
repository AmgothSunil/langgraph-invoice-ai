# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.tools.pdf_extractor import PDFExtractor
from src.graph.state import AgentState, InvoiceData, LineItem
from src.utils.prompt_loader import PromptManager
from src.config.logger import setup_logger
from src.config.exception import AppException
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv
import json
import sys
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

# Get the prompts directory path
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Initialize logger
logger = setup_logger("DocumentIntelligenceAgent", "document_intelligence_agent.log")

class DocumentIntelligenceAgent:
    """Extracts structured data from invoice PDFs"""
    
    def __init__(self):
        try:
            logger.info("Initializing DocumentIntelligenceAgent")
            self.llm = ChatGroq(
                model="openai/gpt-oss-120b",
                temperature=0.1,
                groq_api_key=groq_api_key
            )
            self.pdf_extractor = PDFExtractor()
            self.prompt_manager = PromptManager()
            self.prompt = self._create_prompt()
            logger.info("DocumentIntelligenceAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DocumentIntelligenceAgent: {e}")
            raise AppException(e, sys)
    
    def _create_prompt(self) -> ChatPromptTemplate:
        # Load system prompt from external file
        system_prompt = self.prompt_manager.load_prompt(
            str(PROMPTS_DIR / "document_intelligence_prompt.txt")
        )
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Extract data from this invoice:\n\n{invoice_text}\n\nTables:\n{tables}")
        ])
    
    def run(self, state: AgentState) -> AgentState:
        """Execute document intelligence agent"""
        logger.info("Document Intelligence Agent: Starting extraction...")
        
        try:
            # Extract text and tables
            text, ocr_conf, quality = self.pdf_extractor.extract_text(
                state['invoice_file_path']
            )
            logger.debug(f"Text extraction completed. OCR confidence: {ocr_conf}, Quality: {quality}")
            
            tables = self.pdf_extractor.extract_tables(
                state['invoice_file_path']
            )
            logger.debug(f"Table extraction completed. Found {len(tables)} tables")
            
            # Format tables as text
            table_text = self._format_tables(tables)
            
            # LLM extraction
            logger.info("Invoking LLM for data extraction")
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
                
                logger.info(f"Extraction complete (confidence: {final_conf:.2%})")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                state['extraction_errors'] = [f"JSON parse error: {str(e)}"]
                state['extraction_confidence'] = 0.0
            
            state['current_agent'] = 'document_intelligence'
            state['next_step'] = 'matching'
            
            return state
            
        except Exception as e:
            logger.error(f"Document intelligence extraction failed: {e}")
            state['extraction_errors'] = [str(e)]
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
        try:
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
        except Exception as e:
            logger.error(f"Failed to parse extraction data: {e}")
            raise AppException(e, sys)


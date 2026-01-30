from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.agents.document_intelligence_agent import DocumentIntelligenceAgent
from src.agents.matching_agent import MatchingAgent
from src.agents.discrepancy_detection_agent import DiscrepancyDetectionAgent
from src.agents.resolution_recommendation_agent import ResolutionRecommendationAgent
from src.config.logger import setup_logger
from src.config.exception import AppException
from datetime import datetime, timezone
import time
import sys
from typing import Dict

# Initialize logger
logger = setup_logger("InvoiceReconciliationWorkflow", "workflow.log")

class InvoiceReconciliationWorkflow:
    """LangGraph workflow for invoice reconciliation"""
    
    def __init__(self):
        try:
            logger.info("Initializing InvoiceReconciliationWorkflow")
            self.doc_agent = DocumentIntelligenceAgent()
            self.matching_agent = MatchingAgent()
            self.discrepancy_agent = DiscrepancyDetectionAgent()
            self.resolution_agent = ResolutionRecommendationAgent()
            
            self.workflow = self._build_graph()
            logger.info("InvoiceReconciliationWorkflow initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize InvoiceReconciliationWorkflow: {e}")
            raise AppException(e, sys)
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        logger.debug("Building LangGraph workflow")
        
        # Create graph
        graph = StateGraph(AgentState)
        
        # Add nodes
        graph.add_node("document_intelligence", self._run_doc_intelligence)
        graph.add_node("matching", self._run_matching)
        graph.add_node("discrepancy_detection", self._run_discrepancy)
        graph.add_node("resolution", self._run_resolution)
        
        # Add edges
        graph.set_entry_point("document_intelligence")
        
        graph.add_conditional_edges(
            "document_intelligence",
            self._route_after_extraction,
            {
                "matching": "matching",
                "escalate": "resolution"
            }
        )
        
        graph.add_edge("matching", "discrepancy_detection")
        graph.add_edge("discrepancy_detection", "resolution")
        graph.add_edge("resolution", END)
        
        logger.debug("LangGraph workflow built successfully")
        return graph.compile()
    
    def _run_doc_intelligence(self, state: AgentState) -> AgentState:
        """Run document intelligence agent with timing"""
        logger.info("Running document intelligence agent")
        start = time.time()
        state = self.doc_agent.run(state)
        duration = time.time() - start
        
        if 'agent_execution_trace' not in state:
            state['agent_execution_trace'] = {}
        
        state['agent_execution_trace']['document_intelligence_agent'] = {
            'duration_ms': duration * 1000,
            'confidence': state['extraction_confidence'],
            'status': 'success' if state['extraction_confidence'] > 0 else 'failed'
        }
        
        logger.info(f"Document intelligence agent completed in {duration*1000:.2f}ms")
        return state
    
    def _run_matching(self, state: AgentState) -> AgentState:
        """Run matching agent with timing"""
        logger.info("Running matching agent")
        start = time.time()
        state = self.matching_agent.run(state)
        duration = time.time() - start
        
        state['agent_execution_trace']['matching_agent'] = {
            'duration_ms': duration * 1000,
            'confidence': state['matching_results'].po_match_confidence if state.get('matching_results') else 0.0,
            'status': 'success'
        }
        
        logger.info(f"Matching agent completed in {duration*1000:.2f}ms")
        return state
    
    def _run_discrepancy(self, state: AgentState) -> AgentState:
        """Run discrepancy detection with timing"""
        logger.info("Running discrepancy detection agent")
        start = time.time()
        state = self.discrepancy_agent.run(state)
        duration = time.time() - start
        
        state['agent_execution_trace']['discrepancy_detection_agent'] = {
            'duration_ms': duration * 1000,
            'confidence': 0.99,
            'status': 'success'
        }
        
        logger.info(f"Discrepancy detection agent completed in {duration*1000:.2f}ms")
        return state
    
    def _run_resolution(self, state: AgentState) -> AgentState:
        """Run resolution recommendation with timing"""
        logger.info("Running resolution recommendation agent")
        start = time.time()
        state = self.resolution_agent.run(state)
        duration = time.time() - start
        
        state['agent_execution_trace']['resolution_recommendation_agent'] = {
            'duration_ms': duration * 1000,
            'confidence': state['confidence'],
            'status': 'success'
        }
        
        logger.info(f"Resolution recommendation agent completed in {duration*1000:.2f}ms")
        return state
    
    def _route_after_extraction(self, state: AgentState) -> str:
        """Route after extraction based on confidence"""
        if state['extraction_confidence'] < 0.5:
            logger.warning(f"Low extraction confidence ({state['extraction_confidence']:.2%}), escalating")
            return "escalate"
        logger.debug(f"Extraction confidence acceptable ({state['extraction_confidence']:.2%}), proceeding to matching")
        return "matching"
    
    def run(
        self, 
        invoice_path: str, 
        po_db_path: str
    ) -> Dict:
        """Run the complete workflow"""
        
        logger.info("="*60)
        logger.info(f"Processing: {invoice_path}")
        logger.info("="*60)
        
        start_time = time.time()
        
        try:
            # Initialize state
            initial_state = AgentState(
                invoice_file_path=invoice_path,
                po_database_path=po_db_path,
                raw_document=None,
                document_quality="unknown",
                extracted_data=None,
                extraction_confidence=0.0,
                extraction_errors=[],
                matching_results=None,
                matched_po_data=None,
                discrepancies=[],
                total_variance={},
                recommended_action="",
                risk_level="",
                confidence=0.0,
                agent_reasoning="",
                processing_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                processing_duration=0.0,
                agent_execution_trace={},
                current_agent="",
                next_step="",
                should_escalate=False,
                human_feedback=None
            )
            
            # Run workflow
            logger.info("Starting workflow execution")
            final_state = self.workflow.invoke(initial_state)
            
            # Calculate total duration
            final_state['processing_duration'] = time.time() - start_time
            
            logger.info("="*60)
            logger.info(f"Processing complete ({final_state['processing_duration']:.2f}s)")
            logger.info("="*60)
            
            return self._format_output(final_state, invoice_path)
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise AppException(e, sys)
    
    def _format_output(self, state: AgentState, invoice_path: str) -> Dict:
        """Format final output"""
        import os
        
        try:
            output = {
                "invoice_id": state['extracted_data'].invoice_number if state['extracted_data'] else "UNKNOWN",
                "processing_timestamp": state['processing_timestamp'],
                "processing_duration_seconds": state['processing_duration'],
                "document_info": {
                    "filename": os.path.basename(invoice_path),
                    "file_size_kb": os.path.getsize(invoice_path) / 1024,
                    "page_count": 1,
                    "document_quality": state['document_quality']
                },
                "processing_results": {
                    "extraction_confidence": state['extraction_confidence'],
                    "document_quality": state['document_quality'],
                    "extracted_data": state['extracted_data'].model_dump() if state['extracted_data'] else {},
                    "matching_results": state['matching_results'].model_dump() if state.get('matching_results') else {},
                    "discrepancies": [d.model_dump() for d in state['discrepancies']],
                    "recommended_action": state['recommended_action'],
                    "risk_level": state['risk_level'],
                    "confidence": state['confidence'],
                    "agent_reasoning": state['agent_reasoning']
                },
                "agent_execution_trace": state['agent_execution_trace']
            }
            
            logger.debug("Output formatted successfully")
            return output
            
        except Exception as e:
            logger.error(f"Failed to format output: {e}")
            raise AppException(e, sys)


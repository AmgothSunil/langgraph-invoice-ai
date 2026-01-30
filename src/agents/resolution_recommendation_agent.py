# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.graph.state import AgentState
from src.utils.prompt_loader import PromptManager
from src.config.logger import setup_logger
from src.config.exception import AppException
from typing import List
from pathlib import Path
import json
import sys
from dotenv import load_dotenv
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

# Get the prompts directory path
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Initialize logger
logger = setup_logger("ResolutionRecommendationAgent", "resolution_recommendation_agent.log")

class ResolutionRecommendationAgent:
    """Recommends resolution actions"""
    
    def __init__(self):
        try:
            logger.info("Initializing ResolutionRecommendationAgent")
            self.llm = ChatGroq(
                model="openai/gpt-oss-120b", 
                temperature=0.1,
                groq_api_key=groq_api_key
            )
            self.prompt_manager = PromptManager()
            self.prompt = self._create_prompt()
            logger.info("ResolutionRecommendationAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ResolutionRecommendationAgent: {e}")
            raise AppException(e, sys)
    
    def _create_prompt(self) -> ChatPromptTemplate:
        # Load system prompt from external file
        system_prompt = self.prompt_manager.load_prompt(
            str(PROMPTS_DIR / "resolution_recommendation_prompt.txt")
        )
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", """Analyze this invoice processing result:

Extraction Confidence: {extraction_confidence}
Document Quality: {document_quality}
PO Match: {po_match}
PO Match Confidence: {po_confidence}
Discrepancies: {discrepancies}

Provide your recommendation.""")
        ])
    
    def run(self, state: AgentState) -> AgentState:
        """Execute resolution recommendation"""
        logger.info("Resolution Recommendation Agent: Analyzing...")
        
        try:
            # Prepare context
            discrepancy_summary = self._summarize_discrepancies(
                state['discrepancies']
            )
            
            logger.debug(f"Discrepancy summary: {discrepancy_summary}")
            
            response = self.llm.invoke(
                self.prompt.format_messages(
                    extraction_confidence=state['extraction_confidence'],
                    document_quality=state['document_quality'],
                    po_match=state['matching_results'].matched_po if state.get('matching_results') else "None",
                    po_confidence=state['matching_results'].po_match_confidence if state.get('matching_results') else 0.0,
                    discrepancies=discrepancy_summary
                )
            )
            
            try:
                result = json.loads(response.content)
                
                state['recommended_action'] = result['recommended_action']
                state['risk_level'] = result['risk_level']
                state['confidence'] = result['confidence']
                state['agent_reasoning'] = result['agent_reasoning']
                
                logger.info(f"Recommendation: {result['recommended_action']} (risk: {result['risk_level']})")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse recommendation JSON: {e}")
                state['recommended_action'] = 'escalate_to_human'
                state['risk_level'] = 'high'
                state['confidence'] = 0.0
                state['agent_reasoning'] = "Failed to generate recommendation"
            
            state['current_agent'] = 'resolution'
            state['next_step'] = 'end'
            
            return state
            
        except Exception as e:
            logger.error(f"Resolution recommendation failed: {e}")
            state['recommended_action'] = 'escalate_to_human'
            state['risk_level'] = 'high'
            state['confidence'] = 0.0
            state['agent_reasoning'] = f"Error during recommendation: {str(e)}"
            state['current_agent'] = 'resolution'
            state['next_step'] = 'end'
            return state
    
    def _summarize_discrepancies(self, discrepancies: List) -> str:
        """Summarize discrepancies for LLM"""
        if not discrepancies:
            return "None"
        
        summary = []
        for d in discrepancies:
            summary.append(f"- {d.type} ({d.severity}): {d.details}")
        
        return "\n".join(summary)


# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.graph.state import AgentState
from typing import List
import json
from dotenv import load_dotenv
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

class ResolutionRecommendationAgent:
    """Recommends resolution actions"""
    
    def __init__(self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b", 
            temperature=0.1,
            groq_api_key=groq_api_key
        )
        self.prompt = self._create_prompt()
    
    def _create_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a senior financial analyst making invoice approval decisions.

Decision criteria:
- AUTO_APPROVE: High confidence extraction (≥90%), exact PO match, no discrepancies or only minor (<2%) variances
- FLAG_FOR_REVIEW: Medium confidence (70-89%), minor discrepancies (5-15% price variance), missing PO with good fuzzy match
- ESCALATE_TO_HUMAN: Low confidence (<70%), major discrepancies (>15% variance), no PO match, multiple issues

Provide:
1. recommended_action: auto_approve | flag_for_review | escalate_to_human
2. risk_level: none | low | medium | high | critical
3. confidence: 0.0-1.0
4. detailed reasoning explaining your decision

Return ONLY valid JSON:
{{
  "recommended_action": "string",
  "risk_level": "string",
  "confidence": float,
  "agent_reasoning": "string"
}}"""),
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
        print("📋 Resolution Recommendation Agent: Analyzing...")
        
        # Prepare context
        discrepancy_summary = self._summarize_discrepancies(
            state['discrepancies']
        )
        
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
            
            print(f"✅ Recommendation: {result['recommended_action']} (risk: {result['risk_level']})")
            
        except json.JSONDecodeError:
            print("❌ Failed to parse recommendation")
            state['recommended_action'] = 'escalate_to_human'
            state['risk_level'] = 'high'
            state['confidence'] = 0.0
            state['agent_reasoning'] = "Failed to generate recommendation"
        
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

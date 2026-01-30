"""
Streamlit Frontend for Invoice Reconciliation System

Features:
- Upload invoice PDFs
- Upload purchase order JSON
- View processing results with status badges
- Display discrepancies and recommendations
- Chat with AI agent for clarification
"""

import streamlit as st
import requests
import json
from pathlib import Path
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="LangGraph Invoice AI",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Clean Off-White Theme for Better Readability
st.markdown("""
<style>
    /* Main background - Clean Off-White */
    .stApp {
        background: #F8F9FA;
    }
    
    /* Main content area */
    .main .block-container {
        background: #FFFFFF;
        border-radius: 15px;
        padding: 2rem 3rem;
        margin-top: 1rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        border: 1px solid #E9ECEF;
    }
    
    /* Headers */
    h1 {
        color: #1e3a5f !important;
        font-size: 2.5rem !important;
        font-weight: 700 !important;
    }
    
    h2 {
        color: #2d4a6f !important;
        font-size: 1.8rem !important;
        font-weight: 600 !important;
    }
    
    h3 {
        color: #3d5a80 !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
    }
    
    /* Regular text - Larger font */
    p, .stMarkdown, .stText {
        font-size: 1.1rem !important;
        color: #2c3e50 !important;
        line-height: 1.6 !important;
    }
    
    /* Status badges */
    .status-passed {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
    }
    .status-review {
        background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);
    }
    .status-escalate {
        background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
    }
    .status-error {
        background: linear-gradient(135deg, #6B7280 0%, #4B5563 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
    }
    
    /* Metrics */
    .stMetric {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }
    
    .stMetric label {
        font-size: 1rem !important;
        color: #64748b !important;
        font-weight: 500 !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        color: #1e3a5f !important;
        font-weight: 700 !important;
    }
    
    /* Sidebar - Clean Light Theme */
    .css-1d391kg, [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid #E9ECEF;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #2c3e50 !important;
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #1e3a5f !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #2d4a6f !important;
        background: #f1f5f9 !important;
        border-radius: 10px !important;
    }
    
    /* Info boxes */
    .stAlert {
        font-size: 1.1rem !important;
        border-radius: 12px !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
    }
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #667eea !important;
        border-radius: 15px !important;
        padding: 1rem !important;
    }
    
    /* Chat section */
    .chat-container {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 20px;
        padding: 1.5rem;
        margin-top: 2rem;
        border: 1px solid #e2e8f0;
    }
    
    .chat-message-user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 5px 18px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
        font-size: 1rem;
    }
    
    .chat-message-agent {
        background: white;
        color: #2c3e50;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 5px;
        margin: 8px 0;
        max-width: 80%;
        border: 1px solid #e2e8f0;
        font-size: 1rem;
    }
    
    /* JSON display */
    .stJson {
        font-size: 0.95rem !important;
    }
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_status_badge(status: str) -> str:
    """Get HTML badge for status"""
    badges = {
        "passed": '<span class="status-passed">✅ PASSED - Auto Approved</span>',
        "review": '<span class="status-review">⚠️ REVIEW - Manual Check Required</span>',
        "escalate": '<span class="status-escalate">🚨 ESCALATE - Human Decision Required</span>',
        "error": '<span class="status-error">❌ ERROR - Processing Failed</span>'
    }
    return badges.get(status, status)


def chat_with_agent(query: str, context: dict = None, chat_history: list = None) -> str:
    """Chat with the AI agent for clarifications - with memory support"""
    try:
        from langchain_groq import ChatGroq
        
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return "⚠️ API key not configured. Please set GROQ_API_KEY in .env file."
        
        # Initialize LLM (cached in session for efficiency)
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            groq_api_key=groq_api_key
        )
        
        # Build context message from invoice results
        context_str = ""
        if context and 'last_result' in context:
            result = context['last_result']
            context_str = f"""
            Current invoice processing result:
            - Invoice ID: {result.get('invoice_id', 'N/A')}
            - Status: {result.get('status', 'N/A')}
            - Confidence: {result.get('confidence', 0):.1%}
            - Risk Level: {result.get('risk_level', 'N/A')}
            - Discrepancies: {result.get('discrepancies_count', 0)}
            - Reasoning: {result.get('agent_reasoning', 'N/A')}
            """
        
        system_prompt = f"""You are an AI assistant for the Invoice Reconciliation System. 
        Help users understand invoice processing results, discrepancies, and recommended actions.
        Be concise and helpful. Use simple language.
        Remember the conversation history and refer to previous messages when relevant.
        
        {context_str}
        """
        
        # Build messages with conversation history (memory)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history for memory
        if chat_history:
            for msg in chat_history[-10:]:  # Last 10 messages for context
                if msg['role'] == 'user':
                    messages.append({"role": "user", "content": msg['content']})
                else:
                    messages.append({"role": "assistant", "content": msg['content']})
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def main():
    # Header
    st.title("🧾 LangGraph Invoice AI")
    st.markdown("### AI-Powered Invoice Reconciliation System")
    
    # Check API connection
    api_status = check_api_health()
    if api_status:
        st.sidebar.success("🟢 API Connected")
    else:
        st.sidebar.error("🔴 API Offline")
        st.warning("⚠️ Please start the FastAPI server: `uvicorn app:app --reload --port 8000`")
        return
    
    # Sidebar
    st.sidebar.title("📁 File Management")
    
    # Purchase Orders Upload
    st.sidebar.markdown("### 📋 Purchase Orders")
    po_file = st.sidebar.file_uploader(
        "Upload PO Database (JSON)",
        type=["json"],
        help="Upload your purchase orders JSON file"
    )
    
    if po_file:
        if st.sidebar.button("📤 Upload PO Database", width="stretch"):
            with st.spinner("Uploading purchase orders..."):
                files = {"file": (po_file.name, po_file.getvalue(), "application/json")}
                response = requests.post(f"{API_BASE_URL}/api/upload-po", files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    st.sidebar.success(f"✅ Uploaded {result['po_count']} purchase orders")
                else:
                    st.sidebar.error(f"❌ Upload failed")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("## 📄 Process Invoices")
        
        # Multiple Invoice Upload
        invoice_files = st.file_uploader(
            "Upload Invoice PDFs (Multiple Allowed)",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload one or more invoice PDFs to process"
        )
        
        # Process Button
        if invoice_files:
            st.info(f"📁 {len(invoice_files)} file(s) selected")
            
            if st.button("🚀 Process All Invoices", type="primary", use_container_width=True):
                # Initialize results storage
                if 'all_results' not in st.session_state:
                    st.session_state['all_results'] = []
                
                st.session_state['all_results'] = []
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, invoice_file in enumerate(invoice_files):
                    status_text.text(f"🔄 Processing {invoice_file.name}... ({idx+1}/{len(invoice_files)})")
                    
                    files = {"invoice": (invoice_file.name, invoice_file.getvalue(), "application/pdf")}
                    
                    try:
                        response = requests.post(f"{API_BASE_URL}/api/process-invoice", files=files)
                        
                        if response.status_code == 200:
                            result = response.json()
                            result['filename'] = invoice_file.name
                            st.session_state['all_results'].append(result)
                        else:
                            st.session_state['all_results'].append({
                                'filename': invoice_file.name,
                                'status': 'error',
                                'error': 'Processing failed'
                            })
                    except Exception as e:
                        st.session_state['all_results'].append({
                            'filename': invoice_file.name,
                            'status': 'error',
                            'error': str(e)
                        })
                    
                    progress_bar.progress((idx + 1) / len(invoice_files))
                
                status_text.text("✅ All invoices processed!")
                
                # Set last result to the first one for detailed view
                if st.session_state['all_results']:
                    st.session_state['last_result'] = st.session_state['all_results'][0]
                
                st.success(f"✅ Processed {len(invoice_files)} invoice(s)")
    
    with col2:
        st.markdown("## 📊 Quick Stats")
        
        try:
            po_response = requests.get(f"{API_BASE_URL}/api/purchase-orders")
            if po_response.status_code == 200:
                po_count = len(po_response.json().get("purchase_orders", []))
                st.metric("📋 Purchase Orders", po_count)
            else:
                st.metric("📋 Purchase Orders", "0")
        except:
            st.metric("📋 Purchase Orders", "N/A")
    # Batch Results Summary (if multiple invoices processed)
    if 'all_results' in st.session_state and len(st.session_state['all_results']) > 0:
        st.markdown("---")
        st.markdown("## 📊 Batch Processing Summary")
        
        # Create summary table
        summary_data = []
        passed = 0
        review = 0
        escalate = 0
        errors = 0
        
        for r in st.session_state['all_results']:
            status = r.get('status', 'error')
            if status == 'passed':
                passed += 1
                status_icon = "✅"
            elif status == 'review':
                review += 1
                status_icon = "⚠️"
            elif status == 'escalate':
                escalate += 1
                status_icon = "🚨"
            else:
                errors += 1
                status_icon = "❌"
            
            summary_data.append({
                "File": r.get('filename', 'Unknown'),
                "Status": f"{status_icon} {status.upper()}",
                "Invoice ID": r.get('invoice_id', 'N/A'),
                "Confidence": f"{r.get('confidence', 0):.1%}" if r.get('confidence') else 'N/A',
                "Risk": r.get('risk_level', 'N/A').upper() if r.get('risk_level') else 'N/A',
                "Discrepancies": r.get('discrepancies_count', 0)
            })
        
        # Show summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("✅ Passed", passed)
        with col2:
            st.metric("⚠️ Review", review)
        with col3:
            st.metric("🚨 Escalate", escalate)
        with col4:
            st.metric("❌ Errors", errors)
        
        # Show results table
        import pandas as pd
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Select invoice for detailed view
        st.markdown("### 🔍 View Detailed Results")
        selected_file = st.selectbox(
            "Select invoice for details:",
            options=[r.get('filename', 'Unknown') for r in st.session_state['all_results']]
        )
        
        # Update last_result based on selection
        for r in st.session_state['all_results']:
            if r.get('filename') == selected_file:
                st.session_state['last_result'] = r
                break
    
    # Results Section
    if 'last_result' in st.session_state:
        result = st.session_state['last_result']
        
        st.markdown("---")
        st.markdown(f"## 📋 Detailed Results: {result.get('filename', result.get('invoice_id', 'Invoice'))}")
        
        # Status Badge
        st.markdown(get_status_badge(result['status']), unsafe_allow_html=True)
        st.markdown("")  # Spacing
        
        # Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🔖 Invoice ID", result.get('invoice_id', 'N/A'))
        
        with col2:
            confidence = result.get('confidence', 0)
            st.metric("📈 Confidence", f"{confidence:.1%}")
        
        with col3:
            st.metric("⚡ Risk Level", result.get('risk_level', 'N/A').upper())
        
        with col4:
            st.metric("⚠️ Discrepancies", result.get('discrepancies_count', 0))
        
        # Agent Reasoning
        if result.get('agent_reasoning'):
            st.markdown("### 🤖 AI Reasoning")
            st.info(result['agent_reasoning'])
        
        # Discrepancies
        details = result.get('details', {})
        discrepancies = details.get('processing_results', {}).get('discrepancies', [])
        
        if discrepancies:
            st.markdown("### ⚠️ Discrepancies Found")
            
            for i, disc in enumerate(discrepancies):
                severity_color = "🔴" if disc.get('severity') == 'high' else "🟡" if disc.get('severity') == 'medium' else "🟢"
                with st.expander(f"{severity_color} Discrepancy {i+1}: {disc.get('type', 'Unknown').replace('_', ' ').title()}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**📌 Field:** `{disc.get('field', 'N/A')}`")
                        st.markdown(f"**📄 Invoice Value:** `{disc.get('invoice_value', 'N/A')}`")
                        st.markdown(f"**📋 PO Value:** `{disc.get('po_value', 'N/A')}`")
                    with col2:
                        variance = disc.get('variance_percentage')
                        if variance:
                            st.markdown(f"**📊 Variance:** `{variance:.2f}%`")
                        st.markdown(f"**🔧 Action:** `{disc.get('recommended_action', 'N/A')}`")
                    
                    st.markdown(f"**📝 Details:** {disc.get('details', 'No details')}")
        
        # Extracted Data
        with st.expander("📄 Extracted Invoice Data"):
            extracted = details.get('processing_results', {}).get('extracted_data', {})
            if extracted:
                st.json(extracted)
            else:
                st.write("No extracted data available")
        
        # Matching Results
        with st.expander("🔗 PO Matching Results"):
            matching = details.get('processing_results', {}).get('matching_results', {})
            if matching:
                st.json(matching)
            else:
                st.write("No matching results available")
    
    # Chat Section
    st.markdown("---")
    st.markdown("## 💬 Chat with AI Agent")
    st.markdown("*Ask questions about the invoice processing results or get clarifications. The agent remembers your conversation!*")
    
    # Initialize chat history in session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Chat messages container with fixed height
    chat_container = st.container(height=400)
    
    with chat_container:
        # Display chat history using Streamlit's chat components
        for message in st.session_state.chat_history:
            if message['role'] == 'user':
                with st.chat_message("user", avatar="👤"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(message["content"])
    
    # Chat input - this doesn't cause full page rerun
    if user_input := st.chat_input("Ask about invoice results, discrepancies, or recommendations..."):
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Display user message immediately
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.write(user_input)
        
        # Get agent response WITH memory (pass chat history)
        with st.spinner("🤔 Thinking..."):
            context = {"last_result": st.session_state.get('last_result', {})}
            response = chat_with_agent(
                user_input, 
                context, 
                chat_history=st.session_state.chat_history  # Pass memory!
            )
        
        # Add agent response to history
        st.session_state.chat_history.append({"role": "agent", "content": response})
        
        # Display agent response
        with chat_container:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(response)
        
        # Minimal rerun to update UI
        st.rerun()
    
    # Clear chat button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #64748B; font-size: 1rem;'>
            <p>🧾 LangGraph Invoice AI v1.0 | Built with ❤️ using LangGraph + FastAPI + Streamlit</p>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

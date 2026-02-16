import streamlit as st
import os
import operator
import io
import json
from typing import Annotated, List, TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from docx import Document
from pypdf import PdfReader  # Required: pip install pypdf

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(
    page_title="Deep Intelligence Orchestrator", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ADVANCED CSS ---
st.markdown("""
    <style>
    :root {
        --primary: #3b82f6;
        --bg-dark: #0f172a;
        --glass-bg: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.1);
        --text-main: #f1f5f9;
        --text-muted: #94a3b8;
    }
    * { transition: all 0.3s ease; }
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: var(--text-main);
    }
    .report-card {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }
    .report-card:hover {
        transform: translateY(-5px);
        border-color: var(--primary);
    }
    .section-title {
        color: var(--primary);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 8px;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in { animation: fadeIn 0.8s forwards; }
    
    /* File Uploader Styling */
    section[data-testid="stFileUploadDropzone"] {
        background: var(--glass-bg);
        border: 1px dashed var(--glass-border);
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DOMAIN-SPECIFIC DEEP PROMPTS ---
PROMPT_SOP = {
    "Section 1: Account Business Overview": """
        Persona: Lead Financial Analyst.
        Focus: Fundamental identity and regulatory posture of {company}.
        Requirements:
        1. Exact legal entity name and FDIC Certificate details.
        2. Scalability metrics: FY2024 Assets, Deposits, and Loans.
        3. Regulatory signals: Primary regulator and charter classification.
        Citations: Every metric must be cited as.
    """,
    "Section 2: Key Business Initiatives": """
        Persona: Strategic Strategy Principal.
        Focus: Operational optimization and strategic catalysts.
        Requirements:
        1. Profitability levers: Net interest margin and efficiency goals.
        2. Growth vectors: M&A activity and footprint expansion.
        3. Modernization: Information Services and digital delivery mandates.
        Citations: Connect goals to sources with.
    """,
    "Section 3: Account Tech Landscape": """
        Persona: Chief Technology Architect.
        Focus: Infrastructure, partners, and technical ecosystems.
        Requirements:
        1. Core Digital: Online Banking and Mobile Deposit platforms.
        2. Treasury Engine: Positive Pay, ACH controls, and RDC.
        3. Partner Edge: Integrations with Elan, Autobooks, and Celero.
        Citations: Link technical specs to sources with.
    """,
    "Section 4: Relationship & Stakeholders": """
        Persona: Executive Intelligence Lead.
        Focus: Hierarchy and governance structure.
        Requirements:
        1. C-Suite alignment: CEO, CIO, and CCBO focus areas.
        2. Board Governance: Key committees (Audit, Compliance).
        3. Influence map: Key decision-makers for partner-led work.
        Citations: Reference leadership bios with.
    """,
    "Section 5: Strategic Next Steps": """
        Persona: Solutions Director.
        Focus: Actionable roadmap for partner alignment.
        Requirements:
        1. Friction points: Identification of manual workflow bottlenecks.
        2. Playbooks: Repeatable integration and automation opportunities.
        3. Engagement: 30-day tactical hooks for senior stakeholders.
        Citations: Support recommendations with findings using.
    """
}

# --- 4. MULTI-AGENT ANALYTICS ENGINE ---
class SectionState(TypedDict):
    section_name: str
    target_company: str
    pdf_context: str

class OverallState(TypedDict):
    target_company: str
    pdf_context: str
    research_data: Annotated[List[dict], operator.add]
    source_urls: Annotated[List[str], operator.add]
    final_report: str

def get_llm():
    return ChatAnthropic(model="claude-3-5-sonnet-latest", anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"])

def get_search():
    return TavilySearchResults(max_results=6, tavily_api_key=st.secrets["TAVILY_API_KEY"])

def planner(state: OverallState):
    return [Send("researcher", {
        "section_name": s, 
        "target_company": state['target_company'],
        "pdf_context": state['pdf_context']
    }) for s in PROMPT_SOP.keys()]

def researcher(state: SectionState):
    search_tool = get_search()
    llm = get_llm()
    query = f"{state['target_company']} {state['section_name']} report 2024-2026"
    results = search_tool.invoke(query)
    
    urls = [r['url'] for r in results]
    web_context = "\n".join([f"Source [{i+1}]: {r['content']} (URL: {r['url']})" for i, r in enumerate(results)])
    
    system_msg = f"""You are a specialized intelligence agent. Follow the SOP strictly. 
    Use the provided PDF CONTENT as your primary 'Ground Truth' source. 
    Cross-reference with WEB SEARCH DATA for the latest updates.
    Citations are MANDATORY in format.
    
    {PROMPT_SOP[state['section_name']].format(company=state['target_company'])}"""
    
    user_msg = f"""
    TARGET COMPANY: {state['target_company']}

    --- PDF CONTENT (Primary Source) ---
    {state['pdf_context'][:15000]} 

    --- WEB SEARCH DATA (Secondary Source) ---
    {web_context}
    """
    
    response = llm.invoke([("system", system_msg), ("user", user_msg)])
    return {
        "research_data": [{"section": state['section_name'], "content": response.content}],
        "source_urls": urls
    }

def writer(state: OverallState):
    sorted_data = sorted(state['research_data'], key=lambda x: x['section'])
    report = f"# STRATEGIC ANALYSIS: {state['target_company']}\n\n"
    for item in sorted_data:
        report += f"## {item['section']}\n{item['content']}\n\n"
    
    report += "\n# References\n"
    for i, url in enumerate(list(dict.fromkeys(state['source_urls']))):
        report += f"[{i+1}] {url}\n"
    return {"final_report": report}

# Graph Construction
builder = StateGraph(OverallState)
builder.add_node("planner", planner); builder.add_node("researcher", researcher); builder.add_node("writer", writer)
builder.set_entry_point("planner"); builder.add_conditional_edges("planner", lambda x: x)
builder.add_edge("researcher", "writer"); builder.add_edge("writer", END)
graph = builder.compile()

# --- 5. UI ORCHESTRATION ---
st.title("Strategic Intelligence Orchestrator")
st.markdown("<p style='color: var(--text-muted); margin-top:-1rem;'>Autonomous Multi-Agent Enterprise Research with PDF Ground-Truth</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='padding-top:20px;'></div>", unsafe_allow_html=True)
    st.markdown("### Research Parameters")
    target_name = st.text_input("Target Account", placeholder="e.g. First Northern Bank")
    
    # PDF Upload Logic
    uploaded_file = st.file_uploader("Upload Annual Report (PDF)", type="pdf")
    
    st.divider()
    execute = st.button("EXECUTE ANALYSIS", type="primary", use_container_width=True)

if execute and target_name:
    # PDF Processing Logic
    extracted_text = "No PDF provided."
    if uploaded_file:
        with st.spinner("Processing Annual Report..."):
            reader = PdfReader(uploaded_file)
            extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

    output_container = st.container()
    progress_status = st.status("Orchestrating Agents...", expanded=True)
    
    initial_state = {
        "target_company": target_name, 
        "pdf_context": extracted_text,
        "research_data": [], 
        "source_urls": []
    }
    
    final_report_text = ""
    for event in graph.stream(initial_state):
        for node, output in event.items():
            if node == "researcher":
                data = output["research_data"][0]
                progress_status.write(f"Section Completed: {data['section']}")
                with output_container:
                    st.markdown(f"""
                    <div class="report-card animate-in">
                        <div class="section-title">{data['section']}</div>
                        {data['content']}
                    </div>
                    """, unsafe_allow_html=True)
            if node == "writer":
                final_report_text = output["final_report"]

    progress_status.update(label="Analysis Finalized", state="complete", expanded=False)

    # DOCX Export
    doc = Document()
    for line in final_report_text.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], level=0)
        elif line.startswith('## '): doc.add_heading(line[3:], level=1)
        elif line.strip(): doc.add_paragraph(line)
            
    buf = io.BytesIO()
    doc.save(buf); buf.seek(0)
    
    st.sidebar.download_button(
        "DOWNLOAD DOCX REPORT", 
        data=buf, 
        file_name=f"{target_name}_Plan.docx",
        use_container_width=True
    )

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

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(
    page_title="Deep Intelligence Orchestrator", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ADVANCED CSS FOR MODERN UI ---
st.markdown("""
    <style>
    /* Professional Dark Theme Palette */
    :root {
        --primary: #3b82f6;
        --bg-dark: #0f172a;
        --glass-bg: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.1);
        --text-main: #f1f5f9;
        --text-muted: #94a3b8;
    }

    /* Global Transitions */
    * { transition: all 0.3s ease; }

    /* Main Container Styling */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: var(--text-main);
    }

    /* Modern 3D Glassmorphism Card */
    .report-card {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
        transform: translateZ(0);
    }
    
    .report-card:hover {
        transform: translateY(-5px) scale(1.01);
        box-shadow: 0 20px 40px -15px rgba(0,0,0,0.6);
        border-color: var(--primary);
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }

    .section-title {
        color: var(--primary);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 8px;
    }

    /* Smooth Fade-in Animation */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .animate-in {
        animation: fadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }

    /* Hide Streamlit Default Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border-right: 1px solid var(--glass-border);
    }

    /* Professional Button */
    .stButton>button {
        background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    
    .stButton>button:hover {
        box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4);
        transform: translateY(-2px);
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

class OverallState(TypedDict):
    target_company: str
    research_data: Annotated[List[dict], operator.add]
    source_urls: Annotated[List[str], operator.add]
    final_report: str

def get_llm():
    return ChatAnthropic(model="claude-3-5-sonnet-latest", anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"])

def get_search():
    return TavilySearchResults(max_results=6, tavily_api_key=st.secrets["TAVILY_API_KEY"])

def planner(state: OverallState):
    return [Send("researcher", {"section_name": s, "target_company": state['target_company']}) for s in PROMPT_SOP.keys()]

def researcher(state: SectionState):
    search_tool = get_search()
    llm = get_llm()
    query = f"{state['target_company']} {state['section_name']} report 2024-2026"
    results = search_tool.invoke(query)
    
    urls = [r['url'] for r in results]
    context = "\n".join([f"Source [{i+1}]: {r['content']} (URL: {r['url']})" for i, r in enumerate(results)])
    
    system_msg = f"You are a specialized intelligence agent. Follow the SOP and use for every claim.\n\n{PROMPT_SOP[state['section_name']].format(company=state['target_company'])}"
    user_msg = f"Data for {state['target_company']}:\n\n{context}"
    
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
st.markdown("<p style='color: var(--text-muted); margin-top:-1rem;'>Autonomous Multi-Agent Enterprise Research</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='padding-top:20px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-bottom:0;'>Parameters</h3>", unsafe_allow_html=True)
    target_name = st.text_input("Target Account", placeholder="e.g. First Northern Bank")
    st.divider()
    execute = st.button("RUN DEEP RESEARCH", use_container_width=True)

if execute and target_name:
    output_container = st.container()
    progress_status = st.status("Initializing Agents...", expanded=True)
    
    initial_state = {"target_company": target_name, "research_data": [], "source_urls": []}
    
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

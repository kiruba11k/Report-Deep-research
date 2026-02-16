import os
import io
from typing import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
from docx import Document
from pypdf import PdfReader
import streamlit as st
# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(
    page_title="Deep Intelligence Orchestrator", 
    page_icon="", 
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

class OverallState(TypedDict):
    target_company: str
    pdf_context: str
    remaining_sections: list
    completed_research: list # We will append manually
    all_urls: list
    final_report: str


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
def get_llm():
    return ChatAnthropic(model="claude-3-5-sonnet-latest", anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"])

def initializer(state: OverallState):
    """Starts the process by listing what needs to be researched."""
    return {
        "remaining_sections": list(PROMPT_SOP.keys()),
        "completed_research": [],
        "all_urls": []
    }

def researcher_node(state: OverallState):
    """Researches the next section in the list."""
    if not state["remaining_sections"]:
        return state

    current_section = state["remaining_sections"][0]
    llm = get_llm()
    search_tool = TavilySearchResults(max_results=3, tavily_api_key=st.secrets["TAVILY_API_KEY"])
    
    # 1. Search
    query = f"{state['target_company']} {current_section} 2024 2025"
    try:
        web_results = search_tool.invoke(query)
        urls = [r.get('url', '') for r in web_results]
        web_context = "\n".join([r.get('content', '') for r in web_results])
    except:
        urls, web_context = [], "Web search failed."

    # 2. LLM Analysis
    sys_prompt = PROMPT_SOP[current_section].replace("{company}", state['target_company'])
    user_msg = f"PDF Context: {state['pdf_context'][:8000]}\nWeb Context: {web_context}"
    
    response = llm.invoke([("system", sys_prompt), ("user", user_msg)])
    
    # 3. Update state manually (Standard Python List Addition)
    return {
        "completed_research": state["completed_research"] + [{"section": current_section, "content": response.content}],
        "all_urls": state["all_urls"] + urls,
        "remaining_sections": state["remaining_sections"][1:] # Pop the section we just did
    }

def router(state: OverallState):
    """Checks if there are more sections to research."""
    return "researcher" if state["remaining_sections"] else "writer"

def writer_node(state: OverallState):
    """Finalizes the report."""
    report = f"# STRATEGIC ANALYSIS: {state['target_company']}\n\n"
    for item in state["completed_research"]:
        report += f"## {item['section']}\n{item['content']}\n\n"
    
    report += "\n# References\n"
    for url in list(set(state["all_urls"])):
        report += f"- {url}\n"
    return {"final_report": report}    
# Graph Construction
workflow = StateGraph(OverallState)

workflow.add_node("initializer", initializer)
workflow.add_node("researcher", researcher_node)
workflow.add_node("writer", writer_node)

workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "researcher")

# This loop ensures we research one by one without triggering parallel merge errors
workflow.add_conditional_edges(
    "researcher",
    router,
    {"researcher": "researcher", "writer": "writer"}
)

workflow.add_edge("writer", END)
app = workflow.compile()

# --- 5. UI ORCHESTRATION ---
st.title("Strategic Intelligence Orchestrator")
st.markdown("<p style='color: var(--text-muted); margin-top:-1rem;'>Autonomous Multi-Agent Enterprise Research with PDF Ground-Truth</p>", unsafe_allow_html=True)

target_name = st.sidebar.text_input("Target Account")
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")
execute = st.sidebar.button("EXECUTE ANALYSIS")

if execute and target_name:
    text = ""
    if uploaded_file:
        reader = PdfReader(uploaded_file)
        text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])

    initial_state = {
        "target_company": target_name,
        "pdf_context": text,
        "remaining_sections": [],
        "completed_research": [],
        "all_urls": [],
        "final_report": ""
    }

    container = st.container()
    status = st.status("Orchestrating Research...")
    
    final_text = ""
    for event in app.stream(initial_state):
        for node, output in event.items():
            if node == "researcher" and "completed_research" in output:
                latest = output["completed_research"][-1]
                status.write(f"✅ Completed: {latest['section']}")
                container.markdown(f"### {latest['section']}")
                container.write(latest['content'])
            if node == "writer":
                final_text = output["final_report"]

    status.update(label="Analysis Finished", state="complete")
    
    # Export
    doc = Document()
    for line in final_text.split('\n'):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    st.download_button("Download DOCX", buf.getvalue(), f"{target_name}_Report.docx")

import os
import io
import re
import streamlit as st
from typing import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
from docx import Document
from pypdf import PdfReader
from docx.oxml.shared import OxmlElement, qn
from docx.opc.constants import RELATIONSHIP_TYPE

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(
    page_title="Deep Intelligence Orchestrator", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. THEME CSS ---
st.markdown("""
    <style>
    :root { --primary: #3b82f6; --text-main: #f1f5f9; }
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: var(--text-main); }
    </style>
    """, unsafe_allow_html=True)

class OverallState(TypedDict):
    target_company: str
    pdf_context: str
    remaining_sections: list
    completed_research: list
    all_urls: list
    final_report: str

# --- 3. DYNAMIC DOMAIN PROMPTS ---
# Removed LinkedIn and Stakeholder tables. Focused on verified facts and strategic fit.
PROMPT_SOP = {
    "Section 1: Account Business Overview": """
        Act as a Senior Banking Analyst. Analyze {company}. 
        Use the following structure:
        1.1 Identity: Holding company, ticker, founding date, FDIC Cert #.
        1.2 Regulatory: HQ, primary federal regulator, charter signal.
        1.3 Scale (FY2024/25): Assets, Deposits, Loans, and Stockholders’ equity.
        1.4 Performance: Net Income, ROAA%, ROAE%, and YoY Growth (2024 vs 2023).
        1.5 Business Lines: Publicly emphasized lending and wealth focus.
        
        STYLING: Use '●' for points. End every fact with [ref](URL).
    """,

    "Section 2: Account Key Business Initiatives": """
        Act as a Strategic Advisor. Identify 5 core strategic priorities for {company} based on 2024/2025 earnings calls or news.
        Structure:
        2.1 Executive Synthesis: What are they optimizing for? (e.g. Operating Leverage, M&A).
        2.2 Initiative Portfolio: Specific programs (e.g. digital mortgage, branch expansion).
        2.3 KPI Watchlist: What metrics are they tracking?
        
        STYLING: Use [ref](URL) for every initiative from the search results.
    """,

    "Section 4: Speridian Account Relationship": """
        Act as a Sales Director. Map Speridian’s expertise to {company}.
        1. Analysis: Identify where Speridian fits (Digital Transformation, Cloud, or Data).
        2. Play 1 & Play 2: Define two specific service "Plays" based on the bank's tech gaps or scale.
        *IMPORTANT: DO NOT include LinkedIn URLs, personal contact tables, or stakeholder maps.*
    """,

    "Section 3: Account Tech Landscape": """
        Act as a Fintech Architect. Map the bank's digital stack.
        3.1 Channels: Mobile features, Card controls, and Digital access.
        3.2 Treasury/Workflows: RDC, Positive Pay, and ACH capabilities.
        3.3 Partnerships: Core provider (FIS/Fiserv/Jack Henry) and fintech partners.
        
        STYLING: Use [ref](URL) to verify vendor partnerships or app features.
    """,

    "Section 5: Next Steps and Funding Signals": """
        Act as a Managing Director. Identify 5 "Budget Triggers" for {company}.
        Identify specific signals like: New leadership, M&A activity, efficiency ratio targets, or recent capital raises.
        Explain WHY these signals link to a services need (e.g., modernizing for scale).
        
        STYLING: Every signal must be backed by a [ref](URL).
    """
}

# --- 4. ENGINE LOGIC ---
def get_llm():
    return ChatAnthropic(
        model="claude-3-haiku-latest", 
        anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"],
        temperature=0
    )

def researcher_node(state: OverallState):
    if not state["remaining_sections"]:
        return state

    current_section = state["remaining_sections"][0]
    llm = get_llm()
    
    # --- DOMAIN PRIORITIZATION LOGIC ---
    # We define high-authority banking & fintech domains
    fintech_domains = [
        "americanbanker.com", 
        "fintechnexus.com", 
        "finextra.com", 
        "bankingdive.com", 
        "fintechfutures.com",
        "bankautomationnews.com",
        "fdic.gov",
        "sec.gov"
    ]
    
    search_tool = TavilySearchResults(
        max_results=5, 
        tavily_api_key=st.secrets["TAVILY_API_KEY"],
        # New: Use Tavily's domain filtering capabilities
        include_domains=fintech_domains if "Tech" in current_section or "Business" in current_section else None
    )
    
    # Search Query Enhancement
    if "Tech Landscape" in current_section:
        query = f"{state['target_company']} core banking provider FIS Fiserv Jack Henry platform digital transformation"
    elif "Business Overview" in current_section:
        query = f"{state['target_company']} investor relations annual report 2024 2025 assets"
    else:
        query = f"{state['target_company']} {current_section} 2025 news"

    try:
        web_results = search_tool.invoke(query)
        urls = [r.get('url', '') for r in web_results]
        web_context = "\n".join([f"Source [{r.get('url')}]: {r.get('content')}" for r in web_results])
    except:
        urls, web_context = [], "Web search failed."

    # --- UPDATED STYLING FOR SOURCE REDIRECTION ---
    styling_instruction = """
    STRICT HYPERLINK RULE: 
    - Every claim must end with a clickable [ref](URL).
    - Prioritize deep-links to specific articles rather than homepages.
    - Example: 'The bank utilizes Fiserv DNA for core processing [ref](https://www.americanbanker.com/news/example-article).'
    - DO NOT list raw URLs at the end of the paragraph.
    """

    sys_prompt = f"{PROMPT_SOP[current_section].format(company=state['target_company'])}\n\n{styling_instruction}"
    user_msg = f"PDF Context: {state['pdf_context'][:4000]}\n\nVerified Web Data: {web_context}"
    
    response = llm.invoke([("system", sys_prompt), ("user", user_msg)])
    
    return {
        "completed_research": state["completed_research"] + [{"section": current_section, "content": response.content}],
        "all_urls": state["all_urls"] + urls,
        "remaining_sections": state["remaining_sections"][1:] 
    }
def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
    c = OxmlElement('w:color'); c.set(qn('w:val'), '0000FF'); rPr.append(c)
    new_run.append(rPr)
    text_element = OxmlElement('w:t'); text_element.text = text; new_run.append(text_element)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

def save_report_as_docx(final_text, target_name):
    doc = Document()
    for line in final_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('# '):
            doc.add_heading(line.replace('# ', ''), level=0)
        elif line.startswith('## '):
            doc.add_heading(line.replace('## ', ''), level=1)
        else:
            p = doc.add_paragraph()
            # Split by markdown link pattern [ref](url)
            parts = re.split(r'(\[ref\]\(.*?\))', line)
            for part in parts:
                link_match = re.match(r'\[ref\]\((.*?)\)', part)
                if link_match:
                    url = link_match.group(1)
                    add_hyperlink(p, url, " [ref]")
                else:
                    # Handle bolding inside normal text
                    sub_parts = re.split(r'(\*\*.*?\*\*)', part)
                    for sub in sub_parts:
                        if sub.startswith('**') and sub.endswith('**'):
                            p.add_run(sub.replace('**', '')).bold = True
                        else:
                            p.add_run(sub)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

# --- 5. GRAPH SETUP ---
workflow = StateGraph(OverallState)
workflow.add_node("initializer", lambda x: {"remaining_sections": list(PROMPT_SOP.keys()), "completed_research": [], "all_urls": []})
workflow.add_node("researcher", researcher_node)
workflow.add_node("writer", lambda x: {"final_report": "\n\n".join([f"## {i['section']}\n{i['content']}" for i in x['completed_research']])})

workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "researcher")
workflow.add_conditional_edges("researcher", lambda x: "researcher" if x["remaining_sections"] else "writer", {"researcher": "researcher", "writer": "writer"})
workflow.add_edge("writer", END)
app = workflow.compile()

# --- 6. UI ---
st.title("Strategic Intelligence Orchestrator")
target_name = st.sidebar.text_input("Target Bank Name")
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

if st.sidebar.button("EXECUTE ANALYSIS") and target_name:
    pdf_text = ""
    if uploaded_file:
        pdf_text = "\n".join([p.extract_text() for p in PdfReader(uploaded_file).pages if p.extract_text()])

    initial_state = {"target_company": target_name, "pdf_context": pdf_text, "remaining_sections": [], "completed_research": [], "all_urls": [], "final_report": ""}

    with st.status("Analyzing Bank Intelligence...") as status:
        final_text = ""
        for event in app.stream(initial_state):
            for node, output in event.items():
                if node == "researcher":
                    latest = output["completed_research"][-1]
                    status.write(f"Completed: {latest['section']}")
                    st.markdown(f"### {latest['section']}")
                    st.write(latest['content'])
                if node == "writer":
                    final_text = output["final_report"]

    docx_bytes = save_report_as_docx(final_text, target_name)
    st.download_button(label="Download Strategic Report (DOCX)", data=docx_bytes, file_name=f"Speridian_Analysis_{target_name}.docx")

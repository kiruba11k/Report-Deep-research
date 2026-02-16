import os
import io
from typing import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
from docx import Document
from pypdf import PdfReader
import streamlit as st
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.shared import OxmlElement, qn
from docx.opc.constants import RELATIONSHIP_TYPE
from docx import Document
import docx.oxml.shared as shared
from docx.oxml.shared import OxmlElement, qn
from docx.opc.constants import RELATIONSHIP_TYPE

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
        Act as a professional banking analyst. Use the following EXACT structure and styling:
        
        Section 1: Account Business Overview
        1.1 Who they are
        ● **Who they are:** [Detailed description including holding company and ticker] ref
        ● **Founded:** [Founding date and FDIC record] ref
        ● **Footprint (publicly stated):** [Marketing/Branch count details] ref
        ● **FDIC locations count:** [Regulatory count from BankFind] ref
        
        1.2 Headquarters and regulator signals
        ● **HQ / base (FDIC record):** [Address] ref
        ● **HQ / base (investor profile):** [Address] ref
        ● **Primary federal regulator:** [Regulator Name] ref
        ● **Charter signal:** [State/Federal classification] ref
        ● **FDIC certificate:** Cert #[Number] ref
        
        1.3 Deposit insurance
        ● **Deposit insurance:** [FDIC insurance details] ref
        
        1.4 FY2024 scale (as of 12/31/2024)
        ● **Total assets:** $[Value]B ref
        ● **Total deposits:** $[Value]B ref
        ● **Total loans (including loans held-for-sale):** $[Value]B ref
        ● **Stockholders’ equity:** $[Value]M ref
        
        1.5 FY2024 performance and capital posture
        ● **Net income (FY2024):** $[Value]M ref
        ● **Profitability ratios (FY2024):** ROAA [Value]% and ROAE [Value]% ref
        ● **Book value per share:** $[Value] ref
        ● **Capital signal:** [Capitalization status/ratios] ref
        
        1.6 YoY movement (2024 vs 2023)
        ● **Assets:** [+/-]% ref
        ● **Deposits:** [+/-]% ref
        ● **Net loans:** [+/-]% ref
        ● **Net income:** [+/-]% ref
        
        1.7 Business lines the bank emphasizes publicly
        ● **Business lending focus:** [Details] ref
        ● **SBA capability:** [SBA status and programs] ref
        ● **Wealth / investments:** [Partners and services] ref
        
        1.8 Governance and audit discipline
        ● **Audit oversight:** [Audit firm and committee details] ref
        
        **Why this matters for Speridian**
        [Paragraph synthesizing the data into a sales strategy for Speridian] ref
    """,

    "Section 2: Account Key Business Initiatives": """
        Act as a strategic advisor. Use the following EXACT structure and styling:

        Section 2: Account Key Business Initiatives
        2.1 Executive synthesis: what [Company Name] is optimizing for
        [Provide a short paragraph intro]
        1. **[Priority 1 Title]**: [Brief description] ref
        2. **[Priority 2 Title]**: [Brief description] ref
        3. **[Priority 3 Title]**: [Brief description] ref
        4. **[Priority 4 Title]**: [Brief description] ref
        5. **[Priority 5 Title]**: [Brief description] ref

        2.2 Initiative portfolio: notable programs and why they matter
        **Initiative 1: [Title]**
        **What [Company Name] is doing**
        ● [Details] ref
        **Why it matters**
        ● [Operational analysis/friction points]
        **KPI watchlist**
        ● [List 3 specific metrics] ref

        [Repeat for Initiative 2, 3, and 4 using the same pattern]

        2.3 Other initiatives worth tracking
        ● **[Initiative Name]**: [Details] ref
    """,

    "Section 3: Account Tech Landscape": """
        Act as a Fintech Architect. Use the following EXACT structure and styling:

        Section 3: Account Tech Landscape
        Executive snapshot
        [Intro paragraph]
        1. **Digital access layer for consumers**: [Summary] ref
        2. **Treasury and cash-management capabilities for businesses**: [Summary] ref
        3. **Partner ecosystem for cards and value-added services**: [Summary] ref

        3.1 Digital banking channels and self-service capabilities
        **Online Banking and Bill Pay**
        ● [Details] ref
        **Mobile Banking with Mobile Deposit**
        ● [Details] ref
        **Mobile Wallet**
        ● [Details] ref
        **Debit card controls (CardValet)**
        ● [Details] ref
        **Practical implications**
        ● [Impact analysis] ref

        3.2 Treasury, cash management, and business workflow tooling
        **Business online banking and approvals**
        ● [Details] ref
        **Remote Deposit Capture**
        ● [Details] ref
        **Positive Pay and ACH Positive Pay**
        ● [Details] ref
        **Invoicing and digital payment acceptance**
        ● [Details] ref
        **Practical implications**
        ● [Impact analysis] ref

        3.3 Card, payments, and partner ecosystems
        **Credit cards**
        ● [Issuer name] ref
        **ATM network**
        ● [Network name] ref
        **Practical implications**
        ● [Impact analysis] ref

        3.4 What this means for partner-led delivery
        ● [Strategy 1] ref
        ● [Strategy 2] ref

        3.5 IT Operating Model
        ● [Staff estimate and leadership details]
        ○ [Sub-bullet on committees] ref
        ○ [Sub-bullet on locations] ref
        **Interpretation**
        [Analysis paragraph] ref
    """,

    "Section 4: Speridian Account Relationship": """
        Act as a Sales Director. Use the following EXACT structure and styling:

        Section 4: Speridian Account Relationship and Competitive Context
        4.1 Current Speridian relationship
        [Intro paragraph] ref
        **Current relationship footprint**
        ● **Active working lane (strongest):** [Lending/Agribusiness]
        ○ [Stakeholder Name], [Title]: [Status]
        **Connection status**
        ● **Met / warm:** [Names]
        ● **Next to build (priority):** [Role titles]
        **What this signals**
        ● [Strategic analysis] ref

        4.2 Stakeholder map
        [Description of map priority]
        **Primary sponsor for [Department]**
        ● **[Name]**, [Title]
        ○ [Bio/ownership details] ref

        [Include Table with specific columns: Prospect Name, Designation, LinkedIn URL, Connected/Not, Email, Contact Info]

        4.3 Competitive context: who is already “in the account”
        [Include Table with specific columns: Domain, What they are doing, Who is visibly in the account, Why it matters for Speridian]

        4.4 Where Speridian can realistically fit
        **Play 1: [Title]**
        **What to offer**
        ● [Bullet 1]
        ● [Bullet 2]
        **Why this fits [Company Name]**
        ● [Analysis] ref
    """,

    "Section 5: Speridian Next Steps to Move Account Forward": """
        Act as a Managing Director. Use the following EXACT structure and styling:

        Section 5: Speridian Next Steps to Move Account Forward
        5.1 Strong signals [Company Name] will fund services work

        1. **[Signal 1 Title]**
        ● [Details on current performance/priorities] ref
        ● [Connection to services need] ref

        2. **[Signal 2 Title]**
        ● [Leadership change/mandate details] ref
        ● [Connection to modernization need] ref

        3. **[Signal 3 Title]**
        ● [Specific workflow pain points like Positive Pay/ACH] ref
        ● [Connection to operational efficiency need] ref

        4. **[Signal 4 Title]**
        ● [Acquisition/M&A signal] ref
        ● [Connection to integration playbook need] ref

        5. **[Signal 5 Title]**
        ● [Board/Capital governance signal] ref
        ● [Connection to ROI/Audit-ready delivery] ref
    """
}

# --- 4. MULTI-AGENT ANALYTICS ENGINE ---
def get_llm():
    # 'claude-3-5-sonnet-20241022' is the most stable identifier for Sonnet 3.5
    return ChatAnthropic(
        model="claude-3-haiku-20240307", 
        anthropic_api_key=st.secrets["ANTHROPIC_API_KEY"],
        temperature=0
    )

def initializer(state: OverallState):
    """Starts the process by listing what needs to be researched."""
    return {
        "remaining_sections": list(PROMPT_SOP.keys()),
        "completed_research": [],
        "all_urls": []
    }
def researcher_node(state: OverallState):
    """Researches the next section in the list with strict styling enforcement."""
    if not state["remaining_sections"]:
        return state

    current_section = state["remaining_sections"][0]
    llm = get_llm()
    search_tool = TavilySearchResults(max_results=3, tavily_api_key=st.secrets["TAVILY_API_KEY"])
    
    # 1. Search Logic
    query = f"{state['target_company']} {current_section} 2024 2025"
    try:
        web_results = search_tool.invoke(query)
        urls = [r.get('url', '') for r in web_results]
        web_context = "\n".join([f"Source: {r.get('content', '')}" for r in web_results])
    except:
        urls, web_context = [], "Web search failed."

    # 2. Strict Styling Instructions
    styling_instruction = """
    STRICT FORMATTING RULES:
    1. Use '●' for main points and '○' for sub-points.
    2. Bold category names (e.g., ● **Who they are:**).
    3. HYPERLINKING: Instead of just writing 'ref', write [ref](URL) where URL is the 
       most relevant link from the search data provided.
    4. TABLES: Use standard Markdown table syntax. Ensure columns are separated by | 
       and headers are followed by a separator line | --- | --- |.
    5. Do not add conversational filler.
    """

    sys_prompt = f"{PROMPT_SOP[current_section].replace('{company}', state['target_company'])}\n\n{styling_instruction}"
    
    # 3. User Message
    user_msg = (
        f"Target Company: {state['target_company']}\n\n"
        f"PDF DOCUMENT EXCERPT:\n{state['pdf_context'][:5000]}\n\n"
        f"WEB SEARCH DATA:\n{web_context}\n\n"
        f"Generate the report section now following the styling rules exactly."
    )
    
    try:
        response = llm.invoke([("system", sys_prompt), ("user", user_msg)])
        content = response.content
    except Exception as e:
        content = f"Error analyzing {current_section}: {str(e)}"
    
    return {
        "completed_research": state["completed_research"] + [{"section": current_section, "content": content}],
        "all_urls": state["all_urls"] + urls,
        "remaining_sections": state["remaining_sections"][1:] 
    }
def add_hyperlink(paragraph, url, text):
    """
    Adds a clickable hyperlink to a paragraph.
    """
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    # Optional: Blue and Underline styling
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rPr.append(u)
    c = OxmlElement('w:color')
    c.set(qn('w:val'), '0000FF')
    rPr.append(c)

    new_run.append(rPr)
    text_element = OxmlElement('w:t')
    text_element.text = text
    new_run.append(text_element)
    hyperlink.append(new_run)

    paragraph._p.append(hyperlink)
    return hyperlink
def save_report_as_docx(final_text, target_name):
    doc = Document()
    lines = final_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. HEADINGS
        if line.startswith('# '):
            doc.add_heading(line.replace('# ', ''), level=0)
        elif line.startswith('## '):
            doc.add_heading(line.replace('## ', ''), level=1)
            
        # 2. TABLES (Alignment Fix)
        elif line.startswith('|'):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                # Skip the Markdown separator line (e.g., |---|)
                if not re.match(r'^[| -]+$', lines[i].strip()):
                    # Split by | and remove empty strings from edges
                    cells = [c.strip() for c in lines[i].split('|') if c.strip()]
                    if cells: table_rows.append(cells)
                i += 1
            
            if table_rows:
                table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
                table.style = 'Table Grid'
                for r_idx, row_data in enumerate(table_rows):
                    for c_idx, cell_text in enumerate(row_data):
                        table.cell(r_idx, c_idx).text = cell_text
            continue 

        # 3. TEXT & CLICKABLE LINKS
        elif line:
            p = doc.add_paragraph()
            # Match the [Source](url) pattern from your LLM output
            parts = re.split(r'(\[Source\]\(.*?\))', line)
            for part in parts:
                link_match = re.match(r'\[Source\]\((.*?)\)', part)
                if link_match:
                    url = link_match.group(1)
                    add_hyperlink(p, url, " (Source)")
                else:
                    # Normal text with bolding
                    sub_parts = re.split(r'(\*\*.*?\*\*)', part)
                    for sub in sub_parts:
                        if sub.startswith('**') and sub.endswith('**'):
                            p.add_run(sub.replace('**', '')).bold = True
                        else:
                            p.add_run(sub)
        i += 1
            
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()    
def router(state: OverallState):
    """Checks if there are more sections to research."""
    return "researcher" if state["remaining_sections"] else "writer"

def writer_node(state: OverallState):
    """Finalizes the report with professional styling for the export."""
    report = f"# STRATEGIC ANALYSIS: {state['target_company']}\n\n"
    for item in state["completed_research"]:
        # Standardize Section titles
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
                status.write(f" Completed: {latest['section']}")
                container.markdown(f"### {latest['section']}")
                container.write(latest['content'])
            if node == "writer":
                final_text = output["final_report"]

    status.update(label="Analysis Finished", state="complete")
    
    # Export
    docx_bytes = save_report_as_docx(final_text, target_name)
    st.download_button(
        label="Download Professional Report (DOCX)", 
        data=docx_bytes, 
        file_name=f"Strategic_Analysis_{target_name}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

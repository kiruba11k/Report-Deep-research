import os,io,re,streamlit as st
from typing import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph,END
from docx import Document
from docx.oxml.shared import OxmlElement,qn
from docx.opc.constants import RELATIONSHIP_TYPE
from pypdf import PdfReader
os.environ["TAVILY_API_KEY"]=st.secrets["TAVILY_API_KEY"]
os.environ["ANTHROPIC_API_KEY"]=st.secrets["ANTHROPIC_API_KEY"]
st.set_page_config(page_title="Enterprise Strategic Intelligence",layout="wide")
st.title("Enterprise Strategic Intelligence Orchestrator")
class OverallState(TypedDict):
 target_company:str
 pdf_context:str
 remaining_sections:list
 completed_research:list
 all_urls:list
 final_report:str
def get_llm():
 return ChatAnthropic(model="claude-3-haiku-20240307",temperature=0)
PROMPT_SOP={
"Section 1: Account Business Overview":"""Act as a senior banking analyst and strategy consultant.Combine factual accuracy with consulting insight.Use EXACT structure:
Section 1: Account Business Overview
1.1 Who they are
● **Who they are:** Description including holding company,ticker [ref](URL)
● **Founded:** Founding year [ref](URL)
● **Footprint:** Branch and geography [ref](URL)
1.2 Headquarters and regulator signals
● **HQ:** Location [ref](URL)
● **Primary regulator:** Name [ref](URL)
1.3 Scale and performance
● **Assets:** Value [ref](URL)
● **Deposits:** Value [ref](URL)
● **Net income:** Value [ref](URL)
1.4 Business model
● **Revenue drivers:** Lending,wealth,etc [ref](URL)
**Why this matters for Speridian**
Explain strategic implications and modernization opportunities [ref](URL)
STRICT RULES:
Every fact MUST include clickable [ref](URL)
Use only verified facts
DO NOT invent data""",
"Section 2: Account Key Business Initiatives":"""Act as strategy consultant.Use EXACT structure:
Section 2: Account Key Business Initiatives
2.1 Executive synthesis
Explain strategic priorities [ref](URL)
2.2 Initiative portfolio
● **Initiative:** Description [ref](URL)
● **Why it matters:** Operational impact [ref](URL)
● **KPI watchlist:** Metrics [ref](URL)
**Why this matters for Speridian**
Explain service opportunities [ref](URL)
STRICT RULES:
Every claim must include [ref](URL)
No hallucinations""",
"Section 3: Account Tech Landscape":"""Act as fintech architect.Use EXACT structure:
Section 3: Account Tech Landscape
Executive snapshot
Summary [ref](URL)
3.1 Digital banking
● **Online banking:** Details [ref](URL)
● **Mobile banking:** Details [ref](URL)
3.2 Core banking and partners
● **Core provider:** FIS,Fiserv,Jack Henry,etc [ref](URL)
● **Fintech partners:** Vendors [ref](URL)
3.3 Implications
Explain modernization gaps and opportunities [ref](URL)
STRICT RULES:
Every fact must include [ref](URL)
Use verified sources""",
"Section 4: Speridian Account Relationship":"""Act as sales director.Use EXACT structure:
Section 4: Speridian Account Relationship
4.1 Relationship analysis
Explain likely engagement areas [ref](URL)
4.2 Stakeholder roles
● CIO,CTO,Head of Digital Banking roles and priorities [ref](URL)
4.3 Strategic fit
Explain where Speridian can deliver value [ref](URL)
STRICT RULES:
DO NOT generate LinkedIn URLs
DO NOT generate personal contact info
Use role-level insights only
Include [ref](URL)""",
"Section 5: Speridian Next Steps":"""Act as managing director.Use EXACT structure:
Section 5: Speridian Next Steps
5.1 Funding signals
● Signal description [ref](URL)
● Why it creates opportunity [ref](URL)
5.2 Recommended plays
● Play description [ref](URL)
STRICT RULES:
Every claim must include [ref](URL)
No hallucinations"""}
def initializer(state:OverallState):
 return{"remaining_sections":list(PROMPT_SOP.keys()),"completed_research":[],"all_urls":[]}
def researcher_node(state:OverallState):
 if not state["remaining_sections"]:return state
 current_section=state["remaining_sections"][0]
 llm=get_llm()
 fintech_domains=["fdic.gov","sec.gov","americanbanker.com","finextra.com","bankingdive.com","fintechfutures.com","bankautomationnews.com"]
 if"Tech Landscape"in current_section:
  query=f"{state['target_company']} core banking provider FIS Fiserv Jack Henry fintech"
 elif"Business Overview"in current_section:
  query=f"{state['target_company']} annual report investor relations assets deposits net income"
 else:
  query=f"{state['target_company']} {current_section} banking strategy initiatives"
 search_tool=TavilySearchResults(max_results=5,include_domains=fintech_domains)
 try:
  results=search_tool.invoke({"query":query})
  urls=[];context=""
  for r in results:
   url=r.get("url","")
   urls.append(url)
   context+=f"\nSource [{url}]:{r.get('content','')}"
 except Exception as e:
  urls=[];context=f"Search failed:{str(e)}"
 sys_prompt=PROMPT_SOP[current_section]
 user_msg=f"Company:{state['target_company']}\nPDF Context:{state['pdf_context'][:4000]}\nVerified Sources:{context}"
 response=llm.invoke([("system",sys_prompt),("user",user_msg)])
 return{"completed_research":state["completed_research"]+[{"section":current_section,"content":response.content}],"all_urls":state["all_urls"]+urls,"remaining_sections":state["remaining_sections"][1:]}
def reflection_node(state:OverallState):
 llm=get_llm()
 latest=state["completed_research"][-1]
 audit_prompt=f"""You are audit analyst.Remove hallucinations.Remove claims without sources.Ensure every fact has [ref](URL).Return corrected version only:\n{latest['content']}"""
 response=llm.invoke([("user",audit_prompt)])
 state["completed_research"][-1]["content"]=response.content
 return state
def writer_node(state:OverallState):
 report=f"# Strategic Intelligence Report: {state['target_company']}\n"
 for item in state["completed_research"]:
  report+=f"\n## {item['section']}\n{item['content']}\n"
 report+="\n# References\n"
 for url in list(set(state["all_urls"])):report+=f"- {url}\n"
 return{"final_report":report}
def add_hyperlink(paragraph,url,text):
 part=paragraph.part
 r_id=part.relate_to(url,RELATIONSHIP_TYPE.HYPERLINK,is_external=True)
 hyperlink=OxmlElement("w:hyperlink")
 hyperlink.set(qn("r:id"),r_id)
 run=OxmlElement("w:r")
 text_el=OxmlElement("w:t")
 text_el.text=text
 run.append(text_el)
 hyperlink.append(run)
 paragraph._p.append(hyperlink)
def save_docx(text):
 doc=Document()
 for line in text.split("\n"):
  p=doc.add_paragraph()
  parts=re.split(r'(\[ref\]\(.*?\))',line)
  for part in parts:
   match=re.match(r'\[ref\]\((.*?)\)',part)
   if match:add_hyperlink(p,match.group(1),"[ref]")
   else:p.add_run(part)
 buf=io.BytesIO();doc.save(buf);return buf.getvalue()
workflow=StateGraph(OverallState)
workflow.add_node("initializer",initializer)
workflow.add_node("researcher",researcher_node)
workflow.add_node("reflection",reflection_node)
workflow.add_node("writer",writer_node)
workflow.set_entry_point("initializer")
workflow.add_edge("initializer","researcher")
workflow.add_edge("researcher","reflection")
workflow.add_conditional_edges("reflection",lambda x:"researcher"if x["remaining_sections"]else"writer",{"researcher":"researcher","writer":"writer"})
workflow.add_edge("writer",END)
app=workflow.compile()
target=st.sidebar.text_input("Target Company")
pdf=st.sidebar.file_uploader("Upload PDF",type="pdf")
if st.sidebar.button("Run Analysis")and target:
 pdf_text=""
 if pdf:
  reader=PdfReader(pdf)
  pdf_text="\n".join([p.extract_text()for p in reader.pages if p.extract_text()])
 state={"target_company":target,"pdf_context":pdf_text,"remaining_sections":[],"completed_research":[],"all_urls":[],"final_report":""}
 final=""
 with st.status("Running analysis"):
  for event in app.stream(state):
   for node,out in event.items():
    if node=="reflection":
     latest=out["completed_research"][-1]
     st.markdown(f"### {latest['section']}")
     st.write(latest["content"])
    if node=="writer":final=out["final_report"]
 st.download_button("Download DOCX",save_docx(final),file_name=f"{target}_Strategic_Report.docx")

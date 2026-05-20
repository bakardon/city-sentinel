"""
Generate SDP-formatted FYP report from FYP_Report_Defence.docx content.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = r'D:\hanan_fyp\Report\FYP_Report_Defence.docx'
OUT = r'D:\hanan_fyp\Report\FYP_Report_SDP_Formatted.docx'

src = Document(SRC)

# Extract all source paragraphs
all_paras = [(p.style.name, p.text) for p in src.paragraphs]

# Extract tables
all_tables = []
for t in src.tables:
    rows = []
    for row in t.rows:
        rows.append([cell.text for cell in row.cells])
    all_tables.append(rows)

print(f"Source: {len(all_paras)} paragraphs, {len(all_tables)} tables")

# ── helpers ──────────────────────────────────────────────
doc = Document()

def set_margins(section, top=1.5, bottom=1.5, left=2.0, right=1.33):
    section.top_margin = Inches(top)
    section.bottom_margin = Inches(bottom)
    section.left_margin = Inches(left)
    section.right_margin = Inches(right)
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.header_distance = Inches(1.0)
    section.footer_distance = Inches(0.11)

def fmt_body(p, size=12, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p.alignment = alignment
    pf = p.paragraph_format
    pf.space_after = Pt(0)
    pf.line_spacing = 1.5
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic

def add_body(text, size=12, bold=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    p.alignment = alignment
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    return p

def add_centered(text, size=14, bold=True):
    return add_body(text, size=size, bold=bold, alignment=WD_ALIGN_PARAGRAPH.CENTER)

def add_heading1(text):
    """CHAPTER heading - Heading 1 style"""
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.bold = True
    return p

def add_heading3(text):
    """Chapter title - Heading 3 style"""
    p = doc.add_heading(text, level=3)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.bold = True
    return p

def add_heading4(text):
    """Level-1 subheading - Heading 4"""
    p = doc.add_heading(text, level=4)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.bold = True
    return p

def add_heading5(text):
    """Level-2 subheading - Heading 5"""
    p = doc.add_heading(text, level=5)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.bold = True
    return p

def add_page_break():
    doc.add_page_break()

def add_table(table_data, caption=None):
    if caption:
        add_body(caption, size=12, bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER)
    if not table_data:
        return
    t = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
    t.style = 'Table Grid'
    for ri, row in enumerate(table_data):
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            cell.text = val
            for par in cell.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in par.runs:
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(10)
                    if ri == 0:
                        run.font.bold = True
    add_body('')  # spacing after table

def add_numbered_list(text):
    p = doc.add_paragraph(style='List Number')
    p.text = ''
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5
    return p

def add_bullet(text):
    p = doc.add_paragraph(style='List Bullet')
    p.text = ''
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.5
    return p

# ── Set up first section (title page) ──────────────────
section = doc.sections[0]
set_margins(section, top=1.5, bottom=0.39, left=2.0, right=1.33)

# ═══════════════════════════════════════════════════════
# TITLE PAGE
# ═══════════════════════════════════════════════════════
add_body('')  # spacing
add_body('')
add_body('[University Logo Placeholder]', size=14, bold=False, alignment=WD_ALIGN_PARAGRAPH.CENTER)
add_body('')
add_body('')
add_centered('City Sentinel', size=18, bold=True)
add_centered('An Intelligent Data-Engineering Framework for Smart-City Threat Detection', size=14, bold=True)
add_body('')
add_centered('FINAL YEAR PROJECT REPORT', size=14, bold=True)
add_body('')
add_centered('Submitted in partial fulfillment of the requirements for the degree of', size=12, bold=False)
add_centered('Bachelor of Science in Computer Science', size=12, bold=False)
add_body('')
add_body('')
add_centered('Submitted By:', size=14, bold=True)
add_centered('Syed Hanan Shabir — 2022565', size=14, bold=True)
add_centered('Abu Bakar Bin Mazhar — 2022039', size=14, bold=True)
add_centered('Muhammad Aqeeb Ahmad — 2022349', size=14, bold=True)
add_body('')
add_centered('Supervisor: Dr. Masroor Hussain', size=14, bold=True)
add_centered('Co-Supervisor: Dr. Farhan Khan', size=14, bold=True)
add_body('')
add_centered('Department of Computer Science', size=14, bold=True)
add_centered('Faculty of Computing and Information Technology', size=14, bold=True)
add_body('')
add_centered('Academic Year 2025–2026', size=14, bold=True)

# ═══════════════════════════════════════════════════════
# NEW SECTION: subsequent pages margins
# ═══════════════════════════════════════════════════════
new_section = doc.add_section()
set_margins(new_section, top=1.5, bottom=1.5, left=2.0, right=1.33)

# ═══════════════════════════════════════════════════════
# DECLARATION
# ═══════════════════════════════════════════════════════
add_centered('Declaration', size=14, bold=True)
add_body('')
add_body('We hereby declare that this Final Year Project report entitled "City Sentinel: An Intelligent Data-Engineering Framework for Smart-City Threat Detection" is our own original work and has not been submitted elsewhere for any other degree or qualification. All sources used have been acknowledged in the bibliography and references.')
add_body('')
add_body('Syed Hanan Shabir — 2022565 ____________________')
add_body('')
add_body('Abu Bakar Bin Mazhar — 2022039 ____________________')
add_body('')
add_body('Muhammad Aqeeb Ahmad — 2022349 ____________________')
add_body('')
add_body('Date: April 2026')

add_page_break()

# ═══════════════════════════════════════════════════════
# CERTIFICATE OF APPROVAL
# ═══════════════════════════════════════════════════════
add_centered('Certificate of Approval', size=14, bold=True)
add_body('')
add_body('This is to certify that the Final Year Project report submitted by Syed Hanan Shabir (2022565), Abu Bakar Bin Mazhar (2022039), and Muhammad Aqeeb Ahmad (2022349) entitled "City Sentinel: An Intelligent Data-Engineering Framework for Smart-City Threat Detection" has been examined and is approved for the degree of Bachelor of Science in Computer Science.')
add_body('')
add_body('')
add_body('Supervisor: Dr. Masroor Hussain\t\t\t\t____________________')
add_body('')
add_body('Co-Supervisor: Dr. Farhan Khan\t\t\t\t____________________')
add_body('')
add_body('')
add_body('-------------------')
add_body('Prof. Dr. Qadeer Ul Hassan')
add_body('(Dean)')
add_body('')
add_body('Date: April 2026')

add_page_break()

# ═══════════════════════════════════════════════════════
# SDGs INCLUSION
# ═══════════════════════════════════════════════════════
add_centered('SDGs Inclusion', size=14, bold=True)
add_body('')
add_body('The City Sentinel project contributes to the achievement of the following United Nations Sustainable Development Goals (SDGs):')
add_body('')

add_body('SDG 11 — Sustainable Cities and Communities', size=12, bold=True)
add_body('City Sentinel directly advances SDG 11 by providing an intelligent, technology-driven framework for enhancing urban safety and resilience. The platform integrates six AI-powered detection modules — including face recognition, fire detection, violence detection, and vehicular accident detection — to enable proactive threat identification across city-wide surveillance networks. By transforming passive CCTV infrastructure into an intelligent monitoring system, City Sentinel helps cities become safer, more inclusive, and more resilient to security threats. The real-time alerting capabilities reduce emergency response times, while the cloud-persisted audit trail supports evidence-based urban safety planning and resource allocation. This directly supports Target 11.7 (providing universal access to safe, inclusive, and accessible public spaces) and Target 11.3 (enhancing inclusive and sustainable urbanisation).')
add_body('')

add_body('SDG 16 — Peace, Justice and Strong Institutions', size=12, bold=True)
add_body('The project contributes to SDG 16 by strengthening the technological capacity of public safety institutions to prevent and respond to crime and violence. City Sentinel\'s armed threat detection (knife and firearm recognition), violence detection, and comprehensive event logging provide law enforcement and security agencies with actionable intelligence for crime prevention and post-incident forensic analysis. The system\'s open-architecture design promotes transparency and accountability — operators can audit detection decisions, review confidence scores, and examine annotated snapshots, thereby reducing the opacity that characterises proprietary surveillance systems. The persons database with tagging and deletion capabilities also supports compliance with data protection regulations, advancing Target 16.1 (significantly reduce all forms of violence) and Target 16.6 (develop effective, accountable, and transparent institutions).')
add_body('')

add_body('SDG 9 — Industry, Innovation and Infrastructure', size=12, bold=True)
add_body('City Sentinel exemplifies SDG 9 by demonstrating how cutting-edge artificial intelligence and software engineering innovations can be integrated into existing urban infrastructure at low cost. The platform leverages commodity GPU hardware, open-source deep learning frameworks (YOLOv8, InsightFace, EasyOCR), and cloud-managed databases (Supabase) to deliver enterprise-grade surveillance capabilities without proprietary vendor dependency. The modular, extensible architecture serves as a blueprint for future smart-city infrastructure projects, enabling developing countries to adopt intelligent surveillance at a fraction of the cost of commercial solutions. This directly supports Target 9.1 (develop quality, reliable, sustainable, and resilient infrastructure) and Target 9.5 (enhance scientific research and upgrade technological capabilities).')
add_body('')

add_body('---------------------\t\t\t\t\t\t---------------------')
add_body('Dr. Masroor Hussain\t\t\t\t\t\tDr. Farhan Khan')
add_body('(Supervisor)\t\t\t\t\t\t\t(Co-Supervisor)')

add_page_break()

# ═══════════════════════════════════════════════════════
# ABSTRACT
# ═══════════════════════════════════════════════════════
add_centered('Abstract', size=14, bold=True)
add_body('')

# Extract abstract from source (paragraphs 60-68)
for i in [60, 62, 64, 66, 68]:
    if i < len(all_paras):
        txt = all_paras[i][1].strip()
        if txt:
            add_body(txt)
            add_body('')

add_page_break()

# ═══════════════════════════════════════════════════════
# ACKNOWLEDGEMENTS
# ═══════════════════════════════════════════════════════
add_centered('ACKNOWLEDGEMENTS', size=14, bold=True)
add_body('')

for i in [74, 76, 78, 80, 82, 84]:
    if i < len(all_paras):
        txt = all_paras[i][1].strip()
        if txt:
            add_body(txt)
            add_body('')

add_page_break()

# ═══════════════════════════════════════════════════════
# TABLE OF CONTENTS (placeholder)
# ═══════════════════════════════════════════════════════
add_centered('TABLE OF CONTENTS', size=14, bold=True)
add_body('')
add_body('[Table of Contents — Please update this field in Microsoft Word: References > Table of Contents > Update Table]', bold=True)

add_page_break()

# ═══════════════════════════════════════════════════════
# LIST OF FIGURES (placeholder)
# ═══════════════════════════════════════════════════════
add_centered('LIST OF FIGURES', size=14, bold=True)
add_body('')
add_body('[List of Figures — Please insert via References > Insert Table of Figures in Microsoft Word]', bold=True)

add_page_break()

# ═══════════════════════════════════════════════════════
# LIST OF TABLES (placeholder)
# ═══════════════════════════════════════════════════════
add_centered('LIST OF TABLES', size=14, bold=True)
add_body('')
add_body('[List of Tables — Please insert via References > Insert Table of Figures (select Table label) in Microsoft Word]', bold=True)

add_page_break()

# ═══════════════════════════════════════════════════════
# LIST OF ABBREVIATIONS
# ═══════════════════════════════════════════════════════
add_centered('LIST OF ABBREVIATIONS', size=14, bold=True)
add_body('')
abbrevs = [
    ('ANPR', 'Automatic Number Plate Recognition'),
    ('API', 'Application Programming Interface'),
    ('ASGI', 'Asynchronous Server Gateway Interface'),
    ('CCTV', 'Closed-Circuit Television'),
    ('CNN', 'Convolutional Neural Network'),
    ('CRUD', 'Create, Read, Update, Delete'),
    ('CUDA', 'Compute Unified Device Architecture'),
    ('FAISS', 'Facebook AI Similarity Search'),
    ('GPU', 'Graphics Processing Unit'),
    ('ICT', 'Information and Communication Technology'),
    ('IoU', 'Intersection over Union'),
    ('JWT', 'JSON Web Token'),
    ('LAN', 'Local Area Network'),
    ('mAP', 'Mean Average Precision'),
    ('OCR', 'Optical Character Recognition'),
    ('ONNX', 'Open Neural Network Exchange'),
    ('PII', 'Personally Identifiable Information'),
    ('REST', 'Representational State Transfer'),
    ('RTSP', 'Real-Time Streaming Protocol'),
    ('SDG', 'Sustainable Development Goal'),
    ('SQL', 'Structured Query Language'),
    ('SVG', 'Scalable Vector Graphics'),
    ('UAT', 'User Acceptance Testing'),
    ('UI/UX', 'User Interface / User Experience'),
    ('UUID', 'Universally Unique Identifier'),
    ('WAN', 'Wide Area Network'),
    ('YOLO', 'You Only Look Once'),
]
for abbr, full in abbrevs:
    add_body(f'{abbr}\t\t{full}')

add_page_break()

# ═══════════════════════════════════════════════════════
# Helper: Process a range of source paragraphs
# ═══════════════════════════════════════════════════════
# Table index tracker
table_idx = [0]

def get_source_text(idx):
    if idx < len(all_paras):
        return all_paras[idx][1].strip()
    return ''

def add_next_table(caption=None):
    ti = table_idx[0]
    if ti < len(all_tables):
        add_table(all_tables[ti], caption=caption)
        table_idx[0] += 1

def process_range(start, end):
    """Process source paragraphs from start to end, converting styles."""
    i = start
    while i <= end and i < len(all_paras):
        style, text = all_paras[i]
        text = text.strip()
        if not text:
            i += 1
            continue

        if style == 'Heading 1':
            # Skip - we handle chapter headings manually
            pass
        elif style == 'Heading 2':
            add_heading4(text)
        elif style == 'Heading 3':
            add_heading5(text)
        elif style == 'List Number':
            add_numbered_list(text)
        elif style == 'List Bullet':
            add_bullet(text)
        elif 'table' in text.lower() and text.startswith('| Table') or text.startswith('| table'):
            add_next_table(caption=text.strip('| '))
        elif text.startswith('| Table') or text.startswith('| table'):
            add_next_table(caption=text.strip('| '))
        else:
            add_body(text)

        i += 1


# ═══════════════════════════════════════════════════════
# CHAPTER I — Introduction
# (Source: Section 1, paragraphs 124-200)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER I')
add_heading3('Introduction')
process_range(126, 201)

add_page_break()

# ═══════════════════════════════════════════════════════
# CHAPTER II — Literature Survey
# (Source: Section 2, paragraphs ~202-291)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER II')
add_heading3('Literature Survey')
process_range(204, 291)

add_page_break()

# ═══════════════════════════════════════════════════════
# CHAPTER III — Design (Requirements + Architecture)
# (Source: Sections 3+4, paragraphs ~293-399)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER III')
add_heading3('Design (Systems Requirements and Specifications)')
process_range(295, 399)

add_page_break()

# ═══════════════════════════════════════════════════════
# CHAPTER IV — Proposed Solution (Tech Stack + Implementation)
# (Source: Sections 5+6, paragraphs ~401-544)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER IV')
add_heading3('Proposed Solution (Methodology and Implementation)')
process_range(401, 544)

add_page_break()

# ═══════════════════════════════════════════════════════
# CHAPTER V — Results and Discussion
# (Source: Sections 7+8, paragraphs ~546-700)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER V')
add_heading3('Results and Discussion')
process_range(546, 700)

add_page_break()

# ═══════════════════════════════════════════════════════
# CHAPTER VI — Conclusion and Future Work
# (Source: Section 9, paragraphs ~701-758)
# ═══════════════════════════════════════════════════════
add_heading1('CHAPTER VI')
add_heading3('Conclusion and Future Work')
process_range(703, 758)

add_page_break()

# ═══════════════════════════════════════════════════════
# GLOSSARY (optional)
# ═══════════════════════════════════════════════════════
add_heading1('GLOSSARY')
add_body('')
glossary = [
    ('ArcFace', 'Additive Angular Margin Loss function used in InsightFace for discriminative face embedding learning.'),
    ('Bounding Box', 'A rectangular region in an image that encloses a detected object, defined by corner coordinates.'),
    ('Cosine Similarity', 'A metric measuring the cosine of the angle between two vectors, used for face embedding comparison.'),
    ('Embedding', 'A fixed-length numerical vector representation of an input (e.g., a face image) in a latent feature space.'),
    ('Inference', 'The process of running a trained model on new data to produce predictions.'),
    ('mAP (mean Average Precision)', 'A standard metric for evaluating object detection models across all classes and confidence thresholds.'),
    ('RTSP (Real-Time Streaming Protocol)', 'A network protocol for controlling streaming media servers, commonly used by IP cameras.'),
    ('Temporal Smoothing', 'A technique that aggregates predictions over multiple consecutive frames to reduce false positives.'),
    ('Worker', 'A background thread that continuously processes video frames from an RTSP stream using a specific AI model.'),
]
for term, defn in glossary:
    add_body(f'{term}: {defn}')

add_page_break()

# ═══════════════════════════════════════════════════════
# REFERENCES
# ═══════════════════════════════════════════════════════
add_heading1('REFERENCES')
add_body('')

# Extract references from source (paragraphs 760+)
for i in range(762, 810):
    if i < len(all_paras):
        style, text = all_paras[i]
        text = text.strip()
        if text:
            add_numbered_list(text)

add_page_break()

# ═══════════════════════════════════════════════════════
# APPENDICES
# ═══════════════════════════════════════════════════════

# Appendix A - Environment Variables
add_heading1('APPENDIX A')
add_heading3('Environment Variables Reference')
process_range(810, 900)

add_page_break()

# Appendix B - Database Schema
add_heading1('APPENDIX B')
add_heading3('Database Schema (SQL)')
process_range(900, 968)

add_page_break()

# Appendix C - Project File Structure
add_heading1('APPENDIX C')
add_heading3('Project File Structure')
process_range(970, 1036)

add_page_break()

# Appendix D - Sample API Responses
add_heading1('APPENDIX D')
add_heading3('Sample API Responses')
process_range(1040, 1093)

# ═══════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════
doc.save(OUT)
print(f"\nSaved formatted report to: {OUT}")
print(f"Total paragraphs in output: {len(doc.paragraphs)}")
print("Done!")

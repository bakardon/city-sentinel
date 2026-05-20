import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
doc = Document(r'D:\hanan_fyp\Report\FYP_Report_Defence.docx')
for i in range(104, 128):
    p = doc.paragraphs[i]
    print(f'[{i}] ({p.style.name}) |{p.text}|')

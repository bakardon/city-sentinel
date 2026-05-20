#!/usr/bin/env python3
"""
md_to_docx.py
=============
Converts FYP_Report.md to a professional Word (.docx) document.

Usage:
    cd D:\\hanan_fyp\\Report
    python md_to_docx.py

Output:  FYP_Report.docx  (same folder as this script)

Requirements:
    pip install python-docx lxml
"""

import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL

# ── paths ──────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
MD_FILE = HERE / "FYP_Report.md"
DOCX_OUT = HERE / "FYP_Report.docx"

# ── colour palette ─────────────────────────────────────────────────────────────
C_BLACK      = RGBColor(0x00, 0x00, 0x00)
C_HEADING1   = RGBColor(0x10, 0x2A, 0x6B)   # dark navy
C_HEADING2   = RGBColor(0x1A, 0x47, 0x9A)   # medium blue
C_HEADING3   = RGBColor(0x1E, 0x6A, 0xB0)   # steel blue
C_HEADING4   = RGBColor(0x2E, 0x86, 0xC1)   # lighter blue
C_CODE_BG    = RGBColor(0xF2, 0xF2, 0xF2)   # very light grey (used via shading XML)
C_TABLE_HDR  = RGBColor(0x10, 0x2A, 0x6B)   # same as H1 for table headers
C_TABLE_EVEN = RGBColor(0xE8, 0xF1, 0xFB)   # very light blue stripe
C_RULE_LINE  = RGBColor(0xCC, 0xCC, 0xCC)
C_WHITE      = RGBColor(0xFF, 0xFF, 0xFF)

# ── font names ─────────────────────────────────────────────────────────────────
FONT_BODY  = "Calibri"
FONT_MONO  = "Courier New"


# ══════════════════════════════════════════════════════════════════════════════
# XML / formatting helpers
# ══════════════════════════════════════════════════════════════════════════════

def _set_cell_bg(cell, rgb: RGBColor):
    """Fill a table cell background with a solid colour."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
    tcPr.append(shd)


def _set_para_bg(para, hex_str: str):
    """Add paragraph-level shading (used for code blocks)."""
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_str)
    pPr.append(shd)


def _set_cell_borders(table):
    """Add thin borders to every cell in a table."""
    tbl = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)

    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "AAAAAA")
        borders.append(el)
    tblPr.append(borders)


def _add_horizontal_rule(doc):
    """Insert a visible horizontal rule paragraph."""
    para = doc.add_paragraph()
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "AAAAAA")
    pBdr.append(bottom)
    pPr.append(pBdr)
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(2)
    return para


def _page_break(doc):
    para = doc.add_paragraph()
    run = para.add_run()
    run.add_break(
        __import__("docx.enum.text", fromlist=["WD_BREAK"]).WD_BREAK.PAGE
    )
    return para


def _set_doc_margins(doc):
    """2.5 cm margins on all sides."""
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(3.0)
        section.right_margin  = Cm(2.5)


def _apply_heading_style(run, level: int):
    """Apply colour + bold to a heading run."""
    colours = {1: C_HEADING1, 2: C_HEADING2, 3: C_HEADING3, 4: C_HEADING4}
    run.font.color.rgb = colours.get(level, C_BLACK)
    run.font.bold = True


# ══════════════════════════════════════════════════════════════════════════════
# Inline markdown → run fragments
# ══════════════════════════════════════════════════════════════════════════════

# Matches: **bold**, *italic*, `code`, and plain text between them
_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|([^*`]+)")


def _apply_inline(para, text: str, base_size: Pt = Pt(11),
                  base_bold=False, mono=False):
    """
    Parse inline markdown (bold / italic / code) and add styled runs to *para*.
    Returns the paragraph.
    """
    for m in _INLINE_RE.finditer(text):
        bold_text, italic_text, code_text, plain_text = m.groups()
        if bold_text is not None:
            run = para.add_run(bold_text)
            run.bold = True
            run.font.size = base_size
            run.font.name = FONT_MONO if mono else FONT_BODY
        elif italic_text is not None:
            run = para.add_run(italic_text)
            run.italic = True
            run.font.size = base_size
            run.font.name = FONT_MONO if mono else FONT_BODY
        elif code_text is not None:
            run = para.add_run(code_text)
            run.font.name = FONT_MONO
            run.font.size = Pt(9)
        else:
            if plain_text:
                run = para.add_run(plain_text)
                run.bold = base_bold
                run.font.size = base_size
                run.font.name = FONT_MONO if mono else FONT_BODY
    return para


# ══════════════════════════════════════════════════════════════════════════════
# Section / heading helpers
# ══════════════════════════════════════════════════════════════════════════════

def _add_heading(doc, text: str, level: int):
    """
    Add a heading paragraph with our custom colour scheme.
    level 1..6.
    """
    style_map = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3",
                 4: "Heading 4", 5: "Heading 5", 6: "Heading 6"}
    style = style_map.get(level, "Heading 4")
    para = doc.add_paragraph(style=style)
    para.paragraph_format.space_before = Pt(14 - level)
    para.paragraph_format.space_after  = Pt(4)
    run = para.add_run(text)
    run.font.name = FONT_BODY
    size_map = {1: 22, 2: 17, 3: 14, 4: 12, 5: 11, 6: 11}
    run.font.size = Pt(size_map.get(level, 11))
    _apply_heading_style(run, level)
    return para


# ══════════════════════════════════════════════════════════════════════════════
# Code-block / diagram renderer
# ══════════════════════════════════════════════════════════════════════════════

def _add_code_block(doc, lines: list[str]):
    """
    Render a code/diagram block in Courier New 8 pt on a light-grey background.
    Each line is its own paragraph so Word can re-flow cleanly.
    """
    for line in lines:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after  = Pt(0)
        para.paragraph_format.left_indent  = Cm(0.4)
        # light grey background
        _set_para_bg(para, "F2F2F2")
        run = para.add_run(line if line else " ")   # keep empty lines visible
        run.font.name = FONT_MONO
        run.font.size = Pt(7.5)
        run.font.color.rgb = C_BLACK
    # small spacing after the block
    gap = doc.add_paragraph()
    gap.paragraph_format.space_before = Pt(2)
    gap.paragraph_format.space_after  = Pt(6)


# ══════════════════════════════════════════════════════════════════════════════
# Table renderer
# ══════════════════════════════════════════════════════════════════════════════

def _render_table(doc, header_cells: list[str], data_rows: list[list[str]]):
    """
    Render a markdown table into a styled Word table.
    header_cells — list of column header strings
    data_rows    — list of rows, each row is a list of cell strings
    """
    n_cols = len(header_cells)
    n_rows = 1 + len(data_rows)
    table = doc.add_table(rows=n_rows, cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    _set_cell_borders(table)

    # header row
    hdr_row = table.rows[0]
    for col_idx, hdr_text in enumerate(header_cells):
        cell = hdr_row.cells[col_idx]
        _set_cell_bg(cell, C_TABLE_HDR)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(hdr_text.strip())
        run.font.bold = True
        run.font.color.rgb = C_WHITE
        run.font.name = FONT_BODY
        run.font.size = Pt(9)

    # data rows
    for row_idx, row_data in enumerate(data_rows):
        tr = table.rows[row_idx + 1]
        bg = C_TABLE_EVEN if row_idx % 2 == 1 else None
        for col_idx, cell_text in enumerate(row_data):
            if col_idx >= n_cols:
                break
            cell = tr.cells[col_idx]
            if bg:
                _set_cell_bg(cell, bg)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            _apply_inline(para, cell_text.strip(), base_size=Pt(9))

    # add a small gap after the table
    gap = doc.add_paragraph()
    gap.paragraph_format.space_after = Pt(6)
    return table


# ══════════════════════════════════════════════════════════════════════════════
# List renderer
# ══════════════════════════════════════════════════════════════════════════════

def _add_list_item(doc, text: str, ordered: bool, number: int = 1):
    style = "List Number" if ordered else "List Bullet"
    para = doc.add_paragraph(style=style)
    para.paragraph_format.left_indent  = Cm(1.0)
    para.paragraph_format.space_before = Pt(1)
    para.paragraph_format.space_after  = Pt(1)
    _apply_inline(para, text, base_size=Pt(11))
    return para


# ══════════════════════════════════════════════════════════════════════════════
# Title / cover page
# ══════════════════════════════════════════════════════════════════════════════

def _add_cover(doc, lines: list[str]):
    """
    Render the cover block (between first --- and second ---).
    We give it special centred formatting and a page break at the end.
    """
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(72)  # push down the page

    in_table = False
    cover_lines = [l for l in lines if l.strip() not in ("<div align=\"center\">", "</div>")]
    for line in cover_lines:
        line_s = line.strip()
        if line_s.startswith("**") and line_s.endswith("**"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            run = p.add_run(line_s.strip("*"))
            run.bold = True
            run.font.size = Pt(13)
            run.font.name = FONT_BODY
            run.font.color.rgb = C_HEADING1
        elif line_s.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line_s[2:])
            run.bold = True
            run.font.size = Pt(26)
            run.font.name = FONT_BODY
            run.font.color.rgb = C_HEADING1
        elif line_s.startswith("## "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line_s[3:])
            run.bold = True
            run.font.size = Pt(16)
            run.font.name = FONT_BODY
            run.font.color.rgb = C_HEADING2
        elif "|---|" in line_s or ("|" in line_s and line_s.count("|") >= 3):
            pass  # skip separator rows
        elif line_s.startswith("|") and "|" in line_s[1:]:
            # table row
            cells = [c.strip() for c in line_s.strip("|").split("|")]
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run("  |  ".join(cells))
            run.font.size = Pt(11)
            run.font.name = FONT_BODY
        elif line_s.startswith("*") and not line_s.startswith("**"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line_s.strip("*"))
            run.italic = True
            run.font.size = Pt(11)
            run.font.name = FONT_BODY
        elif line_s and line_s != "---":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _apply_inline(p, line_s, base_size=Pt(11))

    _page_break(doc)


# ══════════════════════════════════════════════════════════════════════════════
# Main parser / state machine
# ══════════════════════════════════════════════════════════════════════════════

def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\|[-| :]+\|$", line.strip()))


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 3


def _parse_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md_path: Path, docx_path: Path):
    lines = md_path.read_text(encoding="utf-8").splitlines()

    doc = Document()
    _set_doc_margins(doc)

    # Default Normal style
    normal = doc.styles["Normal"]
    normal.font.name = FONT_BODY
    normal.font.size = Pt(11)

    # ── state ───────────────────────────────────────────────────────────────
    in_code      = False
    code_lines   = []
    in_table     = False
    table_header = []
    table_data   = []
    cover_done   = False
    cover_lines  = []
    collecting_cover = False
    hr_count = 0

    # The first block up to the third "---" is the cover page
    # Collect it separately
    cover_raw = []
    cover_end_idx = 0
    triple_dash_count = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            triple_dash_count += 1
            if triple_dash_count == 2:
                cover_end_idx = i
                break
        cover_raw.append(ln)

    # Render cover
    _add_cover(doc, cover_raw)

    # Process the rest of the document
    i = cover_end_idx + 1
    ordered_counter = 0

    while i < len(lines):
        line = lines[i]
        raw  = line         # keep original spacing for code blocks
        line = line.rstrip()

        # ── code block toggle ────────────────────────────────────────────────
        if line.startswith("```"):
            if not in_code:
                in_code    = True
                code_lines = []
            else:
                _add_code_block(doc, code_lines)
                in_code    = False
                code_lines = []
            i += 1
            continue

        if in_code:
            code_lines.append(raw.rstrip())
            i += 1
            continue

        # ── flush pending table when a non-table line appears ────────────────
        if in_table and not _is_table_row(line) and not _is_table_separator(line):
            if table_header:
                _render_table(doc, table_header, table_data)
            in_table     = False
            table_header = []
            table_data   = []
            # fall through to process current line normally

        # ── table rows ───────────────────────────────────────────────────────
        if _is_table_separator(line):
            i += 1
            continue  # skip separator rows

        if _is_table_row(line):
            cells = _parse_table_row(line)
            if not in_table:
                in_table     = True
                table_header = cells
                table_data   = []
            else:
                table_data.append(cells)
            i += 1
            continue

        # ── headings ─────────────────────────────────────────────────────────
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text  = heading_match.group(2).strip()
            _add_heading(doc, text, level)
            i += 1
            continue

        # ── horizontal rule --------------------------------------------------
        if re.match(r"^-{3,}$", line.strip()):
            _add_horizontal_rule(doc)
            i += 1
            continue

        # ── page break hint: "---" after certain headings ────────────────────
        # (already handled above as horizontal rule)

        # ── blank line ───────────────────────────────────────────────────────
        if not line.strip():
            # add small spacing paragraph
            gap = doc.add_paragraph()
            gap.paragraph_format.space_before = Pt(0)
            gap.paragraph_format.space_after  = Pt(3)
            i += 1
            continue

        # ── ordered list items ───────────────────────────────────────────────
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if ol_match:
            ordered_counter += 1
            _add_list_item(doc, ol_match.group(2), ordered=True,
                           number=ordered_counter)
            i += 1
            continue
        else:
            ordered_counter = 0

        # ── unordered list items (-, *, •) ───────────────────────────────────
        ul_match = re.match(r"^[-*•]\s+(.+)$", line)
        if ul_match:
            _add_list_item(doc, ul_match.group(1), ordered=False)
            i += 1
            continue

        # ── blockquote (>text) ───────────────────────────────────────────────
        bq_match = re.match(r"^>\s*(.*)$", line)
        if bq_match:
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(1.5)
            para.paragraph_format.space_before = Pt(2)
            para.paragraph_format.space_after  = Pt(2)
            _apply_inline(para, bq_match.group(1), base_size=Pt(10))
            i += 1
            continue

        # ── <div align="center"> … </div> — treat content as centred para ───
        if line.strip() in ('<div align="center">', "</div>"):
            i += 1
            continue

        # ── inline SQL / code fence content that starts with spaces ──────────
        # (already captured inside code blocks above)

        # ── regular paragraph ────────────────────────────────────────────────
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after  = Pt(4)
        para.paragraph_format.alignment    = WD_ALIGN_PARAGRAPH.JUSTIFY
        _apply_inline(para, line, base_size=Pt(11))
        i += 1

    # flush any trailing table
    if in_table and table_header:
        _render_table(doc, table_header, table_data)

    # flush any unclosed code block
    if in_code and code_lines:
        _add_code_block(doc, code_lines)

    doc.save(docx_path)
    print(f"✅  Saved: {docx_path}")
    print(f"   Pages (approx): {len(doc.paragraphs) // 40 + 1}")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not MD_FILE.exists():
        print(f"❌  Input file not found: {MD_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"Converting  {MD_FILE.name}  →  {DOCX_OUT.name} …")
    convert(MD_FILE, DOCX_OUT)

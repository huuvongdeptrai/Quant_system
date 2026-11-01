import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_margins(cell, top=100, bottom=100, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_shading(cell, color_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)

def set_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="12" w:space="0" w:color="1E293B"/>
            <w:bottom w:val="single" w:sz="12" w:space="0" w:color="1E293B"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            <w:insideV w:val="none"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def clean_text(text):
    t = text.strip()
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = t.replace('`', '')
    t = t.replace(r'\mu', 'μ')
    t = t.replace(r'\Delta P_{\text{SL}} > \epsilon_{\text{min}}', 'ΔP_SL > ε_min')
    t = t.replace(r'\Delta', 'Δ')
    t = t.replace(r'\sigma', 'σ')
    t = t.replace(r'\approx', '≈')
    t = t.replace(r'\pm', '±')
    t = t.replace(r'\ge', '≥')
    t = t.replace(r'\le', '≤')
    t = t.replace(r'\times', '×')
    t = t.replace(r'\text{', '').replace('}', '')
    t = t.replace('$', '')
    return t.strip()

# Read Chapter 4
with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

tables_data = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith('*Bảng 4.'):
        title = line.strip('* ')
        i += 1
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        raw_rows = []
        while i < len(lines) and lines[i].strip().startswith('|'):
            row_str = lines[i].strip()
            if not re.match(r'^\|(\s*:?-+:?\s*\|)+$', row_str):
                cells = [c.strip() for c in row_str.split('|')[1:-1]]
                raw_rows.append(cells)
            i += 1
        if raw_rows:
            tables_data.append((title, raw_rows))
    else:
        i += 1

# Custom widths per table (in cm, sum = 17.0 cm)
table_col_widths = {
    1: [3.5, 4.0, 6.0, 3.5],                    # Bảng 4.1
    2: [3.5, 3.5, 2.8, 3.8, 3.4],               # Bảng 4.2
    3: [4.8, 5.2, 4.2, 2.8],                    # Bảng 4.3
    4: [2.5, 2.0, 2.7, 2.3, 2.0, 2.0, 1.7, 1.8], # Bảng 4.4
    5: [2.2, 1.7, 1.7, 1.7, 1.8, 2.5, 2.0, 1.7, 1.7], # Bảng 4.5
    6: [4.0, 1.8, 1.8, 1.8, 1.8, 2.5, 1.8, 1.5], # Bảng 4.6
    7: [2.2, 1.7, 1.7, 1.7, 1.8, 2.5, 2.0, 1.7, 1.7], # Bảng 4.7
    8: [1.2, 1.6, 2.4, 2.4, 1.6, 2.2, 1.5, 2.3, 1.8]  # Bảng 4.8
}

doc = docx.Document()
for s in doc.sections:
    s.page_width = Cm(21.0)
    s.page_height = Cm(29.7)
    s.top_margin = Cm(2.0)
    s.bottom_margin = Cm(2.0)
    s.left_margin = Cm(2.0)
    s.right_margin = Cm(2.0)

# Main Title
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(0)
p.paragraph_format.space_after = Pt(8)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("TẬP HỢP TOÀN BỘ CÁC BẢNG BIỂU CHƯƠNG 4 (CHUẨN HÓA MICROSOFT WORD)")
r.font.name = "Times New Roman"
r.font.size = Pt(13)
r.font.bold = True
r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

sub_p = doc.add_paragraph()
sub_p.paragraph_format.space_after = Pt(14)
sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r_sub = sub_p.add_run("Định dạng APA Viện Hàn Lâm: Font Times New Roman, phân bố độ rộng cột tối ưu, số liệu căn phải, sẵn sàng sao chép trực tiếp vào luận văn")
r_sub.font.name = "Times New Roman"
r_sub.font.size = Pt(10)
r_sub.font.italic = True
r_sub.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

for tbl_idx, (title, rows) in enumerate(tables_data, 1):
    tp = doc.add_paragraph()
    tp.paragraph_format.space_before = Pt(14)
    tp.paragraph_format.space_after = Pt(4)
    tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tr = tp.add_run(clean_text(title))
    tr.font.name = "Times New Roman"
    tr.font.size = Pt(10.5)
    tr.font.bold = True
    tr.font.italic = True
    tr.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    num_rows = len(rows)
    num_cols = len(rows[0])
    
    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    col_widths_cm = table_col_widths.get(tbl_idx, [17.0 / num_cols] * num_cols)

    for r_idx, row in enumerate(rows):
        is_header = (r_idx == 0)
        is_total = (r_idx == num_rows - 1 and ('Tổng' in row[0] or 'Toàn chu kỳ' in row[-1]))
        row_cells = table.rows[r_idx].cells
        
        for c_idx, cell_value in enumerate(row):
            cell = row_cells[c_idx]
            cell.width = Cm(col_widths_cm[c_idx])
            set_cell_margins(cell, top=60 if not is_header else 100,
                                   bottom=60 if not is_header else 100,
                                   left=80, right=80)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            
            if is_header:
                set_cell_shading(cell, "F1F5F9")
            elif is_total:
                set_cell_shading(cell, "F8FAFC")
            elif r_idx % 2 == 0:
                set_cell_shading(cell, "FAFAFA")
                
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            
            clean_val = clean_text(cell_value)
            
            if is_header:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                if any(clean_val.endswith(suffix) for suffix in ['%', 'USD', 'MB', 'MiB', 'KiB', 'ms', 'FPS', 'bytes', 'lệnh', 'points', 'μs']) or re.match(r'^[+-]?\d+([.,]\d+)?$', clean_val):
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif c_idx == 0 and len(clean_val) < 15:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            
            run = p.add_run(clean_val)
            run.font.name = "Times New Roman"
            run.font.size = Pt(8.5 if num_cols >= 8 else 9.5)
            if is_header or is_total or ('**' in cell_value):
                run.font.bold = True
            if is_header:
                run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

out_1 = r"Kho_Do_An/Quant_AI_V2.2/docs/thesis/Tat_ca_bang_Chuong_4.docx"
out_2 = r"C:\Users\vong2\.gemini\antigravity\brain\812099d0-d223-4c93-b8df-d681e60c7043\Tat_ca_bang_Chuong_4.docx"

doc.save(out_1)
doc.save(out_2)

print("Saved Tat_ca_bang_Chuong_4.docx successfully with custom widths!")

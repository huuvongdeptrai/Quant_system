import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
from lxml import etree
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

xslt_path = r'C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL'
xslt = etree.parse(xslt_path)
transform = etree.XSLT(xslt)

def mml_to_omml(mml_str):
    dom = etree.fromstring(mml_str.encode('utf-8'))
    omml = transform(dom)
    return parse_xml(etree.tostring(omml.getroot()))

def set_cell_margins(cell, top=100, bottom=100, left=120, right=120):
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

doc = docx.Document()

# Page setup: A4, Margins 2cm
for section in doc.sections:
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

# Title
title_p = doc.add_paragraph()
title_p.paragraph_format.space_before = Pt(0)
title_p.paragraph_format.space_after = Pt(8)
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title_p.add_run("Bảng 3.5: Bảng đặc tả toán học và thông số vận hành của 11 đặc trưng vi cấu trúc")
run.font.name = "Times New Roman"
run.font.size = Pt(11)
run.font.bold = True
run.font.italic = True
run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

# Data for 11 features
headers = ["Vị trí vector", "Tên biến trong mã nguồn", "Công thức toán học / Quy tắc xác định", "Cửa sổ dữ liệu", "Đơn vị / Miền giá trị", "Ý nghĩa vi cấu trúc"]
col_widths = [Cm(1.1), Cm(1.9), Cm(5.8), Cm(2.2), Cm(2.1), Cm(3.9)]

features = [
    {
        "pos": "x1",
        "name": "is_buy",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <msub><mi>x</mi><mn>1</mn></msub><mo>=</mo>
          <mrow><mo>{</mo><mtable columnalign="left">
            <mtr><mtd><mn>1</mn><mtext>,  nếu tín hiệu Mua (BUY)</mtext></mtd></mtr>
            <mtr><mtd><mn>0</mn><mtext>,  nếu tín hiệu Bán (SELL)</mtext></mtd></mtr>
          </mtable></mrow>
        </math>""",
        "window": "Nến hiện tại t",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mo>{</mo><mn>0</mn><mo>,</mo><mn>1</mn><mo>}</mo></math>""",
        "meaning": "Chiều hướng của tín hiệu sơ cấp"
    },
    {
        "pos": "x2",
        "name": "vol_ratio",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtable columnalign="left">
            <mtr><mtd>
              <mfrac><msub><mi>V</mi><mi>t</mi></msub><mrow><mo>max</mo><mo>(</mo><mn>1.0</mn><mo>,</mo><msub><mover><mi>V</mi><mo>¯</mo></mover><mn>20</mn></msub><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
            <mtr><mtd>
              <mtext>với </mtext><msub><mover><mi>V</mi><mo>¯</mo></mover><mn>20</mn></msub><mo>=</mo><mfrac><mn>1</mn><mn>20</mn></mfrac><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mn>20</mn></munderover><msub><mi>V</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub>
            </mtd></mtr>
          </mtable>
        </math>""",
        "window": "20 nến quá khứ (t-20 đến t-1)",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>[</mo><mn>0</mn><mo>,</mo><mo>+</mo><mo>∞</mo><mo>)</mo></math>""",
        "meaning": "Bùng nổ khối lượng so với nền lịch sử 20 nến"
    },
    {
        "pos": "x3",
        "name": "adx",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtext>Chỉ số ADX 14 chu kỳ theo Wilder</mtext>
        </math>""",
        "window": "Tối thiểu 28 nến lịch sử",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>[</mo><mn>0</mn><mo>,</mo><mn>100</mn><mo>]</mo></math>""",
        "meaning": "Xung lực và độ mạnh của xu hướng giá"
    },
    {
        "pos": "x4",
        "name": "gk_vol",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <msqrt>
            <mrow>
              <mo>max</mo><mo>(</mo><mn>0</mn><mo>,</mo><mfrac><mn>1</mn><mn>14</mn></mfrac><munderover><mo>∑</mo><mrow><mi>j</mi><mo>=</mo><mn>0</mn></mrow><mn>13</mn></munderover><msubsup><mi>σ</mi><mtext>GK</mtext><mn>2</mn></msubsup><mo>(</mo><mi>t</mi><mo>-</mo><mi>j</mi><mo>)</mo><mo>)</mo>
            </mrow>
          </msqrt>
          <mo>×</mo><mn>1000</mn>
        </math>""",
        "window": "14 nến OHLC gần nhất",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>[</mo><mn>0</mn><mo>,</mo><mo>+</mo><mo>∞</mo><mo>)</mo></math>""",
        "meaning": "Độ biến động vi cấu trúc Garman-Klass [15]"
    },
    {
        "pos": "x5",
        "name": "cvd_proxy",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mfrac>
            <mrow><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>0</mn></mrow><mn>9</mn></munderover><msub><mi>s_vol</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub></mrow>
            <mrow><mo>max</mo><mo>(</mo><mn>1.0</mn><mo>,</mo><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>0</mn></mrow><mn>9</mn></munderover><msub><mi>V</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub><mo>)</mo></mrow>
          </mfrac>
        </math>""",
        "window": "10 nến gần nhất",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>[</mo><mo>-</mo><mn>1.0</mn><mo>,</mo><mo>+</mo><mn>1.0</mn><mo>]</mo></math>""",
        "meaning": "Áp lực mua bán đại diện từ Tick Volume"
    },
    {
        "pos": "x6",
        "name": "vwap_zscore",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtable columnalign="left">
            <mtr><mtd>
              <mfrac><mrow><msub><mi>Close</mi><mi>t</mi></msub><mo>-</mo><mi>VWAP</mi><mo>(</mo><mi>t</mi><mo>)</mo></mrow><mrow><mtext>safe_atr</mtext><mo>(</mo><mi>t</mi><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
            <mtr><mtd>
              <mtext>với </mtext><mi>VWAP</mi><mo>=</mo><mfrac><mrow><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>0</mn></mrow><mn>95</mn></munderover><msub><mi>C</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub><msub><mi>V</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub></mrow><mrow><mo>max</mo><mo>(</mo><mn>1.0</mn><mo>,</mo><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>0</mn></mrow><mn>95</mn></munderover><msub><mi>V</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
          </mtable>
        </math>""",
        "window": "96 nến M15 (24 giờ cuốn chiếu)",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>(</mo><mo>-</mo><mo>∞</mo><mo>,</mo><mo>+</mo><mo>∞</mo><mo>)</mo></math>""",
        "meaning": "Độ lệch giá so với VWAP 24h chuẩn hóa theo ATR"
    },
    {
        "pos": "x7",
        "name": "ema_spread",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mfrac><mrow><mo>|</mo><msub><mi>EMA</mi><mn>20</mn></msub><mo>(</mo><mi>t</mi><mo>)</mo><mo>-</mo><msub><mi>EMA</mi><mn>50</mn></msub><mo>(</mo><mi>t</mi><mo>)</mo><mo>|</mo></mrow><mrow><mtext>safe_atr</mtext><mo>(</mo><mi>t</mi><mo>)</mo></mrow></mfrac>
        </math>""",
        "window": "50 nến lịch sử",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>[</mo><mn>0</mn><mo>,</mo><mo>+</mo><mo>∞</mo><mo>)</mo></math>""",
        "meaning": "Động lượng phân kỳ giữa chu kỳ ngắn và trung"
    },
    {
        "pos": "x8",
        "name": "headroom",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtable columnalign="left">
            <mtr><mtd>
              <mtext>Buy: </mtext><mfrac><mrow><msub><mi>High</mi><mn>30</mn></msub><mo>(</mo><mi>t</mi><mo>)</mo><mo>-</mo><msub><mi>Close</mi><mi>t</mi></msub></mrow><mrow><mtext>safe_atr</mtext><mo>(</mo><mi>t</mi><mo>)</mo></mrow></mfrac><mtext>;  Sell: </mtext><mfrac><mrow><msub><mi>Close</mi><mi>t</mi></msub><mo>-</mo><msub><mi>Low</mi><mn>30</mn></msub><mo>(</mo><mi>t</mi><mo>)</mo></mrow><mrow><mtext>safe_atr</mtext><mo>(</mo><mi>t</mi><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
            <mtr><mtd>
              <mtext>với </mtext><msub><mi>High</mi><mn>30</mn></msub><mo>=</mo><munder><mo>max</mo><mrow><mn>1</mn><mo>≤</mo><mi>i</mi><mo>≤</mo><mn>30</mn></mrow></munder><msub><mi>High</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub><mtext>, </mtext><msub><mi>Low</mi><mn>30</mn></msub><mo>=</mo><munder><mo>min</mo><mrow><mn>1</mn><mo>≤</mo><mi>i</mi><mo>≤</mo><mn>30</mn></mrow></munder><msub><mi>Low</mi><mrow><mi>t</mi><mo>-</mo><mi>i</mi></mrow></msub>
            </mtd></mtr>
          </mtable>
        </math>""",
        "window": "30 nến quá khứ (t-30 đến t-1)",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Số thực </mtext><mo>(</mo><mo>-</mo><mo>∞</mo><mo>,</mo><mo>+</mo><mo>∞</mo><mo>)</mo></math>""",
        "meaning": "Khoảng đệm giá tới cản đỉnh/đáy 30 nến gần nhất"
    },
    {
        "pos": "x9",
        "name": "wick_ratio",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtable columnalign="left">
            <mtr><mtd>
              <mtext>Buy: </mtext><mfrac><mrow><mi>High</mi><mo>-</mo><mo>max</mo><mo>(</mo><mi>C</mi><mo>,</mo><mi>O</mi><mo>)</mo></mrow><mrow><mo>max</mo><mo>(</mo><mi>H</mi><mo>-</mo><mi>L</mi><mo>,</mo><msup><mn>10</mn><mn>-4</mn></msup><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
            <mtr><mtd>
              <mtext>Sell: </mtext><mfrac><mrow><mo>min</mo><mo>(</mo><mi>C</mi><mo>,</mo><mi>O</mi><mo>)</mo><mo>-</mo><mi>Low</mi></mrow><mrow><mo>max</mo><mo>(</mo><mi>H</mi><mo>-</mo><mi>L</mi><mo>,</mo><msup><mn>10</mn><mn>-4</mn></msup><mo>)</mo></mrow></mfrac>
            </mtd></mtr>
          </mtable>
        </math>""",
        "window": "Nến tín hiệu t",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mtext>Tỷ lệ </mtext><mo>[</mo><mn>0.0</mn><mo>,</mo><mn>1.0</mn><mo>]</mo></math>""",
        "meaning": "Tỷ lệ bóng nến bất lợi cản trở đà tăng (Buy) hoặc đà giảm (Sell)"
    },
    {
        "pos": "x10",
        "name": "hour",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mtext>bar_open_hour (UTC),  </mtext><mn>0</mn><mo>≤</mo><mi>hour</mi><mo>≤</mo><mn>23</mn>
        </math>""",
        "window": "Nến tín hiệu mới nhất đã đóng (t)",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mo>{</mo><mn>0</mn><mo>,</mo><mn>1</mn><mo>,</mo><mo>…</mo><mo>,</mo><mn>23</mn><mo>}</mo></math>""",
        "meaning": "Khung giờ bắt đầu nến tín hiệu theo phiên giao dịch (Á, Âu, Mỹ)"
    },
    {
        "pos": "x11",
        "name": "dow",
        "mml": """<math xmlns="http://www.w3.org/1998/Math/MathML">
          <mi>dow</mi><mo>∈</mo><mo>{</mo><mn>0</mn><mo>,</mo><mn>1</mn><mo>,</mo><mn>2</mn><mo>,</mo><mn>3</mn><mo>,</mo><mn>4</mn><mo>}</mo>
        </math>""",
        "window": "Nến hiện tại t",
        "range_mml": """<math xmlns="http://www.w3.org/1998/Math/MathML"><mo>{</mo><mn>0</mn><mo>,</mo><mn>1</mn><mo>,</mo><mn>2</mn><mo>,</mo><mn>3</mn><mo>,</mo><mn>4</mn><mo>}</mo></math>""",
        "meaning": "Ngày trong tuần theo lịch chuẩn (0 = Thứ Hai, 4 = Thứ Sáu)"
    }
]

table = doc.add_table(rows=1 + len(features), cols=6)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
set_table_borders(table)

# Format Header
hdr_cells = table.rows[0].cells
for idx, text in enumerate(headers):
    hdr_cells[idx].width = col_widths[idx]
    set_cell_margins(hdr_cells[idx], top=120, bottom=120, left=100, right=100)
    set_cell_shading(hdr_cells[idx], "F1F5F9")
    hdr_cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = hdr_cells[idx].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

# Populate Data Rows
for row_idx, f in enumerate(features, start=1):
    row_cells = table.rows[row_idx].cells
    for c_idx in range(6):
        row_cells[c_idx].width = col_widths[c_idx]
        set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=100, right=100)
        row_cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if row_idx % 2 == 0:
            set_cell_shading(row_cells[c_idx], "F8FAFC")
    
    # Col 0: Position
    p0 = row_cells[0].paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.paragraph_format.space_before = Pt(0)
    p0.paragraph_format.space_after = Pt(0)
    mml_pos = f"""<math xmlns="http://www.w3.org/1998/Math/MathML"><msub><mi>x</mi><mrow>{f['pos'][1:]}</mrow></msub></math>"""
    p0._p.append(mml_to_omml(mml_pos))
    
    # Col 1: Variable Name
    p1 = row_cells[1].paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after = Pt(0)
    r1 = p1.add_run(f['name'])
    r1.font.name = "Consolas"
    r1.font.size = Pt(9.5)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    
    # Col 2: Formula
    p2 = row_cells[2].paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p2.paragraph_format.space_before = Pt(0)
    p2.paragraph_format.space_after = Pt(0)
    p2._p.append(mml_to_omml(f['mml']))
    
    # Col 3: Data window
    p3 = row_cells[3].paragraphs[0]
    p3.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p3.paragraph_format.space_before = Pt(0)
    p3.paragraph_format.space_after = Pt(0)
    r3 = p3.add_run(f['window'])
    r3.font.name = "Times New Roman"
    r3.font.size = Pt(9.5)
    
    # Col 4: Range
    p4 = row_cells[4].paragraphs[0]
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.paragraph_format.space_before = Pt(0)
    p4.paragraph_format.space_after = Pt(0)
    p4._p.append(mml_to_omml(f['range_mml']))
    
    # Col 5: Meaning
    p5 = row_cells[5].paragraphs[0]
    p5.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p5.paragraph_format.space_before = Pt(0)
    p5.paragraph_format.space_after = Pt(0)
    r5 = p5.add_run(f['meaning'])
    r5.font.name = "Times New Roman"
    r5.font.size = Pt(9.5)

# Save file to docs and artifact directory
out_path_1 = r"Kho_Do_An/Quant_AI_V2.2/docs/thesis/Bang_3_5_Dac_ta_11_dac_trung.docx"
out_path_2 = r"C:\Users\vong2\.gemini\antigravity\brain\812099d0-d223-4c93-b8df-d681e60c7043\Bang_3_5_Dac_ta_11_dac_trung.docx"

doc.save(out_path_1)
doc.save(out_path_2)

print(f"Generated DOCX successfully:\n1. {out_path_1}\n2. {out_path_2}")

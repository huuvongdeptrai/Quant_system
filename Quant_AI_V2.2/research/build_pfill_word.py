import sys
sys.stdout.reconfigure(encoding='utf-8')
from lxml import etree
import docx
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.oxml import parse_xml

xslt_path = r'C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL'
xslt = etree.parse(xslt_path)
transform = etree.XSLT(xslt)

mml = """<math xmlns="http://www.w3.org/1998/Math/MathML">
  <msub><mi>P</mi><mtext>fill</mtext></msub>
  <mo>=</mo>
  <mrow>
    <mo>{</mo>
    <mtable columnalign="left">
      <mtr>
        <mtd><msub><mi>P</mi><mtext>order</mtext></msub><mo>+</mo><mi>s</mi><mo>,</mo></mtd>
        <mtd><mtext>&#160;&#160;đối với lệnh Mua (BUY - giá khớp bị trượt lên cao hơn bất lợi)</mtext></mtd>
      </mtr>
      <mtr>
        <mtd><msub><mi>P</mi><mtext>order</mtext></msub><mo>-</mo><mi>s</mi><mo>,</mo></mtd>
        <mtd><mtext>&#160;&#160;đối với lệnh Bán (SELL - giá khớp bị trượt xuống thấp hơn bất lợi)</mtext></mtd>
      </mtr>
    </mtable>
  </mrow>
</math>"""

dom = etree.fromstring(mml.encode('utf-8'))
omml = transform(dom)

doc = docx.Document()
for section in doc.sections:
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

p_intro = doc.add_paragraph()
r = p_intro.add_run("Công thức mô hình trượt giá bất lợi ngẫu nhiên (Mục 3.10.1):")
r.font.name = "Times New Roman"
r.font.size = Pt(12)
r.font.bold = True

p_eq = doc.add_paragraph()
p_eq.paragraph_format.space_before = Pt(6)
p_eq.paragraph_format.space_after = Pt(6)
p_eq._p.append(parse_xml(etree.tostring(omml.getroot())))

p_note = doc.add_paragraph()
r2 = p_note.add_run("Hướng dẫn sử dụng: Chọn toàn bộ công thức trên (Ctrl + C) và dán thẳng (Ctrl + V) vào tài liệu luận văn Word của bạn. Công thức đã được nhúng dưới dạng Equation OMML gốc với font Cambria Math, hiển thị dấu ngoặc nhọn lớn và tiếng Việt có dấu chuẩn 100%.")
r2.font.name = "Times New Roman"
r2.font.size = Pt(10.5)
r2.font.italic = True
r2.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

out_path_1 = r"Kho_Do_An/Quant_AI_V2.2/docs/thesis/Cong_thuc_truot_gia_Pfill.docx"
out_path_2 = r"C:\Users\vong2\.gemini\antigravity\brain\812099d0-d223-4c93-b8df-d681e60c7043\Cong_thuc_truot_gia_Pfill.docx"

doc.save(out_path_1)
doc.save(out_path_2)

print("Saved Cong_thuc_truot_gia_Pfill.docx successfully!")

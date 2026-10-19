"""生成《电网设备缺陷分级标准与缺陷库》PDF（供专家审阅与结构化补充）。

用法：python scripts/gen_defect_pdf.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

OUT = Path(__file__).resolve().parent.parent / "电网设备缺陷分级标准与缺陷库.pdf"

ZH = ParagraphStyle("zh", fontName="STSong-Light", fontSize=11, leading=18)
TITLE = ParagraphStyle("title", fontName="STSong-Light", fontSize=20, leading=28, alignment=1, spaceAfter=4)
SUB = ParagraphStyle("sub", fontName="STSong-Light", fontSize=10, leading=14, alignment=1, textColor=colors.grey)
H2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=14, leading=20, spaceBefore=16, spaceAfter=8)

TABLE_STYLE = TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e0e7")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
])


def main() -> None:
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, topMargin=40, bottomMargin=40, leftMargin=48, rightMargin=48)
    story = []

    story.append(Paragraph("电网设备缺陷分级标准与缺陷库", TITLE))
    story.append(Paragraph("依据 Q/GDW 745-2012《配电网设备缺陷分类标准》、DL/T 1685-2017《输变电设备状态评价导则》整理 · 供专家审阅与补充", SUB))
    story.append(Spacer(1, 20))

    # 一、缺陷三级定义
    story.append(Paragraph("一、缺陷三级定义（Q/GDW 745-2012）", H2))
    story.append(Paragraph("<b>一般缺陷</b>：设备本身及周围环境出现不正常情况，一般不威胁设备的安全运行，可列入年、季检修计划或日常维护工作中处理。", ZH))
    story.append(Paragraph("<b>严重缺陷</b>：设备处于异常状态，可能发展为事故，但设备仍可在一定时间内继续运行，须加强监视并进行检修处理。", ZH))
    story.append(Paragraph("<b>危急缺陷</b>：严重威胁设备的安全运行，不及时处理随时有可能导致事故，必须尽快消除或采取必要的安全技术措施处理。", ZH))

    # 二、消缺时限
    story.append(Paragraph("二、消缺时限", H2))
    story.append(Table(
        [["缺陷等级", "消缺时限", "备注"],
         ["危急", "≤ 24 小时", "超期未消除即为安全隐患"],
         ["严重", "≤ 30 天", "超期未消除即为安全隐患"],
         ["一般", "列入年/季检修计划", "结合检修计划尽早消除"]],
        style=TABLE_STYLE,
    ))

    # 三、状态四态
    story.append(Paragraph("三、设备状态四态（DL/T 1685-2017）", H2))
    story.append(Table(
        [["状态", "定义", "处置策略"],
         ["正常", "各状态量稳定且在警示值、注意值以内", "可正常运行，延长检修周期"],
         ["注意", "状态量变化趋势接近标准限值但未超过", "加强监视、缩短试验周期"],
         ["异常", "单项重要状态量接近或略微超过标准限值", "重点监视，适时停电检修"],
         ["严重", "单项重要状态量严重超过标准限值", "尽快停电检修"]],
        style=TABLE_STYLE,
    ))

    # 四、等级映射
    story.append(Paragraph("四、等级映射规则（告警/状态 → 缺陷）", H2))
    story.append(Paragraph("告警等级与状态四态是缺陷分级的输入信号，映射结果为建议等级，最终等级由缺陷分级规则判定：", ZH))
    story.append(Table(
        [["信号", "信号值", "建议缺陷等级"],
         ["告警", "提示 / 重要 / 紧急", "一般 / 严重 / 危急"],
         ["状态", "正常 / 注意 / 异常 / 严重", "无 / 一般 / 严重 / 危急"]],
        style=TABLE_STYLE,
    ))
    story.append(Paragraph("冲突裁决：同一设备多路信号映射结果不一致时，取最高等级（从严），并建议人工复核。", ZH))

    # 五、现有关键词规则
    story.append(Paragraph("五、现有关键词规则（系统内置，供审阅）", H2))
    story.append(Paragraph("系统当前的缺陷分级采用关键词规则，命中即返回：", ZH))
    story.append(Table(
        [["等级", "关键词"],
         ["危急", "烧损、烧毁、闪络、爬电、击穿、放电、冒烟、起火、爆炸、严重漏油、严重发热、严重过热、拒分、拒合、误动、随时可能、立即停运、立即处理"],
         ["严重", "异常、超标、泄漏、发热、过热、需尽快、明显、隐患、加强监视、受损、破损、渗油、沉降"],
         ["一般", "轻微、不影响、列入计划、不威胁、较轻、影响较小"]],
        style=TABLE_STYLE,
    ))
    story.append(Paragraph("说明：关键词规则为简化实现，覆盖不全。治本方案是下方结构化缺陷库——由设备类别、部件、部位、程度精确判定等级。", ZH))

    # 六、缺陷库模板
    story.append(Paragraph("六、结构化缺陷库模板（供专家填写）", H2))
    story.append(Paragraph("请按下列字段补充缺陷库条目，系统据此实现精确分级：", ZH))
    story.append(Table(
        [["设备类别", "部件", "部位", "缺陷内容", "程度", "参考等级"],
         ["变压器", "本体", "套管", "套管渗漏油", "明显", "严重"],
         ["开关柜", "断路器", "触头", "触头温升超标", "—", "严重"],
         ["电缆", "护层", "护层", "护层绝缘受损", "—", "严重"],
         ["", "", "", "", "", ""],
         ["", "", "", "", "", ""],
         ["", "", "", "", "", ""],
         ["", "", "", "", "", ""],
         ["", "", "", "", "", ""]],
        style=TABLE_STYLE,
    ))

    doc.build(story)
    print(f"已生成：{OUT}")


if __name__ == "__main__":
    main()

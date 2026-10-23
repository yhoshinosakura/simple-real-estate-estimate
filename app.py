from __future__ import annotations

from datetime import date
from io import BytesIO

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from xml.sax.saxutils import escape


st.set_page_config(page_title="不動産簡易査定書", page_icon="⌂", layout="wide")

ROUTE_MULTIPLIER = {"相続税路線価": 1.2, "固定資産税路線価": 1.3}
SQM_TO_TSUBO = 0.3025
RED = colors.HexColor("#b5103d")
PALE = colors.HexColor("#fff1f3")
INK = colors.HexColor("#17243a")
MUTED = colors.HexColor("#63728a")
LINE = colors.HexColor("#d8e0eb")
BLUE = colors.HexColor("#0068a6")
NAVY = colors.HexColor("#46647b")
PINK = colors.HexColor("#e77e9b")
PALE_BLUE = colors.HexColor("#edf2f5")
PAPER = colors.HexColor("#fffefa")


def yen(value: float) -> str:
    return f"{round(value):,}円"


def man(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}万円"


def to_tsubo(sqm: float) -> float:
    return sqm * SQM_TO_TSUBO


def residual_rate(age: float) -> float:
    # User's stated simple rule: 25 years to 10%; for 40+ use rule-4 default below.
    if age >= 40:
        return 0.0
    return max(0.10, 1.0 - 0.90 * max(0.0, age) / 25.0)


def make_pdf(data: dict) -> bytes:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    pdfmetrics.registerFontFamily(
        "HeiseiKakuGo-W5",
        normal="HeiseiKakuGo-W5",
        bold="HeiseiKakuGo-W5",
        italic="HeiseiKakuGo-W5",
        boldItalic="HeiseiKakuGo-W5",
    )
    buffer = BytesIO()
    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h), pageCompression=1)
    pdf.setTitle("不動産簡易査定書")
    if data.get("company"):
        pdf.setAuthor(data["company"])
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("report_title", parent=base["Title"], fontName="HeiseiKakuGo-W5", fontSize=25, leading=31, textColor=NAVY, alignment=TA_LEFT),
        "body": ParagraphStyle("report_body", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=11, leading=17, textColor=INK, wordWrap="CJK"),
        "small": ParagraphStyle("report_small", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=8.5, leading=13, textColor=MUTED, wordWrap="CJK"),
        "card_label": ParagraphStyle("report_card_label", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=10, leading=14, textColor=NAVY, wordWrap="CJK"),
        "card_value": ParagraphStyle("report_card_value", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=15, leading=19, textColor=INK, wordWrap="CJK"),
        "center_label": ParagraphStyle("report_center_label", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=13, leading=18, textColor=NAVY, alignment=TA_CENTER, wordWrap="CJK"),
        "center_value": ParagraphStyle("report_center_value", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=28, leading=34, textColor=NAVY, alignment=TA_CENTER, wordWrap="CJK"),
        "mini_value": ParagraphStyle("report_mini_value", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=15, leading=19, textColor=NAVY, alignment=TA_CENTER, wordWrap="CJK"),
        "right_value": ParagraphStyle("report_right_value", parent=base["Normal"], fontName="HeiseiKakuGo-W5", fontSize=20, leading=26, textColor=NAVY, alignment=TA_RIGHT, wordWrap="CJK"),
    }

    def p(text: str, style: str = "body") -> Paragraph:
        return Paragraph(text, styles[style])

    def draw_para(text: str, style: str, x: float, top: float, width: float) -> float:
        para = p(text, style)
        _, h = para.wrap(width, page_h)
        para.drawOn(pdf, x, top - h)
        return top - h

    def frame(page_no: int, title: str, subtitle: str = "") -> None:
        pdf.setFillColor(PAPER)
        pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        pdf.setStrokeColor(NAVY)
        pdf.setLineWidth(0.8)
        pdf.rect(8 * mm, 8 * mm, page_w - 16 * mm, page_h - 16 * mm, fill=0, stroke=1)
        pdf.setStrokeColor(colors.HexColor("#d8e0e5"))
        pdf.setLineWidth(0.35)
        pdf.line(14 * mm, 15 * mm, page_w - 14 * mm, 15 * mm)
        pdf.setFont("HeiseiKakuGo-W5", 7.5)
        pdf.setFillColor(MUTED)
        if data.get("company"):
            pdf.drawString(15 * mm, 10 * mm, data["company"])
        pdf.drawRightString(page_w - 15 * mm, 10 * mm, f"{page_no} / 4")
        pdf.setFont("HeiseiKakuGo-W5", 23 if page_no == 1 else 20)
        pdf.setFillColor(NAVY)
        pdf.drawString(16 * mm, page_h - 27 * mm, title)
        if subtitle:
            pdf.setFont("HeiseiKakuGo-W5", 9)
            pdf.setFillColor(MUTED)
            pdf.drawString(16 * mm, page_h - 34 * mm, subtitle)
        pdf.setStrokeColor(PINK)
        pdf.setLineWidth(1.8)
        pdf.line(16 * mm, page_h - 39 * mm, page_w - 16 * mm, page_h - 39 * mm)

    def card(x: float, y: float, w: float, h: float, label: str, value: str) -> None:
        pdf.setFillColor(PALE_BLUE)
        pdf.setStrokeColor(NAVY)
        pdf.setLineWidth(0.6)
        pdf.roundRect(x, y, w, h, 2 * mm, fill=1, stroke=1)
        pdf.setStrokeColor(colors.HexColor("#b5c4ce"))
        pdf.line(x + 19 * mm, y + 4 * mm, x + 19 * mm, y + h - 4 * mm)
        draw_para(escape(label), "card_label", x + 23 * mm, y + h - 7 * mm, w - 27 * mm)
        draw_para(escape(value), "card_value", x + 23 * mm, y + h - 15 * mm, w - 27 * mm)

    def pill(x: float, y: float, w: float, text: str, fill=NAVY) -> None:
        pdf.setFillColor(fill)
        pdf.roundRect(x, y, w, 10 * mm, 1.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("HeiseiKakuGo-W5", 10)
        pdf.drawCentredString(x + w / 2, y + 3.2 * mm, text)

    margin = 16 * mm
    content_w = page_w - margin * 2
    gap = 7 * mm

    # Page 1: estimate cover and property summary.
    frame(1, "不動産査定報告書", "机上査定による価格のご案内")
    pdf.setFont("HeiseiKakuGo-W5", 11)
    pdf.setFillColor(INK)
    pdf.drawString(margin, page_h - 51 * mm, f"{data['client']} 様")
    pdf.setFont("HeiseiKakuGo-W5", 8.5)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(page_w - margin, page_h - 51 * mm, data["report_date"])
    hero_y, hero_h = page_h - 112 * mm, 49 * mm
    pdf.setFillColor(colors.HexColor("#f5f7f8"))
    pdf.setStrokeColor(PINK)
    pdf.setLineWidth(1)
    pdf.roundRect(margin, hero_y, content_w, hero_h, 2 * mm, fill=1, stroke=1)
    draw_para("ご提案取引価格", "center_label", margin, hero_y + hero_h - 7 * mm, content_w)
    price_text = f"{man(data['proposal_low'] / 10000, 0)} ～ {man(data['proposal_high'] / 10000, 0)} 前後"
    draw_para(escape(price_text), "center_value", margin, hero_y + hero_h - 17 * mm, content_w)
    draw_para("査定評価額をもとに設定した売却価格の目安です。", "small", margin + 4 * mm, hero_y + 5 * mm, content_w - 8 * mm)

    pdf.setFont("HeiseiKakuGo-W5", 15)
    pdf.setFillColor(NAVY)
    pdf.drawString(margin, hero_y - 12 * mm, "査定対象物件の基本情報")
    card_h, card_gap = 30 * mm, 5 * mm
    col_w = (content_w - card_gap) / 2
    row1_y = hero_y - 48 * mm
    address = data["address"]
    card(margin, row1_y, col_w, card_h, "所在地", escape(address))
    card(margin + col_w + card_gap, row1_y, col_w, card_h, "土地面積", f"{data['land_tsubo']:.2f}坪（{data['land_sqm']:,.2f}㎡）")
    row2_y = row1_y - card_h - card_gap
    building_summary = f"{data['building_tsubo']:.2f}坪（{data['building_sqm']:,.2f}㎡）" if data["building_sqm"] > 0 else "なし"
    age_summary = f"築{data['age']:g}年・{data['structure']}" if data["property_type"] != "土地" else "土地のみ"
    card(margin, row2_y, col_w, card_h, "建物面積", building_summary)
    card(margin + col_w + card_gap, row2_y, col_w, card_h, "物件種別・築年数", f"{data['property_type']}　{age_summary}")
    pdf.showPage()

    # Page 2: land appraisal.
    frame(2, "Step 1　土地の評価額", "路線価または入力された坪単価をもとに算出")
    top = page_h - 53 * mm
    left_w = 105 * mm
    pdf.setStrokeColor(colors.HexColor("#b5c4ce"))
    pdf.line(margin + left_w + 8 * mm, 35 * mm, margin + left_w + 8 * mm, page_h - 53 * mm)
    pdf.setFont("HeiseiKakuGo-W5", 12)
    pdf.setFillColor(NAVY)
    pdf.drawString(margin, top, "査定地周辺の取引相場")
    market_text = ""
    if data["market_low"] > 0 and data["market_high"] > 0:
        market_text = f"坪{data['market_low']:g}万円 ～ {data['market_high']:g}万円前後"
    elif data["market_low"] > 0:
        market_text = f"坪{data['market_low']:g}万円前後"
    elif data["market_high"] > 0:
        market_text = f"坪{data['market_high']:g}万円前後"
    pdf.setFont("HeiseiKakuGo-W5", 9.5)
    pdf.setFillColor(INK)
    pdf.drawString(margin, top - 8 * mm, "査定地周辺では通常、")
    market_detail = f"{market_text}での取引が見られます。" if market_text else "入力された土地単価を基準に評価します。"
    pdf.drawString(margin, top - 16 * mm, market_detail)
    basis_y = top - 60 * mm
    pdf.setFillColor(PALE_BLUE)
    pdf.setStrokeColor(NAVY)
    pdf.roundRect(margin, basis_y, left_w, 39 * mm, 2 * mm, fill=1, stroke=1)
    if data["route_multiplier"]:
        basis = (f"{data['route_type']}<br/>{data['route_value']:,.0f}円/㎡ × {data['route_multiplier']:.1f} × 3.3058<br/>"
                 f"＝ {man(data['land_unit'], 2)}/坪")
    else:
        basis = f"査定単価<br/>{man(data['land_unit'], 2)}/坪"
    draw_para(basis, "body", margin + 7 * mm, basis_y + 32 * mm, left_w - 14 * mm)
    draw_para("路線価にはご指定の補正倍率を適用し、坪単価に換算しています。", "small", margin, basis_y - 9 * mm, left_w)

    rx = margin + left_w + 17 * mm
    rw = content_w - left_w - 17 * mm
    pdf.setFont("HeiseiKakuGo-W5", 11)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(rx + rw, top, "土地面積 × 査定単価")
    formula = f"{data['land_tsubo']:.2f}坪 × {man(data['land_unit'], 2)}/坪"
    draw_para(escape(formula), "right_value", rx, top - 8 * mm, rw)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.2)
    pdf.line(rx, top - 25 * mm, rx + rw, top - 25 * mm)
    pdf.setFont("HeiseiKakuGo-W5", 12)
    pdf.setFillColor(NAVY)
    pdf.drawRightString(rx + rw, top - 37 * mm, "土地評価額")
    draw_para(escape(yen(data["land_value"])), "right_value", rx, top - 42 * mm, rw)
    pill(rx + rw - 58 * mm, top - 70 * mm, 58 * mm, "土地評価額")
    pdf.setFont("HeiseiKakuGo-W5", 24)
    pdf.setFillColor(NAVY)
    pdf.drawRightString(rx + rw, top - 91 * mm, yen(data["land_value"]))
    pdf.showPage()

    # Page 3: building appraisal.
    frame(3, "Step 2　建物の評価額", "再調達価格に築年数に応じた残存率を乗じて算出")
    top = page_h - 54 * mm
    pdf.setFont("HeiseiKakuGo-W5", 12)
    pdf.setFillColor(NAVY)
    pdf.drawString(margin, top, "建物評価の考え方")
    explanation = ("再建築した場合の概算費用を再調達価格として設定し、建物の経過年数に応じた残存率を乗じて評価します。"
                   "木造住宅の簡易計算では、築25年で残存率10%となる設定です。")
    draw_para(escape(explanation), "body", margin, top - 8 * mm, 95 * mm)
    # Simple residual scale based on the current age.
    gx, gy, gw = margin, top - 57 * mm, 96 * mm
    pdf.setFillColor(colors.HexColor("#e5eaee"))
    pdf.roundRect(gx, gy, gw, 7 * mm, 3.5 * mm, fill=1, stroke=0)
    pdf.setFillColor(PINK)
    pdf.roundRect(gx, gy, gw * min(1, data["residual"]), 7 * mm, 3.5 * mm, fill=1, stroke=0)
    pdf.setFont("HeiseiKakuGo-W5", 9)
    pdf.setFillColor(MUTED)
    pdf.drawString(gx, gy - 7 * mm, f"築{data['age']:g}年")
    pdf.drawRightString(gx + gw, gy - 7 * mm, f"残存率 {data['residual'] * 100:.1f}%")

    rx, rw = 123 * mm, page_w - margin - 123 * mm
    pdf.setFont("HeiseiKakuGo-W5", 11)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(rx + rw, top, "建物面積 × 再調達価格 × 残存率")
    formula = f"{data['building_tsubo']:.2f}坪 × {data['replacement_unit']:g}万円 × {data['residual'] * 100:.1f}%"
    draw_para(escape(formula), "right_value", rx, top - 9 * mm, rw)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1)
    pdf.line(rx, top - 28 * mm, rx + rw, top - 28 * mm)
    pdf.setFont("HeiseiKakuGo-W5", 10)
    pdf.setFillColor(INK)
    pdf.drawString(rx, top - 38 * mm, f"建物価格：{yen(data['building_gross'])}")
    pdf.drawString(rx, top - 48 * mm, f"解体費控除：－{yen(data['demolition'] * 10000)}")
    pill(rx + rw - 58 * mm, top - 70 * mm, 58 * mm, "建物評価額")
    pdf.setFont("HeiseiKakuGo-W5", 24)
    pdf.setFillColor(NAVY)
    pdf.drawRightString(rx + rw, top - 91 * mm, yen(data["building_value"]))

    note_y = 36 * mm
    pdf.setFillColor(PALE_BLUE)
    pdf.roundRect(margin, note_y, content_w, 25 * mm, 2 * mm, fill=1, stroke=0)
    if data["age"] >= 40:
        age_note = "築40年以上のため、建物評価は0円として計算し、入力された解体費を差し引いています。"
    else:
        age_note = f"築{data['age']:g}年の残存率は{data['residual'] * 100:.1f}%として計算しています。"
    draw_para(escape(age_note), "body", margin + 6 * mm, note_y + 18 * mm, content_w - 12 * mm)
    pdf.showPage()

    # Page 4: market adjustment and final figures.
    frame(4, "最終的な査定額", "市場流動比を反映した合計評価")
    block_w = 55 * mm
    start_x = 27 * mm
    top_y = page_h - 78 * mm
    labels = [("土地評価額", yen(data["land_value"])), ("建物評価額", yen(data["building_value"])), ("市場流動比", f"× {data['liquidity']:.2f}")]
    colors_seq = [colors.HexColor("#c49a62"), NAVY, PINK]
    for i, (label, value) in enumerate(labels):
        x = start_x + i * (block_w + 28 * mm)
        pdf.setStrokeColor(colors_seq[i])
        pdf.setLineWidth(1.5)
        pdf.roundRect(x, top_y, block_w, 31 * mm, 2 * mm, fill=0, stroke=1)
        draw_para(escape(label), "center_label", x, top_y + 24 * mm, block_w)
        amount = f"{man(data['land_value'] / 10000, 0)}" if i == 0 else (f"{man(data['building_value'] / 10000, 0)}" if i == 1 else value)
        draw_para(escape(amount), "mini_value", x, top_y + 13 * mm, block_w)
        if i < 2:
            pdf.setFillColor(NAVY)
            pdf.setFont("HeiseiKakuGo-W5", 23)
            pdf.drawCentredString(x + block_w + 14 * mm, top_y + 10 * mm, "+" if i == 0 else "×")

    calc_y = top_y - 28 * mm
    formula = f"（{yen(data['land_value'])} ＋ {yen(data['building_value'])}） × {data['liquidity']:.2f}"
    draw_para(escape(formula), "center_label", margin, calc_y, content_w)
    result_y, result_h = calc_y - 48 * mm, 34 * mm
    pdf.setFillColor(NAVY)
    pdf.roundRect(margin + 15 * mm, result_y, content_w - 30 * mm, result_h, 2 * mm, fill=1, stroke=0)
    style_white = ParagraphStyle("report_white", parent=styles["center_value"], textColor=colors.white, fontSize=24, leading=30)
    result_para = Paragraph(f"合計評価額：{escape(yen(data['total']))}", style_white)
    _, ph = result_para.wrap(content_w - 40 * mm, result_h)
    result_para.drawOn(pdf, margin + 20 * mm, result_y + (result_h - ph) / 2)

    notice_y = 28 * mm
    pdf.setFillColor(PALE_BLUE)
    pdf.setStrokeColor(colors.HexColor("#d8e0e5"))
    pdf.roundRect(margin, notice_y, content_w, 27 * mm, 2 * mm, fill=1, stroke=1)
    notes = [
        "本報告書は入力情報に基づく机上査定であり、現地調査を伴う鑑定評価ではありません。",
        "現地状況、権利関係、接道、建物状態、成約事例等により、実際の売却価格は変動します。",
        "建物の状況によっては、解体費相当額を価格から減額する必要があります。",
    ]
    if data["route_multiplier"]:
        notes.append(f"土地単価は{data['route_type']}に{data['route_multiplier']:.1f}を乗じ、坪単価へ換算しています。")
    draw_para("<br/>".join("• " + escape(note) for note in notes), "small", margin + 5 * mm, notice_y + 22 * mm, content_w - 10 * mm)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


st.markdown("""
<style>
  .stApp { background: #fbfcfe; color: #17243a; }
  [data-testid="stHeader"] { background: transparent; }
  .hero-title { color:#b5103d; font-size:2rem; font-weight:750; margin-bottom:0; }
  .hero-sub { color:#63728a; margin-top:0.2rem; }
  .estimate-card { border:1px solid #f29aaa; background:#fff7f8; border-radius:14px; padding:1rem 1.2rem; }
  .estimate-card small { color:#b5103d; }
  .estimate-card strong { color:#b5103d; font-size:1.65rem; }
  div[data-testid="stMetric"] { background:#f3f7fb; border:1px solid #d8e0eb; padding:0.8rem; border-radius:10px; }
  @media print { [data-testid="stSidebar"], header, footer { display:none!important; } }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="hero-title">不動産簡易査定書</p><p class="hero-sub">物件情報を入力すると、査定額とPDFが自動で更新されます。</p>', unsafe_allow_html=True)
st.caption("入力内容は査定計算とPDF作成に使用し、アプリ内に保存する機能はありません。ホスティング環境で処理されます。")

with st.sidebar:
    st.subheader("査定書の表示情報")
    company = st.text_input("会社名", value="")
    agent = st.text_input("担当者", value="")
    report_date = st.date_input("発行日", value=date.today())
    st.divider()
    st.caption("路線価の補正：相続税路線価 × 1.2、固定資産税路線価 × 1.3。㎡単価を坪単価に換算します。")

left, right = st.columns([1.05, 0.95], gap="large")
with left:
    st.subheader("物件・ご依頼者")
    client = st.text_input("お名前", value="")
    property_type = st.selectbox("物件の種類", ["選択してください", "中古一戸建て", "新築一戸建て", "土地", "中古マンション"], index=0)
    address = st.text_input("売却物件住所", value="")
    a, b = st.columns(2)
    land_sqm = a.number_input("土地面積（㎡）", min_value=0.0, value=0.0, step=1.0)
    building_sqm = b.number_input("建物面積（㎡）", min_value=0.0, value=0.0, step=1.0)
    age = st.number_input("築後年数", min_value=0.0, max_value=150.0, value=0.0, step=1.0)
    structure = st.selectbox("建物構造", ["木造住宅", "軽量鉄骨造", "鉄骨造", "鉄筋コンクリート造"], index=0)

    st.subheader("土地の査定")
    route_type = st.selectbox("土地単価の根拠", ["路線価なし（単価を入力）", "相続税路線価", "固定資産税路線価"], index=0)
    route_value = st.number_input("路線価（円/㎡）", min_value=0.0, value=0.0, step=1000.0, help="路線価図などに記載された㎡あたりの価格を入力します。")
    direct_unit = st.number_input("査定単価（万円/坪）※路線価がない場合", min_value=0.0, value=0.0, step=0.5)
    c, d = st.columns(2)
    market_low = c.number_input("周辺相場 下限（万円/坪）", min_value=0.0, value=0.0, step=0.5)
    market_high = d.number_input("周辺相場 上限（万円/坪）", min_value=0.0, value=0.0, step=0.5)

with right:
    st.subheader("建物・市場条件")
    replacement_unit = st.number_input("建物再調達価格（万円/坪）", min_value=0.0, value=0.0, step=1.0, help="建物を再建築する場合の坪単価を入力してください。")
    demolition = st.number_input("解体費控除（万円）", min_value=0.0, value=0.0, step=5.0)
    st.caption("築40年以上は初期設定で建物評価を0円にします。解体費が見込まれる場合は入力してください。")
    if property_type.startswith("中古"):
        liquidity_default = 0.90
        liquidity_note = "中古物件の初期値：平均値0.90"
    else:
        liquidity_default = 1.00
        liquidity_note = "初期値：1.00"
    liquidity = st.number_input("市場流動比", min_value=0.0, max_value=2.0, value=liquidity_default, step=0.01, format="%.2f", help="中古物件は0.90を初期値としています。")
    st.caption(liquidity_note)
    e, f = st.columns(2)
    proposal_low_pct = e.number_input("提案価格 下限（査定額比 %）", min_value=0.0, max_value=200.0, value=95.0, step=1.0)
    proposal_high_pct = f.number_input("提案価格 上限（査定額比 %）", min_value=0.0, max_value=200.0, value=105.0, step=1.0)
    st.info("提案価格帯は査定評価額を基準に、初期設定では95～105%で表示します。必要に応じて変更できます。")

route_multiplier = ROUTE_MULTIPLIER.get(route_type, 0.0)
if route_multiplier and route_value > 0:
    land_unit_yen = route_value * route_multiplier * (1 / SQM_TO_TSUBO)
    land_unit = land_unit_yen / 10000
else:
    land_unit = direct_unit
land_tsubo = to_tsubo(land_sqm)
building_tsubo = to_tsubo(building_sqm)
residual = residual_rate(age)
land_value = land_tsubo * land_unit * 10000
building_gross = building_tsubo * replacement_unit * 10000 * residual
building_value = building_gross - demolition * 10000
pre_liquidity = max(0.0, land_value + building_value)
total = pre_liquidity * liquidity
proposal_low = total * proposal_low_pct / 100
proposal_high = total * proposal_high_pct / 100

validation_errors = []
if not client.strip():
    validation_errors.append("お名前を入力してください。")
if property_type == "選択してください":
    validation_errors.append("物件の種類を選択してください。")
if not address.strip():
    validation_errors.append("売却物件住所を入力してください。")
if land_sqm <= 0:
    validation_errors.append("土地面積を入力してください。")
if route_multiplier and route_value <= 0:
    validation_errors.append("選択した路線価の㎡単価を入力してください。")
if not route_multiplier and direct_unit <= 0:
    validation_errors.append("路線価を使わない場合は、査定単価を入力してください。")
if property_type not in ("選択してください", "土地") and building_sqm <= 0:
    validation_errors.append("建物面積を入力してください。")
if building_sqm > 0 and age < 40 and replacement_unit <= 0:
    validation_errors.append("建物再調達価格を入力してください。")
ready = not validation_errors

if route_multiplier and route_value > 0:
    st.success(f"路線価からの査定単価：{route_value:,.0f}円/㎡ × {route_multiplier:.1f} × {1 / SQM_TO_TSUBO:.4f} ＝ {land_unit:,.2f}万円/坪")
elif route_type != "路線価なし（単価を入力）" and route_value <= 0:
    st.warning("路線価を入力すると、指定倍率を掛けた土地単価を自動計算します。")
elif direct_unit <= 0:
    st.warning("路線価がない場合は、査定単価（万円/坪）を入力してください。")

st.divider()
if ready:
    st.subheader("査定結果プレビュー")
    st.markdown(f'<div class="estimate-card"><small>ご提案取引価格（売却目安）</small><br><strong>{man(proposal_low / 10000, 0)} ～ {man(proposal_high / 10000, 0)} 前後</strong></div>', unsafe_allow_html=True)
    st.write("")
    k1, k2, k3 = st.columns(3)
    k1.metric("土地評価", yen(land_value))
    k2.metric("建物評価", yen(building_value))
    k3.metric("合計評価", yen(total))
    q1, q2 = st.columns(2)
    q1.write(f"**土地**　{land_tsubo:.2f}坪 × {land_unit:,.2f}万円/坪")
    q2.write(f"**建物**　{building_tsubo:.2f}坪 × {replacement_unit:g}万円/坪 × {residual*100:.1f}% − {demolition:g}万円")
    st.caption(f"合計計算：({yen(land_value)} + {yen(building_value)}) × {liquidity:.2f} ＝ {yen(total)}")
    if age >= 40:
        st.warning("築40年以上のため、建物価格を0円として計算し、入力された解体費を控除します。")
else:
    st.info("必要項目を入力すると、査定結果とPDFを表示します。")
    for error in validation_errors:
        st.caption(f"・{error}")

data = {
    "client": client.strip(), "property_type": property_type, "address": address.strip(), "land_sqm": land_sqm,
    "building_sqm": building_sqm, "age": age, "structure": structure, "land_tsubo": land_tsubo,
    "building_tsubo": building_tsubo, "route_type": route_type, "route_value": route_value,
    "route_multiplier": route_multiplier, "land_unit": land_unit, "direct_unit": direct_unit,
    "market_low": market_low, "market_high": market_high, "replacement_unit": replacement_unit,
    "residual": residual, "demolition": demolition, "building_gross": building_gross, "land_value": land_value,
    "building_value": building_value, "pre_liquidity": pre_liquidity, "liquidity": liquidity,
    "total": total, "proposal_low": proposal_low, "proposal_high": proposal_high,
    "company": company, "agent": agent, "report_date": report_date.strftime("%Y年%m月%d日"),
}
if ready:
    pdf_bytes = make_pdf(data)
    st.download_button(
        "査定書PDFをダウンロード",
        data=pdf_bytes,
        file_name="不動産査定報告書.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=False,
    )

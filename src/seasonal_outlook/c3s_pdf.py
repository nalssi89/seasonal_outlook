from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from svglib.svglib import svg2rlg

from .pdf_publish import publish_pdf_copy


PAGE_WIDTH = 1366
PAGE_HEIGHT = 768
MARGIN_X = 36
MARGIN_Y = 26
CARD_GAP = 14
MONTHS = ("2026-05", "2026-06", "2026-07")
MONTH_LABELS = ("2026-05", "2026-06", "2026-07")
FOOTNOTE = (
    "자료 해석 주의: C3S multi-system tercile summary는 각 모델의 hindcast(1993-2016) 기후분포를 기준으로 "
    "상·하위 tercile 확률이 40%를 넘는 영역을 요약한 월평균 확률 지도이며, 유의성 검정은 적용되지 않습니다."
)
COVER_ACCENT = "#6f4a2e"


@dataclass(frozen=True)
class VariableSlide:
    slug: str
    title: str
    english_title: str
    accent: str
    subtitle: str
    month_notes: tuple[str, str, str]
    korea_note: str
    caution: str


def _slides() -> list[VariableSlide]:
    return [
        VariableSlide(
            slug="t2m",
            title="2 m 기온",
            english_title="Surface Temperature",
            accent="#9d3322",
            subtitle=(
                "동아시아에서 가장 일관된 양의 계절 신호입니다. 한반도는 3개월 내내 상위 tercile 고온역의 가장자리에서 "
                "벗어나지 않으며, 6~7월로 갈수록 warm signal의 공간 응집도가 더 높아집니다."
            ),
            month_notes=(
                "화북-한반도-일본으로 상위 tercile 띠가 이어집니다. 5월부터 이미 한반도는 평년보다 더운 쪽으로 기울어져 있고, "
                "봄철 잔류 한기보다 조기 고온 배경이 우세합니다.",
                "양의 고온역이 만주-화북에서 한반도와 일본까지 넓어집니다. 6월은 동아시아 여름철 진입 구간인데도 냉량한 완충영역이 약해, "
                "초여름부터 높은 기온 바탕장이 형성될 가능성이 큽니다.",
                "고온역이 동아시아 전반과 서북태평양 북서부에 남아 있습니다. 7월에도 한반도는 중립대보다 상위 범주에 더 가까워, "
                "폭염 발생 시 그 강도와 지속성이 커질 수 있는 구조입니다.",
            ),
            korea_note=(
                "한반도는 5월부터 7월까지 평년보다 높은 기온 확률이 일관되게 우세합니다. 단순한 일시 고온보다 "
                "여름철 평균 열배경 자체가 높아지는 쪽에 무게를 둘 수 있습니다."
            ),
            caution=(
                "기온은 이번 묶음에서 가장 신호가 강한 변수이지만, 일최고기온 극값과 폭염일수는 계절 평균장만으로 직접 환산할 수는 없습니다."
            ),
        ),
        VariableSlide(
            slug="rain",
            title="강수량",
            english_title="Precipitation",
            accent="#157a66",
            subtitle=(
                "강수는 다른 변수보다 훨씬 파편적이고 신호가 약합니다. 한반도 주변은 3개월 모두 뚜렷한 wet core에 놓이지 않아 "
                "계절총강수는 '평년 부근, 다만 약한 다우 가능성' 정도로 보수적으로 읽는 편이 합리적입니다."
            ),
            month_notes=(
                "습윤 신호의 중심은 서남아와 티베트 남쪽 사면에 놓이고, 한반도는 대부분 중립대에 머뭅니다. "
                "5월 강수는 동아시아 본류보다 남아시아 쪽 예측성이 상대적으로 더 큽니다.",
                "장마철 진입 구간인 6월에도 동아시아 강수 신호는 산개되어 있습니다. 일본과 서북태평양 쪽의 약한 상위 확률은 보이지만, "
                "한반도 자체를 덮는 지속적 습윤 중심은 분명하지 않습니다.",
                "7월에도 한반도는 강한 상위 tercile 핵과는 거리가 있습니다. 중국 내륙과 열대 서태평양 쪽의 대비가 더 크고, "
                "한반도 강수는 계절 평균보다 장마전선의 남북 진동과 개별 강수사건의 기여가 더 중요해 보입니다.",
            ),
            korea_note=(
                "한반도 계절 총강수는 3개월 모두 뚜렷한 우다우 또는 과소우 신호보다 중립에 가깝습니다. "
                "다만 주변 해역이 따뜻해 강수 효율은 높을 수 있으므로, 계절 총량보다 강수 집중도와 사건성에 더 주목해야 합니다."
            ),
            caution=(
                "강수 tercile 지도는 월평균 총량 범주만 보여줍니다. 장마 시작·종료 시기, 호우 빈도, 일강수 극값은 별도 단기·중기 진단이 필요합니다."
            ),
        ),
        VariableSlide(
            slug="mslp",
            title="해면기압",
            english_title="Mean Sea-Level Pressure",
            accent="#345c9c",
            subtitle=(
                "해면기압은 한반도 자체의 단일 고저압보다는 주변 육해 기압경도와 몬순형 배경장을 읽는 데 유용합니다. "
                "6~7월로 갈수록 대륙 내부와 서태평양 사이의 계절 평균 압력대비가 선명해집니다."
            ),
            month_notes=(
                "5월은 인도-인도차이나 쪽 양압 경향이 먼저 보이고, 한반도는 약한 양압대의 북동단 또는 중립대에 걸립니다. "
                "일본 동쪽 해상은 상대적으로 낮은 압력 범주가 나타나 해상 쪽 완충영역이 살아 있습니다.",
                "6월에는 대륙 내부의 중립~약한 양압과 일본 남동 해상의 저압 경향이 대비됩니다. "
                "한반도는 뚜렷한 고압 핵보다는 그 경계대에 놓여, 장마철 남북 압력구배가 형성되기 쉬운 배경입니다.",
                "7월은 서쪽 대륙의 양압과 서태평양 쪽 상대적 저압이 더 분명해집니다. "
                "이는 여름철 몬순형 압력배치의 계절 평균 구조가 강화된 것으로 읽을 수 있으며, 한반도는 그 북서측 경계에 위치합니다.",
            ),
            korea_note=(
                "한반도는 6~7월에 대륙 고압 중심보다 그 동남쪽 경계에 놓이는 모습입니다. "
                "따라서 건조한 대륙고기압 직접 지배보다, 남쪽 해상과 연결된 기압경도 속에서 단기 순환에 민감한 위치로 해석하는 편이 적절합니다."
            ),
            caution=(
                "MSLP는 계절 평균장이므로 전선 위치나 개별 저기압 통과를 직접 뜻하지 않습니다. 강수 해석은 Z500, SST, 풍속장과 결합해야 합니다."
            ),
        ),
        VariableSlide(
            slug="wspd",
            title="10 m 풍속",
            english_title="10 m Wind Speed",
            accent="#3d7b8d",
            subtitle=(
                "저층 풍속장은 몬순 유입의 강도 배경을 보완해 주지만, 방향 정보가 없기 때문에 단독 해석은 위험합니다. "
                "이번 묶음에서는 강풍 코어가 주로 남쪽 해역에 머물고 한반도는 주변부에 놓이는 구조가 우세합니다."
            ),
            month_notes=(
                "5월은 서남아와 내륙 아시아에서 풍속이 평년보다 약한 영역이 넓고, 동아시아 중위도는 대체로 중립입니다. "
                "한반도 주변은 강풍 핵이 아니라 약한 또는 보통 범주에 가까워 초기 수증기 수송 강화 신호는 제한적입니다.",
                "6월에는 벵골만-인도차이나-남중국해 방면으로 풍속이 강화되지만, 중국 북부와 한반도는 여전히 강한 양의 풍속역 중심이 아닙니다. "
                "즉, 몬순 저층 제트의 주축이 한반도 남쪽 해역에 더 가깝습니다.",
                "7월에도 강한 풍속 영역은 필리핀해와 남쪽 해역에 집중되고, 한반도는 대체로 중립 내지 약한 양의 경향입니다. "
                "결국 한반도 강수는 풍속 강도 자체보다 전선 위치와 단기 저기압성 요인의 영향을 더 크게 받을 가능성이 큽니다.",
            ),
            korea_note=(
                "한반도는 여름철 저층 풍속 강화의 직접 core보다 북쪽 가장자리에 놓일 가능성이 큽니다. "
                "따라서 수증기 공급은 가능하지만, 그 효율과 실제 강수 전환은 단기 순환 조건에 크게 좌우됩니다."
            ),
            caution=(
                "이 변수는 풍향이 아니라 풍속만 나타냅니다. 남서류 유입 여부 같은 방향 정보는 MSLP·Z500과 함께 종합적으로 해석해야 합니다."
            ),
        ),
        VariableSlide(
            slug="ssto",
            title="해수면온도",
            english_title="Sea-Surface Temperature",
            accent="#c36a1e",
            subtitle=(
                "주변 해역 SST는 이번 전망에서 가장 느리고 지속적인 양의 경계조건입니다. "
                "동중국해-일본 남쪽-쿠로시오 연장역의 warm ocean background가 3개월 내내 유지됩니다."
            ),
            month_notes=(
                "5월부터 동중국해와 일본 남쪽, 서북태평양 북서부에 양의 해수면온도 확률이 뚜렷합니다. "
                "한반도 주변 해역의 해양 경계조건이 이미 따뜻한 쪽으로 기울어 있습니다.",
                "6월에도 warm SST belt가 유지됩니다. 쿠로시오 및 그 연장역의 따뜻한 해역은 대기 하층의 수증기 함량과 해상 열공급을 높이는 배경으로 작용할 수 있습니다.",
                "7월에는 일본 동쪽과 서북태평양 북서부의 warm signal이 다시 강해집니다. "
                "한반도 인접 해역도 중립보다 따뜻한 해역에 더 가까워, 여름철 고온·고습 환경을 지속적으로 지지합니다.",
            ),
            korea_note=(
                "한반도 주변 바다가 평년보다 따뜻할 가능성이 높습니다. 이는 야간 기온 하강을 억제하고 체감더위를 키우며, "
                "강수 사건이 발생할 때는 수증기 공급과 강수 효율을 높이는 방향으로 작용할 수 있습니다."
            ),
            caution=(
                "SST는 느린 경계조건이어서 열배경 해석에는 강하지만, 계절 총강수량을 단독으로 결정하지는 않습니다. 순환장과 함께 읽어야 합니다."
            ),
        ),
        VariableSlide(
            slug="t850",
            title="850 hPa 기온",
            english_title="Lower-Tropospheric Temperature",
            accent="#994130",
            subtitle=(
                "850 hPa 온도는 표면 고온 신호가 경계층 국지효과에 그치지 않고 대기 하층 전체의 온난 질량장으로 확장된다는 점을 확인시켜 줍니다. "
                "동아시아 하층 온난 배경은 6~7월로 갈수록 더 뚜렷합니다."
            ),
            month_notes=(
                "5월은 중국 동부-황해-한반도-일본으로 따뜻한 하층 공기질량이 형성되는 초기 단계입니다. "
                "표면 고온이 단순 일사 효과만이 아니라 하층 온난 이류와 연결될 가능성을 보여줍니다.",
                "6월에는 화북-만주-한반도 부근 하층 warm core가 더 조직적으로 나타납니다. "
                "이는 초여름에 냉량한 하층 공기의 침투보다 온난한 두께장이 우세할 가능성이 크다는 뜻입니다.",
                "7월에도 하층 온난 질량장은 동아시아 전반에 남아 있습니다. "
                "따라서 한반도는 여름철 평균기온이 높아질 뿐 아니라, 더운 공기덩어리가 반복적으로 유입되기 쉬운 환경입니다.",
            ),
            korea_note=(
                "한반도는 850 hPa 차원에서도 일관된 온난 영역 안에 들어갑니다. "
                "표면 고온과 상층 ridge가 결합할 경우, 더위의 지속성과 열적 체감이 모두 강화될 가능성이 큽니다."
            ),
            caution=(
                "850 hPa 기온은 하층 열배경을 보여주지만, 실제 지상 체감은 운량·바람·습도에 따라 달라집니다. T2m, Z500과 결합해서 보는 것이 안전합니다."
            ),
        ),
        VariableSlide(
            slug="z500",
            title="500 hPa 지위고도",
            english_title="Mid-Tropospheric Height",
            accent="#8a4a1a",
            subtitle=(
                "이번 전망 묶음에서 가장 조직적인 대규모 순환 신호입니다. 동아시아 상공의 양의 지위고도 편차가 5월부터 형성되고 "
                "6~7월에 더 넓고 강한 ridge형 배경으로 확대됩니다."
            ),
            month_notes=(
                "5월은 중국 중동부-동중국해-일본 서쪽으로 양의 고도장이 자리합니다. "
                "한반도는 ridge의 동측 가장자리에 놓이지만 이미 상층 배경은 평년보다 높은 쪽입니다.",
                "6월에는 양의 고도장이 몽골-화북-한반도-일본까지 더 넓게 확장됩니다. "
                "이는 동아시아 상공의 파동가이드가 북쪽으로 들리고, 대기 column 전체가 따뜻해질 준비가 되어 있음을 뜻합니다.",
                "7월은 동아시아 대부분이 강한 양의 지위고도 범주에 들어갑니다. "
                "서태평양 아열대고기압의 계절 평균 북서 확장과 상층 ridge 강화 배경이 한층 분명해지는 모습입니다.",
            ),
            korea_note=(
                "한반도는 6~7월에 상층 ridge 영향권에 더 자주 들 가능성이 큽니다. "
                "따라서 비가 오지 않는 구간의 고온 정체, 일사 강화, 무더운 공기덩어리 체류 가능성을 높게 볼 수 있습니다."
            ),
            caution=(
                "Z500 양의 신호는 고온 배경에는 강한 근거가 되지만, 장마 강도나 호우 시점까지 직접 결정하지는 않습니다. 단기 파동과 제트 변동은 별도 진단이 필요합니다."
            ),
        ),
    ]


def _register_fonts() -> None:
    regular = r"C:\Windows\Fonts\malgun.ttf"
    bold = r"C:\Windows\Fonts\malgunbd.ttf"
    if "MalgunGothic" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MalgunGothic", regular))
    if "MalgunGothic-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MalgunGothic-Bold", bold))


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            parent=styles["BodyText"],
            fontName="MalgunGothic-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#5b666d"),
        ),
        "title": ParagraphStyle(
            "title",
            parent=styles["Heading1"],
            fontName="MalgunGothic-Bold",
            fontSize=26,
            leading=30,
            textColor=colors.HexColor("#172026"),
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=styles["BodyText"],
            fontName="MalgunGothic",
            fontSize=11.7,
            leading=16,
            textColor=colors.HexColor("#354149"),
        ),
        "panel_title": ParagraphStyle(
            "panel_title",
            parent=styles["Heading3"],
            fontName="MalgunGothic-Bold",
            fontSize=14.5,
            leading=17,
            textColor=colors.HexColor("#172026"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName="MalgunGothic",
            fontSize=10.8,
            leading=15,
            textColor=colors.HexColor("#354149"),
        ),
        "label": ParagraphStyle(
            "label",
            parent=styles["BodyText"],
            fontName="MalgunGothic-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#172026"),
        ),
        "badge": ParagraphStyle(
            "badge",
            parent=styles["BodyText"],
            fontName="MalgunGothic-Bold",
            fontSize=9.5,
            leading=11,
            alignment=1,
            textColor=colors.white,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=styles["BodyText"],
            fontName="MalgunGothic",
            fontSize=8.2,
            leading=10,
            textColor=colors.HexColor("#66747d"),
        ),
        "chip": ParagraphStyle(
            "chip",
            parent=styles["BodyText"],
            fontName="MalgunGothic-Bold",
            fontSize=9.5,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#172026"),
        ),
    }


def _fit_box(src_width: float, src_height: float, max_width: float, max_height: float) -> tuple[float, float]:
    scale = min(max_width / src_width, max_height / src_height)
    return src_width * scale, src_height * scale


def _draw_paragraph(c: canvas.Canvas, text: str, style: ParagraphStyle, x: float, y_top: float, width: float) -> float:
    para = Paragraph(text, style)
    _, height = para.wrap(width, PAGE_HEIGHT)
    para.drawOn(c, x, y_top - height)
    return y_top - height


def _draw_slide_shell(c: canvas.Canvas, accent: str, slide_no: str) -> None:
    c.setFillColor(colors.HexColor("#f3efe7"))
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    c.setFillColor(colors.Color(1, 0.985, 0.965, alpha=0.95))
    c.roundRect(14, 14, PAGE_WIDTH - 28, PAGE_HEIGHT - 28, 26, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(accent))
    c.rect(14, PAGE_HEIGHT - 20, PAGE_WIDTH - 28, 8, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#efe4d2"))
    c.roundRect(PAGE_WIDTH - 148, PAGE_HEIGHT - 62, 102, 28, 13, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#5b666d"))
    c.setFont("MalgunGothic", 11)
    c.drawCentredString(PAGE_WIDTH - 97, PAGE_HEIGHT - 51, slide_no)


def _draw_chip(
    c: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    styles: dict,
    fill: str,
    text_color: str = "#172026",
    stroke_color: str | None = None,
) -> None:
    c.setFillColor(colors.HexColor(fill))
    if stroke_color is not None:
        c.setStrokeColor(colors.HexColor(stroke_color))
        c.setLineWidth(1)
        c.roundRect(x, y, width, height, 11, fill=1, stroke=1)
    else:
        c.roundRect(x, y, width, height, 11, fill=1, stroke=0)
    chip_style = ParagraphStyle(
        "chip_inline",
        parent=styles["chip"],
        textColor=colors.HexColor(text_color),
    )
    _draw_paragraph(c, text, chip_style, x + 8, y + height - 7, width - 16)


def _draw_panel(
    c: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    body: str,
    styles: dict,
    accent: str,
) -> None:
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.85))
    c.setStrokeColor(colors.HexColor("#d8cfbf"))
    c.roundRect(x, y, width, height, 18, fill=1, stroke=1)
    c.setFillColor(colors.HexColor(accent))
    c.roundRect(x, y + height - 10, width, 10, 18, fill=1, stroke=0)
    top = y + height - 22
    top = _draw_paragraph(c, title, styles["panel_title"], x + 16, top, width - 32)
    _draw_paragraph(c, body, styles["body"], x + 16, top - 8, width - 32)


def _draw_image(c: canvas.Canvas, path: Path, x: float, y: float, width: float, height: float) -> None:
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#d8cfbf"))
    c.roundRect(x, y, width, height, 18, fill=1, stroke=1)
    inner_x = x + 10
    inner_y = y + 14
    inner_w = width - 20
    inner_h = height - 24
    if path.suffix.lower() == ".svg":
        drawing = svg2rlg(str(path))
        draw_w, draw_h = _fit_box(drawing.width, drawing.height, inner_w, inner_h)
        scale = draw_w / drawing.width
        c.saveState()
        c.translate(inner_x + (inner_w - draw_w) / 2, inner_y + (inner_h - draw_h) / 2)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0)
        c.restoreState()
        return
    image = ImageReader(str(path))
    src_w, src_h = image.getSize()
    draw_w, draw_h = _fit_box(src_w, src_h, inner_w, inner_h)
    c.drawImage(
        image,
        inner_x + (inner_w - draw_w) / 2,
        inner_y + (inner_h - draw_h) / 2,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )


def _resolve_asset(assets: Path, slug: str, month: str) -> Path:
    for ext in (".png", ".svg"):
        candidate = assets / f"{slug}_tsum_{month}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing C3S asset for {slug} {month}")


def _pick_output_path(issue_dir: Path) -> Path:
    preferred = issue_dir / "c3s_multisystem_variable_slides_ko.pdf"
    candidates = [preferred] + [
        issue_dir / f"c3s_multisystem_variable_slides_ko_v{index}.pdf" for index in range(2, 10)
    ]
    for candidate in candidates:
        if not candidate.exists():
            return candidate
        try:
            with candidate.open("ab"):
                pass
            return candidate
        except PermissionError:
            continue
    raise PermissionError("No writable output filename available for the C3S PDF deck.")


def _draw_map_card(
    c: canvas.Canvas,
    path: Path,
    label: str,
    x: float,
    y: float,
    width: float,
    height: float,
    styles: dict,
    accent: str,
) -> None:
    _draw_image(c, path, x, y, width, height)
    _draw_chip(
        c,
        x + (width - 110) / 2,
        y + height + 10,
        110,
        24,
        label,
        styles,
        "#fffaf2",
        text_color=accent,
        stroke_color=accent,
    )


def _draw_cover_slide(c: canvas.Canvas, issue_date: date, total_slides: int, styles: dict) -> None:
    _draw_slide_shell(c, COVER_ACCENT, f"01 / {total_slides:02d}")
    top = PAGE_HEIGHT - 68
    top = _draw_paragraph(c, "Copernicus C3S multi-system seasonal outlook", styles["eyebrow"], MARGIN_X, top, 520)
    top = _draw_paragraph(c, "동아시아-한반도 3개월 전망", styles["title"], MARGIN_X, top - 2, 700)
    _draw_paragraph(
        c,
        "2026년 4월 1일 초기장 기준으로 2026년 5월, 6월, 7월의 동아시아 계절 신호를 정리한 슬라이드입니다. "
        "C3S multi-system tercile summary를 중심으로 해석하고, 한반도 해석은 동아시아 대규모 순환 배경과 함께 읽도록 구성했습니다.",
        styles["subtitle"],
        MARGIN_X,
        top - 12,
        980,
    )
    _draw_chip(c, 1038, 666, 272, 28, f"Issue date | {issue_date.isoformat()}", styles, "#efe4d2")

    _draw_panel(
        c,
        MARGIN_X,
        360,
        612,
        214,
        "전망 범위",
        "<b>대상 기간</b><br/>2026-05, 2026-06, 2026-07<br/><br/>"
        "<b>공간 범위</b><br/>동아시아(area09) 및 한반도 해석<br/><br/>"
        "<b>자료 기준</b><br/>C3S multi-system monthly tercile summary | base time 2026-04-01",
        styles,
        COVER_ACCENT,
    )
    _draw_panel(
        c,
        686,
        360,
        644,
        214,
        "해석 원칙",
        "<b>1.</b> 각 변수는 한 페이지에 독립 배치하여 변수별 의미가 섞이지 않도록 구성했습니다.<br/><br/>"
        "<b>2.</b> 동아시아 분석은 월별 공간 신호의 연속성과 이동을 중심으로 서술했습니다.<br/><br/>"
        "<b>3.</b> 한반도 분석은 계절 평균장 해석에 한정하며, 극한 현상은 과대해석하지 않도록 경고를 함께 제시했습니다.",
        styles,
        COVER_ACCENT,
    )
    _draw_panel(
        c,
        MARGIN_X,
        140,
        1294,
        174,
        "포함 변수",
        "<b>2 m 기온</b>, <b>강수량</b>, <b>해면기압</b>, <b>10 m 풍속</b>, <b>해수면온도</b>, "
        "<b>850 hPa 기온</b>, <b>500 hPa 지위고도</b><br/><br/>"
        "기온 계열 변수는 열배경의 일관성을, SST는 느린 경계조건을, MSLP·풍속·500 hPa 지위고도는 "
        "여름철 대규모 순환 배경을 읽는 보조 진단 변수로 활용했습니다.",
        styles,
        COVER_ACCENT,
    )
    for idx, label in enumerate(MONTH_LABELS):
        _draw_chip(
            c,
            980 + idx * 102,
            618,
            92,
            24,
            label,
            styles,
            "#fffaf2",
            text_color=COVER_ACCENT,
            stroke_color=COVER_ACCENT,
        )
    _draw_paragraph(c, FOOTNOTE, styles["footer"], MARGIN_X, 48, PAGE_WIDTH - 2 * MARGIN_X)


def _draw_variable_slide(
    c: canvas.Canvas,
    assets: Path,
    slide: VariableSlide,
    slide_index: int,
    total_slides: int,
    styles: dict,
) -> None:
    _draw_slide_shell(c, slide.accent, f"{slide_index:02d} / {total_slides:02d}")
    top = PAGE_HEIGHT - 60
    top = _draw_paragraph(c, f"C3S multi-system | {slide.english_title}", styles["eyebrow"], MARGIN_X, top, 520)
    top = _draw_paragraph(c, slide.title, styles["title"], MARGIN_X, top - 4, 560)
    _draw_chip(c, 982, 672, 328, 26, "East Asia | base time 2026-04-01 | tercile summary", styles, "#efe4d2")
    _draw_paragraph(c, slide.subtitle, styles["subtitle"], MARGIN_X, top - 10, PAGE_WIDTH - 2 * MARGIN_X - 10)

    map_y = 332
    map_h = 250
    map_w = (PAGE_WIDTH - 2 * MARGIN_X - 2 * CARD_GAP) / 3
    for idx, month in enumerate(MONTHS):
        x = MARGIN_X + idx * (map_w + CARD_GAP)
        label = MONTH_LABELS[idx]
        _draw_map_card(c, _resolve_asset(assets, slide.slug, month), label, x, map_y, map_w, map_h, styles, slide.accent)

    month_body = (
        f"<b>2026-05.</b> {slide.month_notes[0]}<br/><br/>"
        f"<b>2026-06.</b> {slide.month_notes[1]}<br/><br/>"
        f"<b>2026-07.</b> {slide.month_notes[2]}"
    )
    _draw_panel(c, MARGIN_X, 78, 774, 214, "동아시아 분석", month_body, styles, slide.accent)
    right_body = (
        f"<b>핵심 해석</b><br/>{slide.korea_note}<br/><br/>"
        f"<b>해석 유의</b><br/>{slide.caution}"
    )
    _draw_panel(c, 824, 78, 506, 214, "한반도 분석", right_body, styles, slide.accent)
    _draw_paragraph(c, FOOTNOTE, styles["footer"], MARGIN_X, 46, PAGE_WIDTH - 2 * MARGIN_X)


def build_c3s_pdf(issue_dir: Path) -> Path:
    _register_fonts()
    styles = _styles()
    assets = issue_dir / "c3s_assets"
    output = _pick_output_path(issue_dir)
    issue_date = date.fromisoformat(issue_dir.name)
    c = canvas.Canvas(str(output), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    c.setTitle("C3S Multi-system Variable Slides")
    slides = _slides()
    total_slides = len(slides) + 1
    _draw_cover_slide(c, issue_date, total_slides, styles)
    c.showPage()
    for index, slide in enumerate(slides, start=2):
        _draw_variable_slide(c, assets, slide, index, total_slides, styles)
        c.showPage()
    c.save()
    root_dir = issue_dir.parent.parent
    return publish_pdf_copy(output, issue_date, root_dir)


def main() -> int:
    issue_dir = Path.cwd() / "reports" / "2026-04-15"
    output = build_c3s_pdf(issue_dir)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

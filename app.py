import json
import os
from datetime import datetime
from pathlib import Path
from urllib import request as urlrequest

from flask import Flask, redirect, render_template, request, send_file, send_from_directory, url_for
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.utils import secure_filename

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover
    arabic_reshaper = None
    get_display = None


BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / "backup"
IMAGES_DIR = BASE_DIR / "images"
DATA_FILE = BACKUP_DIR / "data.json"
FONTS_DIR = BASE_DIR / "fonts"

COMPANY_INFO = {
    "name": "یکتا پخش",
    "phone_1": "02191303284",
    "phone_2": "09134148952",
    "order_channels": "ثبت سفارش در ایتا| واتساپ",
    "order_phone": "شماره ثبت سفارش 09134148952",
}

THEME = {
    "black": colors.HexColor("#0b0b0b"),
    "gold": colors.HexColor("#d4af37"),
    "gold_light": colors.HexColor("#f3d47a"),
    "white": colors.HexColor("#ffffff"),
}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(IMAGES_DIR)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


FONT_CANDIDATES = [
    str(FONTS_DIR / "Vazirmatn-Regular.ttf"),
    str(FONTS_DIR / "Vazirmatn-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_DOWNLOADS = {
    "Vazirmatn-Regular.ttf": "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf",
    "Vazirmatn-Bold.ttf": "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf",
}


def ensure_directories() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        save_data({"categories": [], "products": [], "next_category_id": 1, "next_product_id": 1})


def load_data() -> dict:
    ensure_directories()
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_data(data: dict) -> None:
    ensure_directories()
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def reshape_text(text: str) -> str:
    if not text:
        return ""
    if arabic_reshaper is None or get_display is None:
        return "".join(reversed(text))
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def ensure_fonts() -> None:
    for font_name, url in FONT_DOWNLOADS.items():
        font_path = FONTS_DIR / font_name
        if not font_path.exists():
            try:
                urlrequest.urlretrieve(url, font_path)
            except OSError:
                continue


def register_font() -> tuple[str, str]:
    ensure_fonts()
    regular = None
    bold = None
    for candidate in FONT_CANDIDATES:
        if os.path.exists(candidate):
            if "Bold" in candidate and bold is None:
                bold = candidate
            elif regular is None:
                regular = candidate
    if regular:
        pdfmetrics.registerFont(TTFont("Persian", regular))
    if bold:
        pdfmetrics.registerFont(TTFont("PersianBold", bold))
    if regular and bold:
        return "Persian", "PersianBold"
    if regular:
        return "Persian", "Persian"
    return "Helvetica", "Helvetica-Bold"


@app.route("/")
def index():
    data = load_data()
    categories = data["categories"]
    products = data["products"]
    products_by_category = {}
    for product in products:
        products_by_category.setdefault(product["category_id"], []).append(product)
    return render_template(
        "index.html",
        categories=categories,
        products_by_category=products_by_category,
        company_info=COMPANY_INFO,
    )


@app.route("/categories", methods=["POST"])
def add_category():
    name = request.form.get("name", "").strip()
    if not name:
        return redirect(url_for("index"))
    data = load_data()
    data["categories"].append({"id": data["next_category_id"], "name": name})
    data["next_category_id"] += 1
    save_data(data)
    return redirect(url_for("index"))


@app.route("/products", methods=["POST"])
def add_product():
    data = load_data()
    name = request.form.get("name", "").strip()
    category_id = int(request.form.get("category_id", 0))
    if not name or not category_id:
        return redirect(url_for("index"))

    image_file = request.files.get("image")
    filename = ""
    if image_file and image_file.filename:
        safe_name = secure_filename(image_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{safe_name}"
        image_path = IMAGES_DIR / filename
        image_file.save(image_path)

    product = {
        "id": data["next_product_id"],
        "category_id": category_id,
        "name": name,
        "description": request.form.get("description", "").strip(),
        "price_partner": request.form.get("price_partner", "").strip(),
        "price_retail": request.form.get("price_retail", "").strip(),
        "carton_count": request.form.get("carton_count", "").strip(),
        "image": filename,
        "active": True,
    }
    data["next_product_id"] += 1
    data["products"].append(product)
    save_data(data)
    return redirect(url_for("index"))


@app.route("/products/<int:product_id>/toggle", methods=["POST"])
def toggle_product(product_id: int):
    data = load_data()
    for product in data["products"]:
        if product["id"] == product_id:
            product["active"] = not product.get("active", True)
            break
    save_data(data)
    return redirect(url_for("index"))


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id: int):
    data = load_data()
    data["categories"] = [category for category in data["categories"] if category["id"] != category_id]
    remaining_products = []
    for product in data["products"]:
        if product["category_id"] != category_id:
            remaining_products.append(product)
            continue
        if product.get("image"):
            image_path = IMAGES_DIR / product["image"]
            if image_path.exists():
                image_path.unlink()
    data["products"] = remaining_products
    save_data(data)
    return redirect(url_for("index"))


def build_pdf(filepath: Path) -> None:
    data = load_data()
    categories = data["categories"]
    products = [item for item in data["products"] if item.get("active", True)]
    products_by_category = {}
    for product in products:
        products_by_category.setdefault(product["category_id"], []).append(product)

    font_body, font_heading = register_font()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="PersianHeading",
            parent=styles["Heading1"],
            alignment=TA_RIGHT,
            fontName=font_heading,
            fontSize=18,
            textColor=THEME["gold"],
            spaceAfter=6,
            wordWrap="RTL",
        )
    )
    styles.add(
        ParagraphStyle(
            name="PersianBody",
            parent=styles["BodyText"],
            alignment=TA_RIGHT,
            fontName=font_body,
            fontSize=10.5,
            leading=15,
            textColor=THEME["white"],
            wordWrap="RTL",
        )
    )
    styles.add(
        ParagraphStyle(
            name="PersianSmall",
            parent=styles["BodyText"],
            alignment=TA_RIGHT,
            fontName=font_body,
            fontSize=9.5,
            leading=13,
            textColor=THEME["gold_light"],
            wordWrap="RTL",
        )
    )
    styles.add(
        ParagraphStyle(
            name="PersianSection",
            parent=styles["Heading2"],
            alignment=TA_RIGHT,
            fontName=font_heading,
            fontSize=13,
            textColor=THEME["gold_light"],
            spaceBefore=6,
            spaceAfter=4,
            wordWrap="RTL",
        )
    )

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    def draw_background(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(THEME["black"])
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(THEME["gold_light"])
        canvas.setFont(font_body, 8)
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M")
        footer_text = reshape_text(f"صفحه {_doc.page} | به‌روزرسانی: {timestamp}")
        canvas.drawRightString(A4[0] - 1.5 * cm, 1.1 * cm, footer_text)
        canvas.restoreState()

    story = []
    title = reshape_text("فهرست موجودی یکتا پخش")
    story.append(Paragraph(title, styles["PersianHeading"]))
    info_lines = [
        COMPANY_INFO["name"],
        COMPANY_INFO["phone_1"],
        COMPANY_INFO["phone_2"],
        COMPANY_INFO["order_channels"],
        COMPANY_INFO["order_phone"],
    ]
    info_text = "<br/>".join(reshape_text(line) for line in info_lines)
    story.append(Paragraph(info_text, styles["PersianSmall"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(reshape_text("به‌روزرسانی موجودی بر اساس آخرین ثبت سیستم"), styles["PersianSmall"]))
    story.append(Spacer(1, 14))

    def build_image_flowable(image_path: Path) -> Image | Paragraph:
        if not image_path.exists():
            return Paragraph(reshape_text("تصویر نامعتبر"), styles["PersianSmall"])
        try:
            image_reader = ImageReader(str(image_path))
            image_reader.getSize()
            return Image(str(image_path), width=2.8 * cm, height=2.8 * cm)
        except OSError:
            return Paragraph(reshape_text("تصویر نامعتبر"), styles["PersianSmall"])

    for category in categories:
        category_name = reshape_text(category["name"])
        story.append(Paragraph(category_name, styles["PersianSection"]))
        products = products_by_category.get(category["id"], [])
        if not products:
            story.append(Paragraph(reshape_text("محصولی ثبت نشده است."), styles["PersianSmall"]))
            story.append(Spacer(1, 8))
            continue

        for product in products:
            image_path = IMAGES_DIR / product["image"] if product.get("image") else None
            image_flowable = ""
            if image_path:
                image_flowable = build_image_flowable(image_path)
            name = reshape_text(product["name"])
            description = reshape_text(product.get("description", ""))
            description_line = f"<br/>{description}" if description else ""
            name_paragraph = Paragraph(f"{name}{description_line}", styles["PersianBody"])

            price_partner = reshape_text(f"قیمت همکار: {product.get('price_partner', '-')}")
            price_retail = reshape_text(f"قیمت مصرف کننده: {product.get('price_retail', '-')}")
            price_paragraph = Paragraph(f"{price_partner}<br/>{price_retail}", styles["PersianSmall"])

            carton_count = reshape_text(f"تعداد در کارتن: {product.get('carton_count', '-')}")
            carton_paragraph = Paragraph(carton_count, styles["PersianSmall"])

            header_row = [
                Paragraph(reshape_text("تصویر"), styles["PersianSmall"]),
                Paragraph(reshape_text("شرح محصول"), styles["PersianSmall"]),
                Paragraph(reshape_text("قیمت‌ها"), styles["PersianSmall"]),
                Paragraph(reshape_text("کارتن"), styles["PersianSmall"]),
            ]
            row = [[image_flowable, name_paragraph, price_paragraph, carton_paragraph]]
            table = Table(
                [header_row] + row,
                colWidths=[3 * cm, 7.5 * cm, 4 * cm, 3 * cm],
                hAlign="RIGHT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TEXTCOLOR", (0, 0), (-1, -1), THEME["white"]),
                        ("GRID", (0, 0), (-1, -1), 0.3, THEME["gold"]),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111111")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b1b1b")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), THEME["gold_light"]),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.5, THEME["gold_light"]),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 10))
        story.append(Spacer(1, 12))

    doc.build(story, onFirstPage=draw_background, onLaterPages=draw_background)


@app.route("/pdf")
def generate_pdf():
    filename = f"yekta_pakhsh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = BACKUP_DIR / filename
    build_pdf(output_path)
    return send_file(output_path, as_attachment=True)


@app.route("/images/<path:filename>")
def serve_image(filename: str):
    return send_from_directory(IMAGES_DIR, filename)


if __name__ == "__main__":
    ensure_directories()
    app.run(host="0.0.0.0", port=5000, debug=True)

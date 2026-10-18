from io import BytesIO
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import ContentStream
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "pdf"

FILES = [
    (
        Path(
            "/Users/shounpalarpwar/Library/Containers/net.whatsapp.WhatsApp/"
            "Data/tmp/documents/9F0235FA-B109-4D60-B893-03BDC90A723F/"
            "Exploratory Data Analysis Submission 4.pdf"
        ),
        OUTPUT_DIR / "Exploratory Data Analysis Submission 4 - Shoun Palarpwar.pdf",
    ),
    (
        Path(
            "/Users/shounpalarpwar/Library/Containers/net.whatsapp.WhatsApp/"
            "Data/tmp/documents/B3FB3501-1FC7-4D7B-8157-DA110F922B1F/"
            "Exploratory Data Analysis Submission 5.pdf"
        ),
        OUTPUT_DIR / "Exploratory Data Analysis Submission 5 - Shoun Palarpwar.pdf",
    ),
]


def register_font() -> str:
    candidates = [
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("Arial-Bold-Local", str(path)))
            return "Arial-Bold-Local"
    return "Helvetica-Bold"


def make_overlay(width: float, height: float, font_name: str):
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(width, height))

    # Cover only the two original student-detail lines.
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(1, 1, 1)
    c.rect(185, 655, 242, 44, fill=1, stroke=0)

    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFont(font_name, 16)

    lines = [
        ("NAME: SHOUN PALARPWAR", 680.45),
        ("REG. NO. : 25BDS0031", 659.29),
    ]
    for text, baseline in lines:
        text_width = pdfmetrics.stringWidth(text, font_name, 16)
        x = (width - text_width) / 2
        c.drawString(x, baseline, text)
        c.setLineWidth(0.75)
        c.line(x, baseline - 1.6, x + text_width, baseline - 1.6)

    c.save()
    stream.seek(0)
    return PdfReader(stream).pages[0]


def remove_original_detail_groups(page, reader: PdfReader) -> None:
    content = ContentStream(page.get_contents(), reader)
    operations = content.operations
    keep = [True] * len(operations)
    i = 0
    removed = 0
    while i < len(operations):
        if operations[i][1] != b"q":
            i += 1
            continue

        depth = 1
        end = i + 1
        while end < len(operations) and depth:
            operator = operations[end][1]
            if operator == b"q":
                depth += 1
            elif operator == b"Q":
                depth -= 1
            end += 1

        group = operations[i:end]
        removes_detail = False
        for operands, operator in group[:5]:
            if operator != b"cm" or len(operands) != 6:
                continue
            a, b, c, d, x, y = (float(value) for value in operands)
            if (
                abs(a - 0.75) < 0.001
                and abs(d - 0.75) < 0.001
                and abs(b) < 0.001
                and abs(c) < 0.001
                and abs(x - 72) < 0.01
                and 90 < y < 130
            ):
                removes_detail = True
                break
        if removes_detail:
            for index in range(i, end):
                keep[index] = False
            removed += 1
        i = end

    if removed != 4:
        raise RuntimeError(f"Expected to remove 4 student-detail groups, removed {removed}")
    content.operations = [op for index, op in enumerate(operations) if keep[index]]
    page.replace_contents(content)


def update_pdf(source: Path, destination: Path, font_name: str) -> None:
    reader = PdfReader(source)
    first = reader.pages[0]
    remove_original_detail_groups(first, reader)
    width = float(first.mediabox.width)
    height = float(first.mediabox.height)
    rebuilt_first = PageObject.create_blank_page(width=width, height=height)
    rebuilt_first.merge_page(first, over=True)
    rebuilt_first.merge_page(make_overlay(width, height, font_name), over=True)

    writer = PdfWriter()
    writer.add_page(rebuilt_first)
    for page in reader.pages[1:]:
        writer.add_page(page)
    if reader.metadata:
        writer.add_metadata(
            {key: str(value) for key, value in reader.metadata.items() if value is not None}
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        writer.write(output)


def main() -> None:
    font_name = register_font()
    for source, destination in FILES:
        update_pdf(source, destination, font_name)
        print(destination)


if __name__ == "__main__":
    main()

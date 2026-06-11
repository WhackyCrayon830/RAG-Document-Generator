"""PDF export module using ReportLab."""

from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def compile_pdf(
    title: str,
    sections: list[dict],
    output_path: Path,
    template_path: Path | None = None,
    page_size: str = "letter",
) -> Path:
    """
    Compile sections into a PDF document.

    Args:
        title: Document title
        sections: List of dicts with 'title' and 'content' keys
        output_path: Path to save PDF
        template_path: Optional path to a template PDF (for overlaying)
        page_size: "letter" or "a4"

    Returns:
        Path to the generated PDF
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Select page size
    pagesize = A4 if page_size.lower() == "a4" else letter

    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=pagesize,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1 * inch,
        bottomMargin=0.75 * inch,
        title=title,
    )

    # Get default styles
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=28,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=30,
        alignment=1,  # Center
    )

    section_style = ParagraphStyle(
        "CustomSection",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#333333"),
        spaceAfter=12,
        spaceBefore=12,
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=1,
        borderPadding=6,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=11,
        alignment=4,  # Justify
        spaceAfter=12,
        leading=14,
    )

    # Build content
    content = []

    # Add title
    content.append(Paragraph(title, title_style))
    content.append(Spacer(1, 0.3 * inch))

    # Add sections
    for section in sections:
        content.append(Paragraph(section.get("title", "Untitled"), section_style))

        # Process content paragraphs
        text = section.get("content", "")
        for paragraph in text.split("\n\n"):
            text_stripped = paragraph.strip()
            if text_stripped:
                content.append(Paragraph(text_stripped, body_style))

        content.append(Spacer(1, 0.2 * inch))

    # Build PDF
    doc.build(content)
    return output_path

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime


def categories_to_pdf(filename, categories, title=None, generated_at=None):
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    # ---------- CUSTOM STYLES ----------

    category_title_style = ParagraphStyle(
        "CategoryTitle",
        parent=styles["Heading1"],
        fontSize=20,
        alignment=1,  # centered
        spaceAfter=14,
        spaceBefore=0,
    )

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        leading=18,
    )

    date_style = ParagraphStyle(
        "DateStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#374151"),
        wordWrap="CJK",
    )

    url_style = ParagraphStyle(
        "URLStyle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        wordWrap="CJK",
    )

    ics_style = ParagraphStyle(
        "ICSStyle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#059669"),
        wordWrap="CJK",
    )

    story = []

    # ---------- TITLE BLOCK ----------

    if title:
        story.append(Paragraph(f"<b>{title}</b>", category_title_style))
        story.append(Spacer(1, 0.2 * inch))

    ts = generated_at or datetime.now()
    story.append(Paragraph(f"Generated at: {ts.strftime('%Y-%m-%d %H:%M')}", normal))
    story.append(Spacer(1, 0.3 * inch))

    # ---------- CATEGORY SECTIONS ----------

    for category, items in categories.items():

        story.append(Paragraph(category, heading_style))
        story.append(Spacer(1, 0.1 * inch))

        if not items:
            story.append(Paragraph("No items in this category.", normal))
            story.append(Spacer(1, 0.3 * inch))
            continue

        # Table header row
        table_data = [
            [
                Paragraph("<b>Date</b>", url_style),
                Paragraph("<b>Title</b>", url_style)
            ]
        ]

        # ---------- BUILD ROWS ----------
        for item in items:

            title_text = item.get("title") or item.get("heading") or "Untitled"
            date = item.get("starts_at_dt") or item.get("date") or ""
            url = item.get("original_link") or item.get("url") or ""
            sublinks = item.get("sublinks") or []

            # Escape & to &amp; to avoid parser errors
            def safe(s):
                return str(s).replace("&", "&amp;") if s else ""

            safe_url = safe(url)

            # ---------- BUILD TITLE CELL SAFELY ----------
            title_lines = []

            # Main title
            title_lines.append(f"<b>{safe(title_text)}</b>")

            # URL
            if safe_url:
                title_lines.append(
                    f"<font size=9 color='#6b7280'>{safe_url}</font>"
                )

            # ICS
            ics_url = safe(
                item.get("ics_url")
                or item.get("ics")
                or item.get("ics_download")
                or ""
            )
            if ics_url:
                title_lines.append(
                    f"<font size=9 color='#059669'>ICS: {ics_url}</font>"
                )

            # Sublinks
            for sl in sublinks:
                heading = safe(sl.get("heading", ""))
                sl_url = safe(sl.get("url", ""))
                title_lines.append(
                    f"<font size=9><b>{heading}:</b> {sl_url}</font>"
                )

            # Join with simple <br/> (safe for ReportLab)
            title_html = "<br/>".join(title_lines)

            # Add row to table
            table_data.append([
                Paragraph(safe(date), date_style),
                Paragraph(title_html, normal),
            ])

        # ---------- CREATE TABLE ----------

        table = Table(
          table_data,
          colWidths=[1.7 * inch, 5.45 * inch],   # FIXED
          hAlign="LEFT",
      )

        table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6b7280")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),

            # Body background
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f9fafb")),

            # Borders
            ("BOX", (0, 1), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("INNERGRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),

            ("VALIGN", (0, 1), (-1, -1), "TOP"),

            # Padding
            ("LEFTPADDING", (0, 1), (-1, -1), 8),
            ("RIGHTPADDING", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3 * inch))

    # ---------- BUILD PDF ----------
    doc = SimpleDocTemplate(filename, pagesize=letter)
    doc.build(story)

    return filename

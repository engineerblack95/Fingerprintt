"""CSV and PDF exports for the entry-log activity report."""

import csv
import io
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Keep a single PDF bounded so a huge history cannot exhaust worker memory.
# CSV is streamed row-by-row and has no such limit.
MAX_PDF_ROWS = 3000

ROLE_LABELS = {"MEMBER": "Member", "VISITOR": "Visitor"}


def _person_name(log) -> str:
    if log.member_id and log.member:
        return log.member.full_name
    if log.member_name:
        return log.member_name
    return "Unknown person" if log.status == "UNKNOWN" else "—"


def _person_username(log) -> str:
    if log.member_id and log.member:
        return log.member.username
    return log.member_username or ""


def _person_role(log) -> str:
    if log.member_id and log.member:
        return log.member.get_role_display()
    return ROLE_LABELS.get(log.member_role, log.member_role or "—")


def _timestamp(log) -> str:
    return timezone.localtime(log.timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _source(log) -> str:
    return "Buffered sync" if log.synced_from_device else "Live report"


def _filename(extension: str) -> str:
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    return f"activity-report-{stamp}.{extension}"


def build_csv_response(logs) -> HttpResponse:
    """Stream a UTF-8 (BOM) CSV that opens cleanly in Excel."""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Timestamp",
            "Status",
            "Person",
            "Username",
            "Role",
            "Device",
            "Device ID",
            "Source",
            "Hardware slot",
        ]
    )
    for log in logs.iterator():
        writer.writerow(
            [
                _timestamp(log),
                log.get_status_display(),
                _person_name(log),
                _person_username(log),
                _person_role(log),
                log.device.location_name,
                log.device.device_id,
                _source(log),
                log.hardware_slot if log.hardware_slot is not None else "",
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename("csv")}"'
    return response


def build_pdf_response(logs) -> HttpResponse:
    """Render a landscape PDF table of the matching activity."""
    rows = list(logs[: MAX_PDF_ROWS + 1])
    truncated = len(rows) > MAX_PDF_ROWS
    rows = rows[:MAX_PDF_ROWS]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Activity Report",
        author="Fingerprint Access Control",
    )
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"].clone("ReportCell")
    cell_style.fontSize = 7.5
    cell_style.leading = 9

    generated = timezone.localtime().strftime("%A, %d %B %Y at %H:%M %Z")
    story = [
        Paragraph("Activity Report", styles["Title"]),
        Paragraph(
            f"Fingerprint Access Control · generated {escape(generated)}",
            styles["Normal"],
        ),
        Paragraph(f"{len(rows)} event(s) included", styles["Normal"]),
        Spacer(1, 6),
    ]

    if truncated:
        story.append(
            Paragraph(
                f"Showing the first {MAX_PDF_ROWS} events. "
                "Use the CSV export for the complete history.",
                styles["Italic"],
            )
        )
        story.append(Spacer(1, 6))

    data = [["Timestamp", "Status", "Person", "Role", "Device", "Source", "Slot"]]
    for log in rows:
        data.append(
            [
                Paragraph(escape(_timestamp(log)), cell_style),
                Paragraph(escape(log.get_status_display()), cell_style),
                Paragraph(escape(_person_name(log)), cell_style),
                Paragraph(escape(_person_role(log)), cell_style),
                Paragraph(
                    escape(f"{log.device.location_name} ({log.device.device_id})"),
                    cell_style,
                ),
                Paragraph(escape(_source(log)), cell_style),
                Paragraph(
                    escape(
                        str(log.hardware_slot)
                        if log.hardware_slot is not None
                        else "—"
                    ),
                    cell_style,
                ),
            ]
        )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[36 * mm, 24 * mm, 58 * mm, 22 * mm, 62 * mm, 28 * mm, 14 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    document.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename("pdf")}"'
    return response

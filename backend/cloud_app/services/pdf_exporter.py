"""
Exportación PDF sobre hoja membretada Albatros Corp.

Área útil respetando logo (superior) y franja azul (pie).
El Total solo se imprime en la última página.
Numeración: Pág. actual/total (ej. 1/5).

Asistencia: sombreado suave
  - rojo claro → llegada después de 09:00 (tarde)
  - amarillo claro → sin marca de salida
  - naranja → tarde + sin marca
"""

from __future__ import annotations

from datetime import date, time
from io import BytesIO
from pathlib import Path
from typing import TypeVar

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

from shared.models.reports import AttendanceReport, AttendanceRow, CafeteriaReport
from shared.services.name_format import format_employee_name

# Márgenes del área útil (letter = 612 x 792 pt)
_TOP_MARGIN = 2.95 * inch
_BOTTOM_SAFE = 1.15 * inch
_META_Y = 1.22 * inch

_LEFT = 0.7 * inch
_RIGHT_EDGE = letter[0] - 0.7 * inch
_ROW_ATT = 11.0
_ROW_CAFE = 11.2

_ARRIVAL_CUTOFF = time(9, 0, 0)

# Tonos marca de agua (impresos sobre fondo blanco del membrete)
_TONE_LATE = colors.Color(0.96, 0.88, 0.89)  # rojo suave
_TONE_MISSING = colors.Color(0.98, 0.95, 0.82)  # amarillo suave
_TONE_BOTH = colors.Color(0.98, 0.90, 0.82)  # naranja suave
_ACCENT_LATE = colors.Color(0.82, 0.42, 0.45)
_ACCENT_MISSING = colors.Color(0.85, 0.70, 0.12)
_ACCENT_BOTH = colors.Color(0.90, 0.52, 0.22)

T = TypeVar("T")


def _format_date_dmy(value) -> str:
    return value.strftime("%d/%m/%Y")


def _format_delay(minutes: int | None) -> str:
    if minutes is None or minutes <= 0:
        return "—"
    if minutes < 60:
        return f"{minutes} min"
    hours, rem = divmod(minutes, 60)
    return f"{hours} h {rem} min" if rem else f"{hours} h"


def _attendance_flags(row: AttendanceRow, *, today: date | None = None) -> tuple[bool, int | None, bool, bool]:
    """Retorna (is_late, delay_minutes, missing_exit, day_in_progress)."""
    if row.first_seen_at is None:
        is_today = today is not None and row.date == today
        return False, None, not is_today, is_today

    arrival = row.first_seen_at.time()
    is_late = arrival > _ARRIVAL_CUTOFF
    delay: int | None = None
    if is_late:
        arrival_secs = arrival.hour * 3600 + arrival.minute * 60 + arrival.second
        cutoff_secs = (
            _ARRIVAL_CUTOFF.hour * 3600
            + _ARRIVAL_CUTOFF.minute * 60
            + _ARRIVAL_CUTOFF.second
        )
        delay = (arrival_secs - cutoff_secs) // 60

    no_exit = row.last_seen_at is None
    is_today = today is not None and row.date == today
    day_in_progress = no_exit and is_today
    missing_exit = no_exit and not is_today
    return is_late, delay, missing_exit, day_in_progress


def _overlay_canvas() -> tuple[canvas.Canvas, BytesIO]:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    return c, buffer


def _merge_with_letterhead(overlay_bytes: bytes, letterhead_path: Path) -> bytes:
    if not letterhead_path.exists():
        return overlay_bytes

    letterhead = PdfReader(str(letterhead_path))
    overlay = PdfReader(BytesIO(overlay_bytes))
    writer = PdfWriter()

    template = letterhead.pages[0]
    for overlay_page in overlay.pages:
        page = writer.add_blank_page(
            width=template.mediabox.width,
            height=template.mediabox.height,
        )
        page.merge_page(template)
        page.merge_page(overlay_page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _y_after_title_and_header(*, has_subtitle: bool = True) -> float:
    """Misma geometría que al dibujar título + encabezado de tabla."""
    y = letter[1] - _TOP_MARGIN
    if has_subtitle:
        y -= 13  # título → subtítulo
        y -= 6  # subtítulo → línea
    else:
        y -= 8  # título → línea
    y -= 12  # línea → headers
    y -= 4  # headers → regla
    y -= 9  # regla → primera fila
    return y


def _paginate(
    items: list[T],
    row_height: float,
    *,
    has_subtitle: bool = True,
) -> list[list[T]]:
    if not items:
        return [[]]

    pages: list[list[T]] = []
    current: list[T] = []
    y = _y_after_title_and_header(has_subtitle=has_subtitle)

    for item in items:
        if current and y < _BOTTOM_SAFE + row_height:
            pages.append(current)
            current = []
            y = _y_after_title_and_header(has_subtitle=has_subtitle)
        current.append(item)
        y -= row_height

    if current:
        pages.append(current)
    return pages


def _draw_title(c: canvas.Canvas, title: str, subtitle: str | None = None) -> float:
    y = letter[1] - _TOP_MARGIN
    center_x = letter[0] / 2
    c.setFillColor(colors.HexColor("#0f2744"))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(center_x, y, title)
    if subtitle:
        y -= 13
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#3d526b"))
        c.drawCentredString(center_x, y, subtitle)
        y -= 6
    else:
        y -= 8
    c.setStrokeColor(colors.HexColor("#c5d0dc"))
    c.setLineWidth(0.45)
    c.line(_LEFT, y, _RIGHT_EDGE, y)
    return y - 12


def _draw_page_number(c: canvas.Canvas, page_num: int, total_pages: int) -> None:
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#5a6b7c"))
    c.drawRightString(_RIGHT_EDGE, _META_Y, f"Pág. {page_num}/{total_pages}")


def _draw_total_last_page(
    c: canvas.Canvas,
    total_text: str,
    *,
    with_attendance_legend: bool = False,
) -> None:
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#0f2744"))
    c.drawString(_LEFT, _META_Y, total_text)
    if with_attendance_legend:
        _draw_attendance_legend(c, _META_Y - 11)


def _draw_attendance_legend(c: canvas.Canvas, y: float) -> None:
    """Leyenda: rojo = tarde, amarillo = sin salida, naranja = ambos."""
    items = [
        (_TONE_LATE, _ACCENT_LATE, "Tarde (>09:00)"),
        (_TONE_MISSING, _ACCENT_MISSING, "Sin marca"),
        (_TONE_BOTH, _ACCENT_BOTH, "Tarde + sin marca"),
    ]
    x = _LEFT
    size = 7.0
    gap = 12.0
    c.setFont("Helvetica", 6.5)
    for fill, accent, label in items:
        c.setFillColor(fill)
        c.rect(x, y - 1.2, size, size, fill=1, stroke=0)
        c.setFillColor(accent)
        c.rect(x, y - 1.2, 1.8, size, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#c5d0dc"))
        c.setLineWidth(0.4)
        c.rect(x, y - 1.2, size, size, fill=0, stroke=1)
        c.setFillColor(colors.HexColor("#5a6b7c"))
        c.drawString(x + size + 3.5, y, label)
        x += size + 3.5 + c.stringWidth(label, "Helvetica", 6.5) + gap


def _draw_table_header(c: canvas.Canvas, y: float, headers: list[str], widths: list[float]) -> float:
    c.setFillColor(colors.HexColor("#0f2744"))
    c.setFont("Helvetica-Bold", 7.5)
    x = _LEFT
    for header, w in zip(headers, widths):
        c.drawString(x, y, header)
        x += w
    y -= 4
    c.setStrokeColor(colors.HexColor("#c5d0dc"))
    c.setLineWidth(0.5)
    c.line(_LEFT, y, _RIGHT_EDGE, y)
    return y - 9


def _draw_row_band(
    c: canvas.Canvas,
    y: float,
    row_height: float,
    *,
    fill: colors.Color | None,
    accent: colors.Color | None,
) -> None:
    """Sombreado suave detrás de la fila (tipo marca de agua)."""
    band_bottom = y - 2.5
    band_height = row_height - 0.8
    width = _RIGHT_EDGE - _LEFT
    if fill is not None:
        c.setFillColor(fill)
        c.rect(_LEFT, band_bottom, width, band_height, fill=1, stroke=0)
    if accent is not None:
        c.setFillColor(accent)
        c.rect(_LEFT, band_bottom, 2.2, band_height, fill=1, stroke=0)


def _draw_row(
    c: canvas.Canvas,
    y: float,
    values: list[str],
    widths: list[float],
    row_height: float = 14,
    *,
    fill: colors.Color | None = None,
    accent: colors.Color | None = None,
) -> float:
    _draw_row_band(c, y, row_height, fill=fill, accent=accent)
    c.setFillColor(colors.HexColor("#1a2b3c"))
    x = _LEFT
    for i, (value, w) in enumerate(zip(values, widths)):
        text_x = x + (4 if i == 0 and accent is not None else 0)
        c.drawString(text_x, y, value)
        x += w
    return y - row_height


def build_attendance_pdf(report: AttendanceReport, letterhead_path: Path) -> bytes:
    c, buffer = _overlay_canvas()
    title = "Asistencia - Primera y Ultima Marca"
    today = date.today()

    headers = ["Nro.", "Fecha", "Empleado", "Depto.", "Entrada", "Demora", "Salida"]
    widths = [26, 50, 130, 82, 48, 48, 68]

    indexed_rows = list(enumerate(report.rows, start=1))
    pages = _paginate(indexed_rows, _ROW_ATT, has_subtitle=False)
    total_pages = max(1, len(pages))
    total_rows = len(report.rows)

    late_count = 0
    missing_count = 0
    for row in report.rows:
        is_late, _, missing, _in_progress = _attendance_flags(row, today=today)
        if is_late:
            late_count += 1
        if missing:
            missing_count += 1

    for page_idx, page_rows in enumerate(pages, start=1):
        if page_idx > 1:
            c.showPage()

        page_title = title if page_idx == 1 else f"{title} (cont.)"
        y = _draw_title(c, page_title, subtitle=None)
        y = _draw_table_header(c, y, headers, widths)
        c.setFont("Helvetica", 7.5)

        for idx, row in page_rows:
            is_late, delay, missing, in_progress = _attendance_flags(row, today=today)
            fill = None
            accent = None
            if is_late and missing:
                fill, accent = _TONE_BOTH, _ACCENT_BOTH
            elif is_late:
                fill, accent = _TONE_LATE, _ACCENT_LATE
            elif missing:
                fill, accent = _TONE_MISSING, _ACCENT_MISSING

            if in_progress:
                exit_label = "Dia en curso"
            elif missing or row.last_seen_at is None:
                exit_label = "Sin marca"
            else:
                exit_label = row.last_seen_at.strftime("%H:%M")
            entry_label = (
                "—"
                if row.first_seen_at is None
                else row.first_seen_at.strftime("%H:%M")
            )
            values = [
                str(idx),
                _format_date_dmy(row.date),
                format_employee_name(row.employee_name),
                (row.department or "—")[:16],
                entry_label,
                _format_delay(delay),
                exit_label,
            ]
            y = _draw_row(
                c,
                y,
                values,
                widths,
                row_height=_ROW_ATT,
                fill=fill,
                accent=accent,
            )

        _draw_page_number(c, page_idx, total_pages)
        if page_idx == total_pages:
            parts = [f"Total: {total_rows}", f"Tarde: {late_count}"]
            if missing_count:
                parts.append(f"Sin salida: {missing_count}")
            _draw_total_last_page(
                c,
                "  ·  ".join(parts),
                with_attendance_legend=True,
            )

    c.save()
    return _merge_with_letterhead(buffer.getvalue(), letterhead_path)


def build_cafeteria_pdf(report: CafeteriaReport, letterhead_path: Path) -> bytes:
    """
    Listado para el comedor: incluye excepciones GTH en la nómina,
    pero sin hora, sin observación ni resaltado (solo nombres a servir).
    """
    c, buffer = _overlay_canvas()
    title = "Cierre Diario — Comedor"

    headers = ["Nro.", "Empleado", "Departamento"]
    widths = [40, 300, 164]

    indexed = list(enumerate(report.employees, start=1))
    pages = _paginate(indexed, _ROW_CAFE, has_subtitle=False)
    total_pages = max(1, len(pages))

    for page_idx, page_emps in enumerate(pages, start=1):
        if page_idx > 1:
            c.showPage()

        page_title = title if page_idx == 1 else f"{title} (cont.)"
        y = _draw_title(c, page_title, subtitle=None)
        y = _draw_table_header(c, y, headers, widths)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#1a2b3c"))

        for idx, emp in page_emps:
            values = [
                str(idx),
                format_employee_name(emp.employee_name),
                (emp.department or "—")[:32],
            ]
            y = _draw_row(c, y, values, widths, row_height=_ROW_CAFE)

        _draw_page_number(c, page_idx, total_pages)
        if page_idx == total_pages:
            _draw_total_last_page(c, f"Total: {report.headcount}")

    c.save()
    return _merge_with_letterhead(buffer.getvalue(), letterhead_path)

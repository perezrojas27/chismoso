"""
Genera assets/instructivo-reportes-asistencia.pdf
con el mismo formato de membrete/pies que los reportes PDF (fondos / biométrico).

Incluye: roles, asistencia, comedor, excepciones GTH y dispositivos (Admin TI).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ASSETS = Path(__file__).resolve().parent
OUT = ASSETS / "instructivo-reportes-asistencia.pdf"
LETTERHEAD = ASSETS / "hoja-membretada.pdf"

# Misma geometría que backend/app/services/pdf_exporter.py
_TOP_MARGIN = 2.95 * inch
_BOTTOM_SAFE = 1.15 * inch
_META_Y = 1.22 * inch
_LEFT = 0.7 * inch
_RIGHT_EDGE = letter[0] - 0.7 * inch

_NAVY = colors.HexColor("#0f2744")
_MUTED = colors.HexColor("#3d526b")
_LINE = colors.HexColor("#c5d0dc")
_SOFT = colors.HexColor("#f4f7fb")
_BODY = colors.HexColor("#1a2b3c")
_FOOT = colors.HexColor("#5a6b7c")

_CONTENT_W = _RIGHT_EDGE - _LEFT


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=_NAVY,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=_MUTED,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=_NAVY,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=_NAVY,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=_BODY,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=_BODY,
            leftIndent=2,
        ),
        "note": ParagraphStyle(
            "note",
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=_MUTED,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=_BODY,
        ),
        "cell_b": ParagraphStyle(
            "cell_b",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=_NAVY,
        ),
        "th": ParagraphStyle(
            "th",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=_NAVY,
        ),
    }


def _bullets(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(b, styles["bullet"]), leftIndent=8, bulletColor=_NAVY) for b in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontSize=8,
        spaceBefore=0,
        spaceAfter=4,
    )


def _numbered(items: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [
            ListItem(Paragraph(s, styles["bullet"]), leftIndent=8, value=str(i))
            for i, s in enumerate(items, start=1)
        ],
        bulletType="1",
        leftIndent=14,
        bulletFontName="Helvetica-Bold",
        bulletFontSize=8,
        spaceBefore=0,
        spaceAfter=4,
    )


def _styled_table(data: list[list], col_widths: list[float]) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _SOFT),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _SOFT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, _LINE),
                ("LINEBELOW", (0, 1), (-1, -2), 0.3, _LINE),
                ("BOX", (0, 0), (-1, -1), 0.45, _LINE),
            ]
        )
    )
    return table


def _merge_letterhead(overlay_bytes: bytes) -> bytes:
    if not LETTERHEAD.exists():
        return overlay_bytes
    letterhead = PdfReader(str(LETTERHEAD))
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


def _build_story(styles: dict[str, ParagraphStyle]):
    story: list = []

    story.append(Paragraph("Instructivo de uso — Módulo Biométrico", styles["title"]))
    story.append(
        Paragraph(
            "Roles · Asistencia · Comedor · Excepciones GTH · Dispositivos · Exportación PDF",
            styles["subtitle"],
        )
    )

    # —— 1. Acceso ——
    story.append(
        KeepTogether(
            [
                Paragraph("1. Acceso al módulo", styles["h1"]),
                Paragraph(
                    "Abra la aplicación <b>Biométrico</b> (portal Albatros INTEGRADO o entorno local). "
                    "El menú lateral muestra solo las vistas permitidas según su rol. "
                    "En desarrollo local puede usar el selector de rol para simular cada perfil.",
                    styles["body"],
                ),
            ]
        )
    )

    # —— 2. Roles ——
    roles = [
        [
            Paragraph("Rol", styles["th"]),
            Paragraph("Qué puede hacer", styles["th"]),
        ],
        [
            Paragraph("Servicios Generales", styles["cell_b"]),
            Paragraph(
                "Comedor: consultar listado e imprimir PDF. Ve el cierre limpio "
                "(corte 09:00 + inclusiones ya autorizadas por GTH), sin panel de excepciones.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("GTH", styles["cell_b"]),
            Paragraph(
                "Comedor + Asistencia + permisos de excepción (candidatos 09:00–11:00). "
                "Puede autorizar llegadas tardías al comedor y generar PDF de asistencia.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Admin (TI)", styles["cell_b"]),
            Paragraph(
                "Todo lo anterior + pestaña <b>Dispositivos</b>: agregar, probar y eliminar "
                "biométricos por ubicación.",
                styles["cell"],
            ),
        ],
    ]
    story.append(
        KeepTogether(
            [
                Paragraph("2. Roles y permisos", styles["h1"]),
                _styled_table(roles, [_CONTENT_W * 0.28, _CONTENT_W * 0.72]),
            ]
        )
    )

    # —— 3. Asistencia ——
    story.append(Paragraph("3. Reporte de asistencia", styles["h1"]))
    story.append(
        Paragraph(
            "Menú <b>Asistencia</b> — primera y última marca por empleado y día. "
            "Disponible para <b>GTH</b> y <b>Admin</b>.",
            styles["body"],
        )
    )
    story.append(Paragraph("3.1 Qué muestra cada fila", styles["h2"]))
    story.append(
        _bullets(
            [
                "<b>Entrada:</b> primera marca del día.",
                "<b>Salida:</b> última marca del día. Si solo hay una marca: en el <b>día en curso</b> "
                "aparece <b>Día en curso</b>; en días ya cerrados, <b>Sin marca</b>.",
                "<b>Demora:</b> minutos después de las 09:00:00 (corte de llegada).",
                "<b>Empleado / Departamento:</b> nombre formateado y área asociada.",
                "<b>Orden del listado:</b> por fecha y, dentro de cada día, por <b>hora de llegada</b> "
                "(más temprano → más tarde). La salida no altera el orden.",
            ],
            styles,
        )
    )

    story.append(Paragraph("3.2 Selección de periodo", styles["h2"]))
    story.append(
        Paragraph(
            "Use la barra de periodos. Elija el modo y, si aplica, quincena / mes / trimestre / "
            "semestre / año o la fecha ancla. Luego pulse <b>Generar</b>.",
            styles["body"],
        )
    )
    period_rows = [
        [
            Paragraph("Periodo", styles["th"]),
            Paragraph("Qué cubre", styles["th"]),
            Paragraph("Cómo elegirlo", styles["th"]),
        ],
        [
            Paragraph("Día", styles["cell_b"]),
            Paragraph("Una fecha concreta", styles["cell"]),
            Paragraph("Selector de fecha", styles["cell"]),
        ],
        [
            Paragraph("Semana", styles["cell_b"]),
            Paragraph("Lunes a domingo (hasta hoy)", styles["cell"]),
            Paragraph("Elija un día de esa semana", styles["cell"]),
        ],
        [
            Paragraph("Quincena", styles["cell_b"]),
            Paragraph("1–15 o 16–fin de mes", styles["cell"]),
            Paragraph("1Q / 2Q + mes + año", styles["cell"]),
        ],
        [
            Paragraph("Mes", styles["cell_b"]),
            Paragraph("Mes calendario (hasta hoy si está en curso)", styles["cell"]),
            Paragraph("Mes + año", styles["cell"]),
        ],
        [
            Paragraph("Trimestre", styles["cell_b"]),
            Paragraph(
                "3 meses: 1T Ene–Mar · 2T Abr–Jun · 3T Jul–Sep · 4T Oct–Dic",
                styles["cell"],
            ),
            Paragraph("Trimestre + año", styles["cell"]),
        ],
        [
            Paragraph("Semestre", styles["cell_b"]),
            Paragraph("6 meses: 1S Ene–Jun · 2S Jul–Dic", styles["cell"]),
            Paragraph("Semestre + año", styles["cell"]),
        ],
    ]
    story.append(
        KeepTogether(
            [
                _styled_table(
                    period_rows,
                    [_CONTENT_W * 0.18, _CONTENT_W * 0.52, _CONTENT_W * 0.30],
                ),
                Paragraph(
                    "La fecha fin nunca supera el día de hoy. Periodos en curso se cortan en la fecha actual.",
                    styles["note"],
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                Paragraph("3.3 Generar e interpretar", styles["h2"]),
                _numbered(
                    [
                        "Seleccione el <b>periodo</b> y los filtros correspondientes.",
                        "Pulse <b>Generar</b> y espere el listado.",
                        "Revise indicadores: <b>Total</b>, <b>Tarde (&gt;9:00)</b> y <b>Sin salida</b>.",
                        "Fila en tono <b>rojo</b>: llegada después de las 09:00. "
                        "<b>Amarillo</b>: sin marca de salida. "
                        "<b>Naranja</b>: demora y sin marca a la vez.",
                        "Pulse <b>PDF</b> para vista previa / descarga sobre hoja membretada Albatros.",
                    ],
                    styles,
                ),
            ]
        )
    )

    # —— 4. Comedor ——
    story.append(
        KeepTogether(
            [
                Paragraph("4. Reporte de comedor", styles["h1"]),
                Paragraph(
                    "Menú <b>Comedor</b>. Disponible para <b>Servicios Generales</b>, <b>GTH</b> y <b>Admin</b>. "
                    "Lista quién llega a tiempo para el servicio del día.",
                    styles["body"],
                ),
                _bullets(
                    [
                        "<b>Corte:</b> marcas con hora ≤ <b>09:00:00</b> entran al listado.",
                        "<b>Orden:</b> por hora de llegada (más temprano primero).",
                        "<b>Inclusiones GTH:</b> personas autorizadas con llegada después de las 09:00 "
                        "también aparecen en el listado final.",
                        "<b>Servicios Generales:</b> ve el listado limpio (sin detalle de excepciones) "
                        "y puede imprimir el PDF.",
                        "Elija la <b>fecha</b> del cierre y pulse <b>Generar</b> / <b>PDF</b>.",
                    ],
                    styles,
                ),
            ]
        )
    )

    # —— 5. Excepciones GTH ——
    story.append(
        KeepTogether(
            [
                Paragraph("5. Excepciones de comedor (GTH)", styles["h1"]),
                Paragraph(
                    "Solo <b>GTH</b> y <b>Admin</b>. Permite incluir en el comedor a quien marcó "
                    "<b>después de las 09:00</b> y como máximo hasta las <b>11:00</b> "
                    "(primera marca del día en esa ventana).",
                    styles["body"],
                ),
                _numbered(
                    [
                        "Abra <b>Comedor</b> con la fecha del día.",
                        "Revise el panel de <b>candidatos</b> (09:00–11:00).",
                        "Autorice con una observación (motivo del permiso).",
                        "La persona pasa al listado de comedor y al PDF de ese día.",
                        "Puede quitar el permiso si fue un error.",
                    ],
                    styles,
                ),
                Paragraph(
                    "Quien marca después de las 11:00 no aparece como candidato de excepción.",
                    styles["note"],
                ),
            ]
        )
    )

    # —— 6. Dispositivos ——
    story.append(
        KeepTogether(
            [
                Paragraph("6. Dispositivos (Admin TI)", styles["h1"]),
                Paragraph(
                    "Pestaña <b>Dispositivos</b> (solo Admin). Gestiona los biométricos Hikvision "
                    "por <b>ubicación</b> (no se muestran etiquetas técnicas PRINCIPAL/SECUNDARIA).",
                    styles["body"],
                ),
                _bullets(
                    [
                        "<b>Agregar:</b> ubicación + IP + puerto. El sistema asigna un ID interno.",
                        "<b>Probar conexión:</b> valida acceso ISAPI al equipo.",
                        "<b>Descubrimiento:</b> puede detectar vecinos Hikvision en la red local.",
                        "Equipos detectados pero no configurados aparecen como conexión fallida / no configurado.",
                        "Ubicación de referencia actual: Torre Sindoni — Ascensores Pequeños.",
                    ],
                    styles,
                ),
            ]
        )
    )

    # —— 7. PDF ——
    story.append(
        KeepTogether(
            [
                Paragraph("7. Exportación PDF", styles["h1"]),
                Paragraph(
                    "Los PDF de <b>Asistencia</b> y <b>Comedor</b> usan la hoja membretada Albatros. "
                    "Incluyen las mismas columnas/indicadores de la pantalla. En el pie figuran la "
                    "identificación del módulo y la numeración <b>Pág. actual/total</b>.",
                    styles["body"],
                ),
            ]
        )
    )

    # —— 8. Datos ——
    story.append(
        KeepTogether(
            [
                Paragraph("8. Fuente de datos y límites", styles["h1"]),
                Paragraph(
                    "En producción los reportes se arman consultando los biométricos Hikvision (ISAPI). "
                    "Solo aparecen marcas que aún estén en el buffer del terminal. Un reinicio de fábrica "
                    "borra el historial local. Periodos largos (trimestre / semestre) pueden tardar más "
                    "por la paginación de eventos.",
                    styles["body"],
                ),
                Paragraph(
                    "<b>Recomendación:</b> para auditorías, genere y archive el PDF del periodo; "
                    "no dependa solo del almacenamiento del dispositivo.",
                    styles["body"],
                ),
            ]
        )
    )

    # —— 9. Problemas ——
    issues = [
        [
            Paragraph("Situación", styles["th"]),
            Paragraph("Qué revisar", styles["th"]),
        ],
        [
            Paragraph("Bad Gateway / API caída", styles["cell_b"]),
            Paragraph(
                "Backend en ejecución (puerto 8003 en desarrollo) y red hacia los biométricos.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Listado vacío", styles["cell_b"]),
            Paragraph(
                "Personas sincronizadas en el equipo y marcas reales en el rango de fechas.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Solo aparece el código", styles["cell_b"]),
            Paragraph(
                "El terminal debe tener UserInfo; el módulo completa el nombre desde el equipo.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Fecha futura", styles["cell_b"]),
            Paragraph("No se permiten fechas posteriores a hoy.", styles["cell"]),
        ],
        [
            Paragraph("No ve Asistencia / Dispositivos", styles["cell_b"]),
            Paragraph(
                "Verifique el rol: Asistencia = GTH/Admin; Dispositivos = solo Admin.",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Candidato GTH no aparece", styles["cell_b"]),
            Paragraph(
                "La primera marca del día debe estar entre 09:00 y 11:00 (exclusive el corte).",
                styles["cell"],
            ),
        ],
        [
            Paragraph("Conexión fallida a dispositivo", styles["cell_b"]),
            Paragraph(
                "IP/puerto, usuario/clave ISAPI y que el equipo esté en la misma red.",
                styles["cell"],
            ),
        ],
    ]
    story.append(
        KeepTogether(
            [
                Paragraph("9. Problemas frecuentes", styles["h1"]),
                _styled_table(issues, [_CONTENT_W * 0.32, _CONTENT_W * 0.68]),
                Spacer(1, 8),
                Paragraph(
                    "Actualizado julio 2026 · Módulo Biométrico Albatros Corp.",
                    styles["note"],
                ),
            ]
        )
    )
    return story


def build() -> Path:
    styles = _styles()
    story = _build_story(styles)

    frame = Frame(
        _LEFT,
        _BOTTOM_SAFE,
        _RIGHT_EDGE - _LEFT,
        letter[1] - _TOP_MARGIN - _BOTTOM_SAFE,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=6,
        showBoundary=0,
    )

    count_buf = BytesIO()
    count_doc = BaseDocTemplate(
        count_buf,
        pagesize=letter,
        leftMargin=_LEFT,
        rightMargin=letter[0] - _RIGHT_EDGE,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_SAFE,
    )
    count_doc.addPageTemplates(
        [PageTemplate(id="main", frames=[frame], onPage=lambda c, d: None)]
    )
    count_doc.build(list(story))
    total_pages = count_doc.page

    out_buf = BytesIO()

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_FOOT)
        canvas.drawString(
            _LEFT,
            _META_Y,
            "Albatros Corp.  ·  Biométrico  ·  Instructivo de uso",
        )
        canvas.drawRightString(
            _RIGHT_EDGE,
            _META_Y,
            f"Pág. {doc.page}/{total_pages}",
        )
        canvas.restoreState()

    doc = BaseDocTemplate(
        out_buf,
        pagesize=letter,
        leftMargin=_LEFT,
        rightMargin=letter[0] - _RIGHT_EDGE,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_SAFE,
        title="Instructivo — Módulo Biométrico",
        author="Albatros Corp.",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])
    doc.build(_build_story(styles))

    final = _merge_letterhead(out_buf.getvalue())
    OUT.write_bytes(final)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"OK -> {path} ({path.stat().st_size} bytes)")

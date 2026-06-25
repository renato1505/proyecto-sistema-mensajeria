import os
import re
from io import BytesIO


def generar_pdf_reporte(reporte, envio, movimientos, evidencias, autor_reporte="Equipo de Operaciones L'Oreal Mensajeria"):
    return _generar_pdf_reporte_reportlab(reporte, envio, movimientos, evidencias, autor_reporte)

def _generar_pdf_reporte_reportlab(reporte, envio, movimientos, evidencias, autor_reporte):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    navy = colors.HexColor("#082747")
    navy_2 = colors.HexColor("#0f2d5c")
    gold = colors.HexColor("#c0903a")
    green = colors.HexColor("#2e7d32")
    text = colors.HexColor("#162033")
    muted = colors.HexColor("#5f6b7a")
    line = colors.HexColor("#d7dde7")
    side_bg = colors.HexColor("#f4f6f9")

    def draw_text(value, x, y, size=9, font="Helvetica", color=text):
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawString(x, y, str(value or ""))

    def wrap_text(value, max_width, font="Helvetica", size=8.5, max_lines=None):
        words = re.sub(r"\s+", " ", str(value or "")).strip().split()
        lines = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if stringWidth(trial, font, size) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if not lines:
            lines = [""]
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = f"{lines[-1][: max(0, len(lines[-1]) - 3)]}..."
        return lines

    def draw_wrapped(value, x, y, max_width, size=8.5, font="Helvetica", color=text, leading=11, max_lines=None):
        c.setFont(font, size)
        c.setFillColor(color)
        for line_text in wrap_text(value, max_width, font, size, max_lines):
            c.drawString(x, y, line_text)
            y -= leading
        return y

    def section_title(title, x, y, w, align="left"):
        c.setStrokeColor(gold)
        c.setLineWidth(0.8)
        c.line(x, y - 4, x + w, y - 4)
        title_width = stringWidth(title, "Helvetica-Bold", 10.5)
        title_x = x + ((w - title_width) / 2 if align == "center" else 0)
        draw_text(title, title_x, y, size=10.5, font="Helvetica-Bold", color=navy_2)

    def rounded_rect(x, y, w, h, stroke=line, fill=colors.white, radius=6, lw=0.8):
        c.setStrokeColor(stroke)
        c.setFillColor(fill)
        c.setLineWidth(lw)
        c.roundRect(x, y, w, h, radius, stroke=1, fill=1)

    def draw_image_cover(path, x, y, w, h):
        image = ImageReader(path)
        img_w, img_h = image.getSize()
        scale = max(w / img_w, h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        draw_x = x + (w - draw_w) / 2
        draw_y = y + (h - draw_h) / 2

        c.saveState()
        clip = c.beginPath()
        clip.rect(x, y, w, h)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(image, draw_x, draw_y, width=draw_w, height=draw_h, mask="auto")
        c.restoreState()

    def draw_icon(kind, x, y, color=navy_2):
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(1.4)
        if kind == "of":
            c.rect(x - 5, y - 7, 10, 14, stroke=1, fill=0)
            c.line(x - 2, y + 4, x + 2, y + 4)
            c.line(x - 2, y, x + 3, y)
            c.line(x - 2, y - 4, x + 3, y - 4)
        elif kind == "estado":
            c.line(x - 6, y, x - 2, y - 5)
            c.line(x - 2, y - 5, x + 7, y + 6)
        elif kind == "tipo":
            c.line(x - 7, y + 3, x, y + 8)
            c.line(x, y + 8, x + 7, y + 3)
            c.line(x + 7, y + 3, x + 7, y - 5)
            c.line(x + 7, y - 5, x, y - 10)
            c.line(x, y - 10, x - 7, y - 5)
            c.line(x - 7, y - 5, x - 7, y + 3)
        elif kind == "fecha":
            c.rect(x - 7, y - 7, 14, 14, stroke=1, fill=0)
            c.line(x - 7, y + 3, x + 7, y + 3)
            c.line(x - 3, y + 8, x - 3, y + 5)
            c.line(x + 3, y + 8, x + 3, y + 5)
        elif kind == "responsable":
            c.circle(x, y + 4, 4, stroke=1, fill=0)
            c.arc(x - 8, y - 10, x + 8, y + 4, 20, 140)

    def side_item(y, label, value, accent=navy_2, icon="of", max_lines=2):
        c.setStrokeColor(gold)
        c.setLineWidth(0.6)
        c.line(24, y + 24, 155, y + 24)
        c.setStrokeColor(accent)
        c.setLineWidth(1.3)
        c.circle(42, y, 12, stroke=1, fill=0)
        draw_icon(icon, 42, y, accent)
        draw_text(label.upper(), 68, y + 8, size=7.2, font="Helvetica-Bold", color=navy_2)
        draw_wrapped(value, 68, y - 4, 92, size=8.6, font="Helvetica-Bold", color=text, leading=10, max_lines=max_lines)

    estado_visual = "Anulado" if reporte.x_estado == "anulado" else ("Vigente" if reporte.x_estado not in {"resuelto", "cerrado"} else "Resuelto")
    fecha_reporte = reporte.x_fecha_creacion.strftime("%d/%m/%Y %H:%M") if reporte.x_fecha_creacion else "-"
    resumen_cierre = reporte.x_resumen_cierre or "Caso en gestion. Se mantiene seguimiento operativo hasta contar con resolucion final."
    caso = envio.e_orden_flete or f"CASO-{reporte.id}"

    page_num = 0
    main_x = 205
    main_w = width - main_x - 28

    def draw_footer():
        c.setStrokeColor(gold)
        c.setLineWidth(0.8)
        c.line(40, 22, 280, 22)
        draw_text("Uso interno - L'Oreal Mensajeria", 300, 17, size=7.8, color=navy_2)
        draw_text(f"PAGINA {page_num}", 516, 17, size=7.2, color=navy_2)

    def start_page():
        nonlocal page_num
        page_num += 1

        c.setFillColor(navy)
        c.rect(0, height - 82, width, 82, stroke=0, fill=1)
        draw_text("L'OREAL", 30, height - 40, size=28, font="Helvetica-Bold", color=colors.white)
        draw_text("M E N S A J E R I A", 33, height - 62, size=10, font="Helvetica-Bold", color=gold)
        c.setStrokeColor(gold)
        c.setLineWidth(1.1)
        c.line(205, height - 68, 205, height - 18)
        draw_text("REPORTE EJECUTIVO DE CASO", 238, height - 38, size=18, font="Helvetica-Bold", color=colors.white)
        draw_text("Gestion de incidencia con proveedor", 238, height - 58, size=11, font="Helvetica-Bold", color=gold)

        c.setFillColor(side_bg)
        c.rect(0, 32, 178, height - 114, stroke=0, fill=1)
        section_title("DATOS DEL CASO", 24, height - 116, 132, align="center")
        side_item(height - 170, "OF / caso", caso, icon="of")
        side_item(height - 232, "Estado", estado_visual, green if estado_visual == "Resuelto" else navy_2, icon="estado")
        side_item(height - 294, "Tipo", reporte.x_tipo, icon="tipo")
        side_item(height - 370, "Fecha reporte", fecha_reporte, icon="fecha")
        side_item(height - 450, "Responsable", autor_reporte, icon="responsable", max_lines=3)
        section_title("AUTOR DEL REPORTE", 24, 236, 132, align="center")
        draw_text("L'OREAL", 38, 205, size=20, font="Helvetica-Bold", color=colors.black)
        draw_text("M E N S A J E R I A", 42, 188, size=7.5, font="Helvetica-Bold", color=gold)
        draw_wrapped(autor_reporte, 38, 162, 104, size=8.5, font="Helvetica-Bold", color=navy_2, leading=11, max_lines=3)
        section_title("PROVEEDOR", 24, 118, 132, align="center")
        draw_text("starken", 38, 84, size=22, font="Helvetica-Bold", color=green)
        draw_text("Proveedor logistico", 38, 66, size=8.2, color=muted)
        return height - 116

    def new_page():
        draw_footer()
        c.showPage()
        return start_page()

    def ensure_space(y_actual, needed, repeat_title=None):
        if y_actual - needed >= 58:
            return y_actual
        y_nuevo = new_page()
        if repeat_title:
            section_title(repeat_title, main_x, y_nuevo, main_w)
            y_nuevo -= 28
        return y_nuevo

    y = start_page()
    section_title("GESTION EJECUTIVA", main_x, y, main_w)
    y -= 22
    resumen = (
        "El presente informe detalla la gestion realizada por L'Oreal Mensajeria ante una incidencia "
        f"reportada con el proveedor Starken, asociada a la orden de flete {caso}. "
        "Se describe la secuencia de eventos, acciones tomadas, comunicacion mantenida y resolucion obtenida."
    )
    y = draw_wrapped(resumen, main_x, y, main_w, size=9, color=text, leading=12, max_lines=5)

    y -= 8
    section_title("LINEA DE TIEMPO", main_x, y, main_w)
    y -= 28
    line_x = main_x + 8
    timeline_items = []
    for movimiento in movimientos:
        detalle_lineas = wrap_text(movimiento.m_detalle, main_w - 108, size=7.7)
        alto = max(46, 20 + (len(detalle_lineas) * 9))
        timeline_items.append((movimiento, detalle_lineas, alto))

    for idx, (movimiento, detalle_lineas, alto) in enumerate(timeline_items, start=1):
        y = ensure_space(y, alto + 8, "LINEA DE TIEMPO")
        fecha = movimiento.m_fecha.strftime("%d/%m/%Y\n%H:%M hrs.") if movimiento.m_fecha else "-"
        if idx < len(timeline_items):
            c.setStrokeColor(gold)
            c.setLineWidth(1.0)
            c.line(line_x, y + 1, line_x, max(60, y - alto + 8))
        c.setFillColor(gold)
        c.circle(line_x, y + 1, 4, stroke=0, fill=1)
        fecha_lineas = fecha.split("\n")
        draw_text(fecha_lineas[0], main_x + 26, y + 2, size=8.2, font="Helvetica-Bold", color=navy_2)
        if len(fecha_lineas) > 1:
            draw_text(fecha_lineas[1], main_x + 26, y - 9, size=8.2, font="Helvetica-Bold", color=navy_2)
        draw_text(movimiento.m_tipo, main_x + 104, y + 2, size=9, font="Helvetica-Bold", color=navy_2)
        c.setFont("Helvetica", 7.7)
        c.setFillColor(text)
        texto_y = y - 11
        for linea in detalle_lineas:
            c.drawString(main_x + 104, texto_y, linea)
            texto_y -= 9
        y -= alto

    if not movimientos:
        draw_text("Sin movimientos registrados.", main_x + 26, y, size=9, color=muted)
        y -= 32

    y = ensure_space(y - 2, 170)
    section_title("EVIDENCIA DEL CASO", main_x, y, main_w)
    y -= 152
    card_w = (main_w - 12) / 2
    card_h = 134
    evidencia_slots = evidencias if evidencias else [None]
    for idx, evidencia in enumerate(evidencia_slots, start=1):
        if idx > 1 and (idx - 1) % 2 == 0:
            y -= card_h + 18
        y = ensure_space(y + card_h, card_h + 28, "EVIDENCIA DEL CASO") - card_h
        x = main_x + ((idx - 1) % 2) * (card_w + 12)
        rounded_rect(x, y, card_w, card_h, stroke=line, fill=colors.white, radius=4)
        c.setFillColor(navy)
        c.rect(x, y, card_w, 18, stroke=0, fill=1)
        draw_text(f"{idx:02d}. EVIDENCIA", x + 7, y + 6, size=6.5, font="Helvetica-Bold", color=colors.white)
        if evidencia:
            ruta = os.path.join("static", "uploads", "reportes", evidencia.ev_nombre_archivo)
            if os.path.exists(ruta):
                try:
                    draw_image_cover(ruta, x + 8, y + 26, card_w - 16, 96)
                except Exception:
                    draw_text("Imagen no disponible", x + 12, y + 62, size=6.5, color=muted)
            else:
                draw_text("Imagen no disponible", x + 12, y + 62, size=6.5, color=muted)
        else:
            c.setStrokeColor(line)
            c.rect(x + 24, y + 45, card_w - 48, 48, stroke=1, fill=0)
            draw_text("Sin evidencia adjunta", x + 42, y + 66, size=7.2, color=muted)

    y -= 46
    y = ensure_space(y, 98)
    section_title("CIERRE OPERATIVO", main_x, y, main_w)
    y -= 78
    fill = colors.HexColor("#eef8ef") if estado_visual == "Resuelto" else colors.HexColor("#f4f7fb")
    stroke = colors.HexColor("#8ab98f") if estado_visual == "Resuelto" else line
    rounded_rect(main_x, y, main_w, 64, stroke=stroke, fill=fill, radius=6)
    c.setStrokeColor(green if estado_visual == "Resuelto" else navy_2)
    c.setLineWidth(1.4)
    c.circle(main_x + 26, y + 34, 14, stroke=1, fill=0)
    draw_text("OK" if estado_visual == "Resuelto" else "!", main_x + 18, y + 29, size=10, font="Helvetica-Bold", color=green if estado_visual == "Resuelto" else navy_2)
    draw_text(f"El caso {caso} se encuentra {estado_visual.upper()}.", main_x + 56, y + 45, size=9, font="Helvetica-Bold", color=green if estado_visual == "Resuelto" else navy_2)
    draw_wrapped(resumen_cierre, main_x + 56, y + 30, main_w - 72, size=7.5, color=text, leading=9, max_lines=3)
    if reporte.x_of_retorno:
        draw_text(f"OF retorno: {reporte.x_of_retorno}", main_x + 56, y + 8, size=7.8, font="Helvetica-Bold", color=navy_2)

    draw_footer()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

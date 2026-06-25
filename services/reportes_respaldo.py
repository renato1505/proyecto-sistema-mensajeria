from email.message import EmailMessage

from config.settings import CORREO_EMISOR
from services.email_client import enviar_mensaje, proveedor_correo_configurado
from services.historico import destinatarios_respaldo_historico
from services.email_templates import email_shell_html, html_escape
from utils.fechas import fecha_hora_chile_texto


def respaldo_reportes_configurado():
    return bool(destinatarios_respaldo_historico() and proveedor_correo_configurado())


def enviar_respaldo_eliminacion_reporte(
    reporte,
    envio,
    pdf_bytes,
    motivo,
    responsable="Usuario no identificado",
):
    if not respaldo_reportes_configurado():
        raise RuntimeError("Faltan credenciales o destinatarios para respaldar reportes.")

    motivo = motivo or "Sin motivo informado"
    nombre_pdf = f"respaldo_reporte_eliminado_OF_{envio.e_orden_flete or reporte.id}.pdf"
    contenido_html = f"""
        <p style="margin:0 0 16px;color:#344054;line-height:1.5;">
          Se elimino un reporte de excepcion desde el Portal Operativo. El PDF adjunto corresponde al respaldo del caso antes de su eliminacion.
        </p>
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:16px;margin-bottom:16px;">
          <div style="color:#9a3412;font-size:12px;font-weight:800;text-transform:uppercase;">Caso eliminado</div>
          <div style="font-size:18px;font-weight:900;margin-top:6px;">OF {html_escape(envio.e_orden_flete or reporte.id)}</div>
          <div style="color:#344054;margin-top:6px;">Remitente: {html_escape(envio.e_remitente)}</div>
          <div style="color:#344054;">Destinatario: {html_escape(envio.e_destinatario)}</div>
          <div style="color:#344054;">Responsable: {html_escape(responsable)}</div>
          <div style="color:#344054;">Fecha respaldo: {html_escape(fecha_hora_chile_texto())}</div>
        </div>
        <div style="background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:16px;">
          <div style="color:#667085;font-size:12px;font-weight:900;text-transform:uppercase;margin-bottom:6px;">Motivo informado</div>
          <p style="margin:0;color:#111827;font-weight:700;">{html_escape(motivo)}</p>
        </div>
    """

    msg = EmailMessage()
    msg["Subject"] = f"Respaldo reporte eliminado - OF {envio.e_orden_flete or reporte.id}"
    msg["From"] = CORREO_EMISOR
    msg["To"] = ", ".join(destinatarios_respaldo_historico())
    msg.set_content(
        "Se elimino un reporte de excepcion desde el Portal Operativo.\n\n"
        f"OF: {envio.e_orden_flete or reporte.id}\n"
        f"Remitente: {envio.e_remitente}\n"
        f"Destinatario: {envio.e_destinatario}\n"
        f"Responsable: {responsable}\n"
        f"Motivo: {motivo}\n\n"
        "Se adjunta PDF de respaldo.\n"
    )
    msg.add_alternative(
        email_shell_html("Reporte eliminado", "Respaldo operativo", contenido_html, "#7c2d12"),
        subtype="html",
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=nombre_pdf,
    )
    enviar_mensaje(msg)
    return nombre_pdf, destinatarios_respaldo_historico()

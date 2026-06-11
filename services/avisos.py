import io
import re
from collections import defaultdict
from datetime import datetime
from email.message import EmailMessage

import pandas as pd

from config.settings import (
    CORREO_RESPALDO_MENSAJERIA,
)
from database.modelos import Envio
from services.email_client import enviar_mensaje, proveedor_correo_configurado


def correo_avisos_configurado():
    return bool(CORREO_RESPALDO_MENSAJERIA and proveedor_correo_configurado())


def _limpiar_nombre_archivo(texto):
    texto = str(texto or "").strip()
    texto = re.sub(r"[^A-Za-z0-9_.-]+", "_", texto)
    return texto[:90] or "archivo"


def obtener_envios_lote(db, lote):
    return (
        db.query(Envio)
        .filter(Envio.e_lote == lote)
        .order_by(Envio.e_fila_excel.asc(), Envio.id.asc())
        .all()
    )


def obtener_lotes_con_avisos(db):
    envios = (
        db.query(Envio)
        .filter(
            Envio.e_estado == "historico",
            Envio.e_lote.isnot(None),
            Envio.e_resultado_of == "OK",
            Envio.e_orden_flete.isnot(None),
            Envio.e_correo_remitente.isnot(None),
            Envio.e_aviso_funcionario_estado == "pendiente",
        )
        .order_by(Envio.e_fecha_exportacion.desc(), Envio.e_lote.desc())
        .all()
    )

    lotes = {}
    for envio in envios:
        if envio.e_lote not in lotes:
            lotes[envio.e_lote] = {
                "lote": envio.e_lote,
                "fecha": envio.e_fecha_exportacion,
                "envios": 0,
                "funcionarios": set(),
                "archivo": envio.e_nombre_archivo or "",
            }

        lotes[envio.e_lote]["envios"] += 1
        lotes[envio.e_lote]["funcionarios"].add(
            (envio.e_correo_remitente or "").strip().lower()
        )

    resultado = []
    for lote in lotes.values():
        resultado.append({
            "lote": lote["lote"],
            "fecha": lote["fecha"],
            "envios": lote["envios"],
            "funcionarios": len([correo for correo in lote["funcionarios"] if correo]),
            "archivo": lote["archivo"],
        })

    return resultado


def contar_lotes_avisos_pendientes(db):
    lotes = (
        db.query(Envio.e_lote)
        .filter(
            Envio.e_estado == "historico",
            Envio.e_lote.isnot(None),
            Envio.e_resultado_of == "OK",
            Envio.e_orden_flete.isnot(None),
            Envio.e_correo_remitente.isnot(None),
            Envio.e_aviso_funcionario_estado == "pendiente",
        )
        .distinct()
        .all()
    )

    return len(lotes)


def marcar_avisos_pendientes_lote(db, lote):
    envios = (
        db.query(Envio)
        .filter(
            Envio.e_lote == lote,
            Envio.e_resultado_of == "OK",
            Envio.e_orden_flete.isnot(None),
            Envio.e_correo_remitente.isnot(None),
        )
        .all()
    )

    for envio in envios:
        if not envio.e_aviso_funcionario_estado:
            envio.e_aviso_funcionario_estado = "pendiente"

    db.commit()


def _fila_envio(envio, incluir_remitente=True, incluir_detalle_of=True):
    fila = {}

    if incluir_remitente:
        fila.update({
            "Remitente": envio.e_remitente,
            "Correo remitente": envio.e_correo_remitente,
            "Centro de costo": envio.e_centro_costo,
            "Division": envio.e_division,
        })

    fila.update({
        "Destinatario": envio.e_destinatario,
        "RUT destinatario": envio.e_rut_destinatario,
        "Direccion": envio.e_direccion,
        "Comuna": envio.e_comuna,
        "Region": envio.e_region,
        "Telefono": envio.e_telefono_destinatario,
        "Tipo envio": envio.e_tipo_envio,
        "Codigo agencia": envio.e_codigo_agencia or "",
        "Bultos": envio.e_bultos,
        "Kilos": envio.e_kilos,
        "Orden de flete": envio.e_orden_flete or "",
    })

    if incluir_detalle_of:
        fila["Detalle OF"] = envio.e_detalle_of or ""

    return fila


def generar_excel_envios(envios, hoja="Detalle", incluir_remitente=True, incluir_detalle_of=True):
    output = io.BytesIO()
    df = pd.DataFrame([
        _fila_envio(envio, incluir_remitente, incluir_detalle_of)
        for envio in envios
    ])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=hoja[:31])

    output.seek(0)
    return output.getvalue()


def preparar_resumen_avisos(envios):
    grupos = defaultdict(list)
    total_ok = 0
    total_error = 0

    for envio in envios:
        if (
            envio.e_resultado_of == "OK"
            and envio.e_orden_flete
            and envio.e_aviso_funcionario_estado == "pendiente"
        ):
            total_ok += 1
            correo = (envio.e_correo_remitente or "").strip().lower()
            if correo:
                grupos[correo].append(envio)
        elif envio.e_resultado_of:
            total_error += 1

    funcionarios = []
    for correo, items in sorted(grupos.items()):
        funcionarios.append({
            "correo": correo,
            "remitente": items[0].e_remitente or correo,
            "cantidad": len(items),
            "bultos": sum(envio.e_bultos or 0 for envio in items),
            "envios": items,
        })

    return {
        "total_lote": len(envios),
        "total_ok": total_ok,
        "total_error": total_error,
        "funcionarios": funcionarios,
        "respaldo_destino": CORREO_RESPALDO_MENSAJERIA,
    }


def _enviar_correo(destinatario, asunto, cuerpo, nombre_adjunto, contenido_adjunto, html=None):
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = CORREO_EMISOR
    msg["To"] = destinatario
    msg.set_content(cuerpo)

    if html:
        msg.add_alternative(html, subtype="html")

    msg.add_attachment(
        contenido_adjunto,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=nombre_adjunto,
    )

    enviar_mensaje(msg)


def _html_escape(texto):
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tabla_of_html(envios):
    filas = []
    for envio in envios[:12]:
        filas.append(
            "<tr>"
            f"<td>{_html_escape(envio.e_destinatario)}</td>"
            f"<td>{_html_escape(envio.e_comuna)}</td>"
            f"<td><strong>{_html_escape(envio.e_orden_flete)}</strong></td>"
            "</tr>"
        )

    if len(envios) > 12:
        filas.append(
            "<tr>"
            f"<td colspan=\"3\">Y {len(envios) - 12} envio(s) mas en el Excel adjunto.</td>"
            "</tr>"
        )

    return "".join(filas)


def _correo_funcionario_html(lote, remitente, envios):
    return f"""
    <!doctype html>
    <html>
    <body style="margin:0;padding:0;background:#f3f5f7;font-family:Arial,Helvetica,sans-serif;color:#161a1f;">
      <div style="max-width:680px;margin:0 auto;padding:28px 18px;">
        <div style="background:#111827;color:#ffffff;border-radius:8px 8px 0 0;padding:22px 24px;">
          <div style="font-size:18px;font-weight:800;letter-spacing:0;">L'OREAL Mensajeria</div>
          <div style="width:72px;height:3px;background:#d9b66b;margin-top:12px;"></div>
        </div>
        <div style="background:#ffffff;border:1px solid #d9dee5;border-top:0;border-radius:0 0 8px 8px;padding:24px;">
          <p style="margin:0 0 14px;font-size:16px;">Hola {_html_escape(remitente)},</p>
          <p style="margin:0 0 18px;color:#344054;line-height:1.45;">
            Tus envios ya fueron procesados por Mensajeria y cuentan con orden de flete.
          </p>

          <div style="display:block;background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:16px;margin-bottom:18px;">
            <div style="font-size:12px;color:#667085;font-weight:800;text-transform:uppercase;">Resumen</div>
            <div style="font-size:22px;font-weight:900;margin-top:4px;">{len(envios)} envio(s)</div>
            <div style="color:#667085;margin-top:4px;">Lote: {_html_escape(lote)}</div>
            <div style="color:#667085;">Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
          </div>

          <table style="width:100%;border-collapse:collapse;margin:0 0 18px;">
            <thead>
              <tr>
                <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Destinatario</th>
                <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Comuna</th>
                <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Orden de flete</th>
              </tr>
            </thead>
            <tbody>
              {_tabla_of_html(envios)}
            </tbody>
          </table>

          <p style="margin:0;color:#344054;line-height:1.45;">
            Adjuntamos un Excel con el detalle completo para tu respaldo.
          </p>
          <p style="margin:20px 0 0;color:#667085;">
            Saludos,<br>
            <strong>Equipo de Mensajeria</strong><br>
            L'Oreal
          </p>
        </div>
      </div>
    </body>
    </html>
    """


def enviar_respaldo_mensajeria(lote, envios):
    contenido = generar_excel_envios(envios, "Lote completo")
    nombre_adjunto = f"respaldo_{_limpiar_nombre_archivo(lote)}.xlsx"
    asunto = f"Respaldo lote Starken {lote}"
    cuerpo = (
        f"Se adjunta respaldo completo del lote {lote}.\n\n"
        f"Total de envios: {len(envios)}\n"
        f"Fecha respaldo: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        "Equipo de Mensajeria\n"
    )

    _enviar_correo(
        CORREO_RESPALDO_MENSAJERIA,
        asunto,
        cuerpo,
        nombre_adjunto,
        contenido,
    )


def enviar_aviso_funcionario(lote, correo, envios):
    contenido = generar_excel_envios(
        envios,
        "Mis envios",
        incluir_remitente=False,
        incluir_detalle_of=False,
    )
    nombre_adjunto = f"ordenes_flete_{_limpiar_nombre_archivo(lote)}.xlsx"
    remitente = envios[0].e_remitente or "Funcionario"
    asunto = f"Tus envios Starken ya fueron procesados"
    detalle_of = "\n".join(
        f"- {envio.e_orden_flete or 'Sin OF'} | {envio.e_destinatario} | {envio.e_comuna}"
        for envio in envios
    )
    cuerpo = (
        f"Hola {remitente},\n\n"
        "Tus envios fueron procesados por Mensajeria y ya cuentan con orden de flete.\n"
        "Adjuntamos el detalle correspondiente para tu respaldo.\n\n"
        f"Resumen:\n"
        f"- Lote: {lote}\n"
        f"- Total de envios: {len(envios)}\n"
        f"- Fecha de aviso: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        "Ordenes de flete:\n"
        f"{detalle_of}\n\n"
        "Saludos,\n"
        "Equipo de Mensajeria\n"
        "L'Oreal\n"
    )

    _enviar_correo(
        correo,
        asunto,
        cuerpo,
        nombre_adjunto,
        contenido,
        html=_correo_funcionario_html(lote, remitente, envios),
    )


def enviar_avisos_lote(lote, envios, correos_funcionarios):
    if not correo_avisos_configurado():
        raise RuntimeError("Faltan credenciales de correo para enviar avisos.")

    resumen = preparar_resumen_avisos(envios)
    seleccionados = {correo.strip().lower() for correo in correos_funcionarios}
    enviados_funcionarios = 0

    for funcionario in resumen["funcionarios"]:
        correo = funcionario["correo"]
        if correo not in seleccionados:
            continue

        enviar_aviso_funcionario(lote, correo, funcionario["envios"])
        for envio in funcionario["envios"]:
            envio.e_aviso_funcionario_estado = "enviado"
            envio.e_fecha_aviso_funcionario = datetime.now()
        enviados_funcionarios += 1

    return {
        "funcionarios": enviados_funcionarios,
    }

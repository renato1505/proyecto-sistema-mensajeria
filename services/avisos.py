import io
import re
from collections import defaultdict
from email.message import EmailMessage

import pandas as pd

from config.settings import (
    CORREO_EMISOR,
    CORREO_RESPALDO_MENSAJERIA,
)
from database.modelos import Envio
from services.email_client import enviar_mensaje, proveedor_correo_configurado
from services.email_templates import (
    correo_destinatario_html,
    correo_funcionario_html,
    correo_respaldo_mensajeria_html,
)
from utils.fechas import ahora_chile, fecha_hora_chile_texto


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
            Envio.e_anulado.is_(False),
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
            Envio.e_anulado.is_(False),
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
            Envio.e_anulado.is_(False),
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
        "Correo destinatario": envio.e_correo_destinatario,
        "Observacion": envio.e_observacion,
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
    envios_elegibles = [envio for envio in envios if not envio.e_anulado]

    for envio in envios_elegibles:
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
        "total_lote": len(envios_elegibles),
        "total_ok": total_ok,
        "total_error": total_error,
        "funcionarios": funcionarios,
        "respaldo_destino": CORREO_RESPALDO_MENSAJERIA,
    }


def _enviar_correo(destinatario, asunto, cuerpo, nombre_adjunto=None, contenido_adjunto=None, html=None):
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = CORREO_EMISOR
    msg["To"] = destinatario
    msg.set_content(cuerpo)

    if html:
        msg.add_alternative(html, subtype="html")

    if nombre_adjunto and contenido_adjunto:
        msg.add_attachment(
            contenido_adjunto,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=nombre_adjunto,
        )

    enviar_mensaje(msg)


def _primer_nombre(nombre_completo, respaldo="Funcionario"):
    partes = str(nombre_completo or "").strip().split()
    return partes[0] if partes else respaldo


def enviar_respaldo_mensajeria(lote, envios, responsable="Usuario no identificado"):
    contenido = generar_excel_envios(envios, "Lote completo")
    nombre_adjunto = f"respaldo_{_limpiar_nombre_archivo(lote)}.xlsx"
    asunto = f"Respaldo lote Starken {lote}"
    cuerpo = (
        f"Se adjunta respaldo completo del lote {lote}.\n\n"
        f"Total de envios: {len(envios)}\n"
        f"Fecha respaldo: {fecha_hora_chile_texto()}\n\n"
        f"Responsable: {responsable}\n\n"
        "Equipo de Mensajeria\n"
    )

    _enviar_correo(
        CORREO_RESPALDO_MENSAJERIA,
        asunto,
        cuerpo,
        nombre_adjunto,
        contenido,
        html=correo_respaldo_mensajeria_html(lote, envios, responsable),
    )


def enviar_aviso_destinatario(envio):
    correo = (envio.e_correo_destinatario or "").strip()
    if not correo:
        return False

    asunto = "L'Oreal Mensajeria - envio en curso"
    cuerpo = (
        "Te informamos que Mensajeria L'Oreal gestiono un envio a tu nombre mediante Starken.\n\n"
        f"Remitente: {envio.e_remitente}\n"
        f"Orden de flete: {envio.e_orden_flete or 'Sin OF'}\n"
        f"Direccion de entrega: {envio.e_direccion}\n"
        f"Comuna / Region: {envio.e_comuna} / {envio.e_region or 'No informada'}\n"
        f"Telefono registrado: {envio.e_telefono_destinatario or 'No informado'}\n"
        f"Observacion: {envio.e_observacion or 'Sin observacion'}\n\n"
        "Puedes revisar el seguimiento en Starken:\n"
        "https://www.starken.cl/seguimiento\n\n"
        "Si algun dato de entrega no corresponde, comunicate con mensajeria.alcantara@loreal.com.\n\n"
        "Equipo de Mensajeria\n"
        "L'Oreal\n"
    )

    _enviar_correo(
        correo,
        asunto,
        cuerpo,
        html=correo_destinatario_html(envio),
    )
    return True


def enviar_aviso_funcionario(lote, correo, envios):
    contenido = generar_excel_envios(
        envios,
        "Mis envios",
        incluir_remitente=False,
        incluir_detalle_of=False,
    )
    nombre_adjunto = f"ordenes_flete_{_limpiar_nombre_archivo(lote)}.xlsx"
    remitente = envios[0].e_remitente or "Funcionario"
    saludo = _primer_nombre(remitente)
    asunto = f"Tus envios Starken ya fueron procesados"
    detalle_of = "\n".join(
        f"- {envio.e_orden_flete or 'Sin OF'} | {envio.e_destinatario} | {envio.e_comuna}"
        for envio in envios
    )
    cuerpo = (
        f"Hola {saludo},\n\n"
        "Tus envios fueron procesados por Mensajeria y ya cuentan con orden de flete.\n"
        "Adjuntamos el detalle correspondiente para tu respaldo.\n\n"
        f"Resumen:\n"
        f"- Lote: {lote}\n"
        f"- Total de envios: {len(envios)}\n"
        f"- Fecha de aviso: {fecha_hora_chile_texto()}\n\n"
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
        html=correo_funcionario_html(lote, saludo, envios, fecha_hora_chile_texto()),
    )


def enviar_avisos_lote(lote, envios, correos_funcionarios):
    if not correo_avisos_configurado():
        raise RuntimeError("Faltan credenciales de correo para enviar avisos.")

    resumen = preparar_resumen_avisos(envios)
    seleccionados = {correo.strip().lower() for correo in correos_funcionarios}
    enviados_funcionarios = 0
    enviados_destinatarios = 0

    for funcionario in resumen["funcionarios"]:
        correo = funcionario["correo"]
        if correo not in seleccionados:
            continue

        enviar_aviso_funcionario(lote, correo, funcionario["envios"])
        for envio in funcionario["envios"]:
            if enviar_aviso_destinatario(envio):
                enviados_destinatarios += 1

        for envio in funcionario["envios"]:
            envio.e_aviso_funcionario_estado = "enviado"
            envio.e_fecha_aviso_funcionario = ahora_chile()
        enviados_funcionarios += 1

    return {
        "funcionarios": enviados_funcionarios,
        "destinatarios": enviados_destinatarios,
    }


def cancelar_avisos_lote(envios):
    cantidad = 0
    for envio in envios:
        if envio.e_aviso_funcionario_estado == "pendiente":
            envio.e_aviso_funcionario_estado = "cancelado"
            cantidad += 1
    return cantidad

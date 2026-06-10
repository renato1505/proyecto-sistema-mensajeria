from flask import render_template

from database.conexion import SessionLocal
from database.modelos import Envio
from services.estado_sistema import obtener_estado_sistema


def _resumen_pendientes(envios):
    return {
        "total": len(envios),
        "bultos": sum(envio.e_bultos or 0 for envio in envios),
        "kilos": sum(envio.e_kilos or 0 for envio in envios),
        "domicilio": sum(1 for envio in envios if envio.e_tipo_envio == "Domicilio"),
        "agencia": sum(1 for envio in envios if envio.e_tipo_envio == "Agencia"),
    }


def _agrupar_lotes_en_proceso(envios):
    lotes_dict = {}

    for envio in envios:
        lote = envio.e_lote or "SIN_LOTE"

        if lote not in lotes_dict:
            lotes_dict[lote] = {
                "lote": lote,
                "fecha_exportacion": envio.e_fecha_exportacion,
                "envios": [],
            }

        lotes_dict[lote]["envios"].append(envio)

    return list(lotes_dict.values())


def _estado_correo_lote(envios):
    estados_correo = {envio.e_estado_correo for envio in envios if envio.e_estado_correo}

    if "error" in estados_correo:
        return "Error correo"
    if "enviado" in estados_correo:
        return "Correo enviado"
    if "descargado" in estados_correo:
        return "CSV descargado"
    if "pendiente" in estados_correo:
        return "Correo pendiente"
    return "Sin registro"


def _estado_general_lote(envios, resultados):
    if not resultados:
        return "Esperando OF"

    if any(resultado == "ERROR" for resultado in resultados):
        if len(resultados) < len(envios):
            return "Procesado parcialmente"
        return "Con errores"

    if all(resultado == "OK" for resultado in resultados):
        return "Completado"

    return "Procesado parcialmente"


def _completar_metricas_lotes(lotes):
    for lote in lotes:
        envios = lote["envios"]
        resultados = [envio.e_resultado_of for envio in envios if envio.e_resultado_of]

        lote["cantidad_envios"] = len(envios)
        lote["total_bultos"] = sum(envio.e_bultos or 0 for envio in envios)
        lote["total_kilos"] = sum(envio.e_kilos or 0 for envio in envios)
        lote["total_ok"] = sum(1 for envio in envios if envio.e_resultado_of == "OK")
        lote["total_error"] = sum(1 for envio in envios if envio.e_resultado_of == "ERROR")
        lote["total_esperando"] = lote["cantidad_envios"] - len(resultados)
        lote["estado_correo"] = _estado_correo_lote(envios)
        lote["estado_general"] = _estado_general_lote(envios, resultados)


def _resumen_en_proceso(lotes):
    return {
        "lotes": len(lotes),
        "envios": sum(lote["cantidad_envios"] for lote in lotes),
        "bultos": sum(lote["total_bultos"] for lote in lotes),
        "esperando_of": sum(1 for lote in lotes if lote["estado_general"] == "Esperando OF"),
        "correo_error": sum(1 for lote in lotes if lote["estado_correo"] == "Error correo"),
    }


def registrar_rutas_paginas(app):
    @app.route("/")
    def inicio():
        estado = obtener_estado_sistema()
        return render_template("index.html", estado=estado)

    @app.route("/estado_sistema")
    def estado_sistema():
        estado = obtener_estado_sistema()
        return render_template("estado_sistema.html", estado=estado)

    @app.route("/envios")
    def ver_envio():
        db = SessionLocal()
        envios = (
            db.query(Envio)
            .filter(Envio.e_estado == "pendiente")
            .order_by(Envio.e_fecha_creacion.desc(), Envio.id.desc())
            .all()
        )
        resumen = _resumen_pendientes(envios)
        db.close()

        return render_template("envios.html", envios=envios, resumen=resumen)

    @app.route("/en_proceso")
    def ver_en_proceso():
        db = SessionLocal()
        envios_en_proceso = (
            db.query(Envio)
            .filter(Envio.e_estado == "en_proceso")
            .order_by(Envio.e_fecha_exportacion.desc(), Envio.e_fila_excel.asc())
            .all()
        )
        db.close()

        lotes = _agrupar_lotes_en_proceso(envios_en_proceso)
        _completar_metricas_lotes(lotes)
        resumen = _resumen_en_proceso(lotes)

        return render_template("en_proceso.html", lotes=lotes, resumen=resumen)

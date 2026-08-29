from datetime import datetime
from pathlib import Path
from tempfile import gettempdir

import pandas as pd
from sqlalchemy.engine import make_url

from database.modelos import Envio, PuntoRetiro
from services.lotes import obtener_envios_seleccionados_para_lote, preparar_lote_starken
from services.of_processor import procesar_archivo_of
from services.puntos_retiro import (
    PUNTO_ACADEMIA,
    PUNTO_MENSAJERIA_LOCAL,
    asignar_punto_retiro_nuevo_envio,
)
from utils.fechas import ahora_chile


ESCENARIOS_OF_DEMO = {"TODOS_OK", "UNO_ERROR", "MIXTO", "H2H_AMBIGUO"}
OF_DEMO_BASE = 900_000_000_000


class DemoEnvironmentError(RuntimeError):
    pass


def raiz_demo_permitida():
    return (Path(gettempdir()) / "mensajeria-v2-demo").resolve()


def validar_entorno_demo(database_url, app_env, render, demo_root=None):
    if str(render or "").strip().lower() == "true":
        raise DemoEnvironmentError("RENDER=true no permite ejecutar el simulador demo")
    if str(app_env or "").strip().lower() in {"production", "produccion", "prod"}:
        raise DemoEnvironmentError("APP_ENV productivo no permite ejecutar el simulador demo")
    url = make_url(database_url or "")
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise DemoEnvironmentError("El simulador requiere una SQLite demo persistente")
    raiz = raiz_demo_permitida()
    raiz_informada = Path(demo_root or raiz).resolve()
    base = Path(url.database).resolve()
    if raiz_informada != raiz or not base.is_relative_to(raiz):
        raise DemoEnvironmentError("La SQLite demo debe permanecer dentro del directorio TEMP autorizado")
    return base


def _asegurar_puntos_demo(db):
    definiciones = [
        (PUNTO_MENSAJERIA_LOCAL, "Mensajeria local", True, True),
        (PUNTO_ACADEMIA, "Academia", False, False),
    ]
    for codigo, nombre, es_local, metricas in definiciones:
        punto = db.query(PuntoRetiro).filter(PuntoRetiro.pr_codigo == codigo).one_or_none()
        if punto is None:
            db.add(PuntoRetiro(
                pr_codigo=codigo,
                pr_nombre=nombre,
                pr_es_local=es_local,
                pr_incluir_metricas_locales=metricas,
                pr_activo=True,
            ))
    db.flush()


def generar_envios_ficticios(db, cantidad, incluir_academia=False):
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not 1 <= cantidad <= 50:
        raise ValueError("La cantidad demo debe estar entre 1 y 50")
    _asegurar_puntos_demo(db)
    envios = []
    for indice in range(1, cantidad + 1):
        es_agencia = indice % 4 == 0
        es_academia = incluir_academia and indice % 5 == 0
        bultos = (indice % 5) + 1
        envio = Envio(
            e_remitente=f"Funcionario Ficticio {indice:03d}",
            e_correo_remitente=f"funcionario{indice:03d}@demo.invalid",
            e_division=("ACADEMIA DEMO" if es_academia else ["DPGP", "DPP", "DL"][indice % 3]),
            e_centro_costo="ACM" if es_academia else f"DEMO-{indice:04d}",
            e_destinatario=f"Destinatario Ficticio {indice:03d}",
            e_rut_destinatario="0",
            e_direccion=f"Avenida Ficticia {100 + indice}",
            e_comuna="Santiago",
            e_region="Metropolitana",
            e_telefono_destinatario=f"5699000{indice:04d}",
            e_correo_destinatario=f"destino{indice:03d}@demo.invalid",
            e_observacion="Dato exclusivamente ficticio MODO DEMO LOCAL",
            e_tipo_envio="Agencia" if es_agencia else "Domicilio",
            e_codigo_agencia=f"{70000 + indice}" if es_agencia else None,
            e_bultos=bultos,
            e_kilos=bultos,
            e_estado="pendiente",
            e_anulado=False,
        )
        asignar_punto_retiro_nuevo_envio(db, envio)
        db.add(envio)
        envios.append(envio)
    db.flush()
    return envios


def _directorio_starken(demo_root):
    raiz = raiz_demo_permitida()
    informado = Path(demo_root).resolve()
    if informado != raiz:
        raise DemoEnvironmentError("Los archivos demo solo pueden escribirse en TEMP")
    destino = (informado / "starken").resolve()
    if not destino.is_relative_to(raiz):
        raise DemoEnvironmentError("Ruta Starken demo fuera de TEMP")
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def crear_lote_demo(db, envio_ids, demo_root, fecha_actual=None):
    fecha_actual = fecha_actual or ahora_chile()
    envios = obtener_envios_seleccionados_para_lote(db, envio_ids)
    resultado = preparar_lote_starken(envios, fecha_actual, estado_correo="descargado")
    ruta_csv = _directorio_starken(demo_root) / resultado["nombre_archivo"]
    ruta_csv.write_bytes(resultado["contenido_bytes"])
    db.commit()
    resultado["ruta_csv"] = ruta_csv
    return resultado


def generar_respuesta_of_demo(db, lote, escenario, demo_root):
    escenario = str(escenario or "").strip().upper()
    if escenario not in ESCENARIOS_OF_DEMO:
        raise ValueError(f"Escenario OF demo no permitido: {escenario}")
    envios = (
        db.query(Envio)
        .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
        .order_by(Envio.e_fila_excel.asc(), Envio.id.asc())
        .all()
    )
    if not envios:
        raise ValueError("El lote demo no contiene envios en proceso")
    filas = []
    for indice, envio in enumerate(envios):
        es_error = (
            (escenario in {"UNO_ERROR", "H2H_AMBIGUO"} and indice == 0)
            or (escenario == "MIXTO" and indice % 2 == 1)
        )
        detalle = "Procesado correctamente en simulador demo"
        if escenario == "H2H_AMBIGUO" and indice == 0:
            detalle = f"Error al enviar fila {envio.e_fila_excel} a servicio H2H"
        elif es_error:
            detalle = "Error controlado exclusivamente para QA demo"
        filas.append({
            "Estado": "ERROR" if es_error else "OK",
            "Fila": envio.e_fila_excel,
            "Orden Flete": None if es_error else OF_DEMO_BASE + envio.id,
            "Detalle": detalle,
        })
    ruta = _directorio_starken(demo_root) / f"respuesta_{lote}_{escenario}.xlsx"
    pd.DataFrame(filas).to_excel(ruta, index=False, engine="openpyxl")
    return ruta


def procesar_respuesta_of_demo(db, lote, escenario, demo_root):
    ruta = generar_respuesta_of_demo(db, lote, escenario, demo_root)
    with ruta.open("rb") as archivo:
        resultado = procesar_archivo_of(db, lote, archivo, ruta.name)
    resultado["ruta_of"] = ruta
    return resultado


def ejecutar_escenario_demo(db, database_url, app_env, render, cantidad, escenario, demo_root):
    validar_entorno_demo(database_url, app_env, render, demo_root)
    envios = generar_envios_ficticios(db, cantidad)
    db.commit()
    lote = crear_lote_demo(db, [envio.id for envio in envios], demo_root)
    of = procesar_respuesta_of_demo(db, lote["lote"], escenario, demo_root)
    return {"envios": envios, "lote": lote, "of": of}

import io
import logging
from datetime import datetime

import pandas as pd
from flask import flash, redirect, render_template, request, send_file

from database.conexion import SessionLocal
from database.modelos import Envio
from services.carga_masiva import (
    construir_envio_desde_carga,
    eliminar_carga_temporal,
    generar_plantilla_carga_masiva,
    leer_carga_temporal,
    validar_archivo_carga_masiva,
    validar_registros_carga_masiva,
)
from services.correo import (
    correo_starken_configurado,
    enviar_archivo_starken,
    obtener_correo_destino_starken,
)
from services.starken import generar_csv_starken, guardar_respaldo_lote
from utils.validaciones import (
    email_valido,
    normalizar_telefono_chile,
    rut_operativo_valido,
    telefono_chile_valido,
)


logger = logging.getLogger(__name__)


CAMPOS_CARGA_MASIVA = [
    "numero",
    "remitente",
    "correo_remitente",
    "centro_costo",
    "division",
    "destinatario",
    "rut_destinatario",
    "direccion",
    "region",
    "comuna",
    "telefono_destinatario",
    "tipo_envio",
    "bultos",
    "kilos",
    "observacion",
]


def _leer_form_envio():
    return {
        "remitente": request.form.get("remitente", "").strip(),
        "correo_remitente": request.form.get("correo_remitente", "").strip(),
        "division": request.form.get("division", "").strip(),
        "centro_costo": request.form.get("centro_costo", "").strip(),
        "destinatario": request.form.get("destinatario", "").strip(),
        "rut_destinatario": request.form.get("rut_destinatario", "").strip(),
        "direccion": request.form.get("direccion", "").strip(),
        "comuna": request.form.get("comuna", "").strip(),
        "region": request.form.get("region", "").strip(),
        "telefono_destinatario": normalizar_telefono_chile(
            request.form.get("telefono_destinatario", "").strip()
        ),
        "tipo_envio": request.form.get("tipo_envio", "").strip(),
        "codigo_agencia": request.form.get("codigo_agencia", "").strip(),
        "bultos": request.form.get("bultos", "").strip(),
        "kilos": request.form.get("kilos", "").strip(),
    }


def _validar_form_envio(data):
    campos_obligatorios = [
        data["remitente"],
        data["correo_remitente"],
        data["division"],
        data["centro_costo"],
        data["destinatario"],
        data["rut_destinatario"],
        data["direccion"],
        data["comuna"],
        data["region"],
        data["telefono_destinatario"],
        data["tipo_envio"],
        data["bultos"],
        data["kilos"],
    ]

    if not all(campos_obligatorios):
        return None, None, "Todos los campos obligatorios deben estar completos"

    if not email_valido(data["correo_remitente"]):
        return None, None, "El correo del remitente no tiene un formato valido"

    if not rut_operativo_valido(data["rut_destinatario"]):
        return None, None, "Debes ingresar RUT del destinatario o 0 si no fue informado"

    if not telefono_chile_valido(data["telefono_destinatario"]):
        return None, None, "El telefono debe tener 8 o 9 digitos"

    if data["tipo_envio"] == "Agencia":
        if not data["codigo_agencia"]:
            return None, None, "Debes ingresar el codigo de agencia"

        if not data["codigo_agencia"].isdigit():
            return None, None, "El codigo de agencia debe contener solo numeros"

        if len(data["codigo_agencia"]) > 5:
            return None, None, "El codigo de agencia no puede superar 5 digitos"

    try:
        bultos_int = int(data["bultos"])
        kilos_int = int(data["kilos"])
    except ValueError:
        return None, None, "Bultos y kilos deben ser numericos"

    if bultos_int < 1 or kilos_int < 1:
        return None, None, "Bultos y kilos deben ser mayores a 0"

    if bultos_int > 9999 or kilos_int > 9999:
        return None, None, "Bultos y kilos no pueden superar 9999"

    return bultos_int, kilos_int, None


def _aplicar_data_envio(envio, data, bultos_int, kilos_int):
    envio.e_remitente = data["remitente"]
    envio.e_correo_remitente = data["correo_remitente"]
    envio.e_division = data["division"]
    envio.e_centro_costo = data["centro_costo"]
    envio.e_destinatario = data["destinatario"]
    envio.e_rut_destinatario = data["rut_destinatario"]
    envio.e_direccion = data["direccion"]
    envio.e_comuna = data["comuna"]
    envio.e_region = data["region"]
    envio.e_telefono_destinatario = data["telefono_destinatario"]
    envio.e_tipo_envio = data["tipo_envio"]
    envio.e_codigo_agencia = data["codigo_agencia"]
    envio.e_bultos = bultos_int
    envio.e_kilos = kilos_int


def _leer_registros_carga_masiva_desde_form():
    total = int(request.form.get("total_filas", "0") or 0)
    registros = []

    for index in range(total):
        registro = {}
        for campo in CAMPOS_CARGA_MASIVA:
            registro[campo] = request.form.get(f"filas-{index}-{campo}", "").strip()
        registros.append(registro)

    return registros


def registrar_rutas_envios(app):
    @app.route("/nuevo_envio", methods=["GET", "POST"])
    def nuevo_envio():
        if request.method == "POST":
            db = SessionLocal()
            data = _leer_form_envio()
            bultos_int, kilos_int, error = _validar_form_envio(data)

            if error:
                db.close()
                flash(error, "danger")
                return redirect("/nuevo_envio")

            nuevo = Envio(e_estado="pendiente")
            _aplicar_data_envio(nuevo, data, bultos_int, kilos_int)

            db.add(nuevo)
            db.commit()
            db.close()

            flash("Envio registrado correctamente", "success")
            return redirect("/nuevo_envio")

        return render_template("nuevo_envio.html")

    @app.route("/plantilla_carga_masiva")
    def descargar_plantilla_carga_masiva():
        db = SessionLocal()
        try:
            wb = generar_plantilla_carga_masiva(db)
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return send_file(
                output,
                as_attachment=True,
                download_name="plantilla_carga_masiva_mensajeria.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        finally:
            db.close()

    @app.route("/carga_masiva", methods=["GET", "POST"])
    def carga_masiva():
        resultado = None

        if request.method == "POST":
            archivo = request.files.get("archivo")

            if not archivo or not archivo.filename:
                flash("Debes seleccionar un archivo Excel", "danger")
                return redirect("/carga_masiva")

            if not archivo.filename.lower().endswith((".xlsx", ".xls")):
                flash("El archivo debe ser Excel (.xlsx o .xls)", "danger")
                return redirect("/carga_masiva")

            db = SessionLocal()
            try:
                resultado = validar_archivo_carga_masiva(archivo, db)
            except Exception:
                logger.exception("No se pudo validar archivo de carga masiva")
                flash("No se pudo leer el archivo. Revisa que uses la plantilla oficial.", "danger")
                return redirect("/carga_masiva")
            finally:
                db.close()

        return render_template("carga_masiva.html", resultado=resultado)

    @app.route("/confirmar_carga_masiva", methods=["POST"])
    def confirmar_carga_masiva():
        token = request.form.get("token", "").strip()
        registros = leer_carga_temporal(token)

        if not registros:
            flash("La carga ya no esta disponible. Vuelve a subir el archivo.", "warning")
            return redirect("/carga_masiva")

        db = SessionLocal()
        try:
            for data in registros:
                db.add(construir_envio_desde_carga(data))
            db.commit()
            eliminar_carga_temporal(token)
            flash(f"Se cargaron {len(registros)} envios a pendientes", "success")
            return redirect("/envios")
        except Exception:
            db.rollback()
            logger.exception("No se pudo confirmar carga masiva")
            flash("No se pudo guardar la carga masiva", "danger")
            return redirect("/carga_masiva")
        finally:
            db.close()

    @app.route("/revalidar_carga_masiva", methods=["POST"])
    def revalidar_carga_masiva():
        registros = _leer_registros_carga_masiva_desde_form()

        if not registros:
            flash("No hay filas para revalidar", "warning")
            return redirect("/carga_masiva")

        db = SessionLocal()
        try:
            resultado = validar_registros_carga_masiva(registros, db)
        finally:
            db.close()

        return render_template("carga_masiva.html", resultado=resultado)

    @app.route("/generar_excel", methods=["POST"])
    def generar_excel():
        db = SessionLocal()

        envios_pendientes = (
            db.query(Envio)
            .filter(Envio.e_estado == "pendiente")
            .order_by(Envio.id.asc())
            .all()
        )

        if not envios_pendientes:
            db.close()
            flash("No hay envios pendientes para generar y enviar", "warning")
            return redirect("/envios")

        agencias_sin_codigo = [
            envio for envio in envios_pendientes
            if envio.e_tipo_envio == "Agencia" and not envio.e_codigo_agencia
        ]

        if agencias_sin_codigo:
            db.close()
            flash(
                "Hay envios de agencia sin codigo. Editalos antes de generar el lote Starken.",
                "danger",
            )
            return redirect("/envios")

        if not correo_starken_configurado():
            db.close()
            flash("Faltan credenciales de correo en .env. No se genero ningun lote.", "danger")
            return redirect("/envios")

        fecha_actual = datetime.now()
        lote = fecha_actual.strftime("LOTE-%Y%m%d-%H%M%S")
        nombre_archivo, contenido_bytes = generar_csv_starken(envios_pendientes, fecha_actual)

        fila_excel = 2
        for envio in envios_pendientes:
            envio.e_estado = "en_proceso"
            envio.e_lote = lote
            envio.e_fila_excel = fila_excel
            envio.e_fecha_exportacion = fecha_actual
            envio.e_nombre_archivo = nombre_archivo
            envio.e_correo_destino = obtener_correo_destino_starken()
            envio.e_fecha_envio_correo = None
            envio.e_estado_correo = "pendiente"
            fila_excel += 1

        cantidad_envios = len(envios_pendientes)

        try:
            guardar_respaldo_lote(nombre_archivo, contenido_bytes)
        except Exception as e:
            db.rollback()
            db.close()
            logger.exception("No se pudo guardar respaldo local de lote Starken")
            flash(f"No se pudo guardar el respaldo local del CSV: {str(e)}", "danger")
            return redirect("/envios")

        db.commit()

        try:
            enviar_archivo_starken(nombre_archivo, contenido_bytes, lote)

            for envio in envios_pendientes:
                envio.e_fecha_envio_correo = fecha_actual
                envio.e_estado_correo = "enviado"

            db.commit()
            db.close()

            flash(f"Archivo enviado correctamente por correo. Lote generado: {lote}", "success")
            return redirect("/en_proceso")

        except Exception as e:
            db.rollback()
            logger.exception("No se pudo enviar correo Starken para lote %s", lote)

            for envio in envios_pendientes:
                envio_db = db.query(Envio).filter(Envio.id == envio.id).first()
                if envio_db:
                    envio_db.e_estado_correo = "error"

            db.commit()
            db.close()

            flash(
                f"Lote {lote} creado y respaldado con {cantidad_envios} envio(s), "
                f"pero no se pudo enviar el correo: {str(e)}",
                "danger",
            )
            return redirect("/en_proceso")

    @app.route("/cargar_of/<lote>", methods=["POST"])
    def cargar_of(lote):
        db = SessionLocal()
        archivo = request.files.get("archivo_of")

        if not archivo or archivo.filename == "":
            db.close()
            flash("Debes seleccionar un archivo Excel OF", "danger")
            return redirect("/en_proceso")

        try:
            nombre_archivo = archivo.filename.lower()

            if nombre_archivo.endswith(".xls"):
                df = pd.read_excel(archivo, engine="xlrd")
            else:
                df = pd.read_excel(archivo, engine="openpyxl")

            df.columns = [str(col).strip().lower() for col in df.columns]

            columnas_requeridas = ["estado", "fila", "orden flete", "detalle"]
            for columna in columnas_requeridas:
                if columna not in df.columns:
                    db.close()
                    flash(f"Falta la columna requerida: {columna}", "danger")
                    return redirect("/en_proceso")

            envios_lote = (
                db.query(Envio)
                .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
                .all()
            )

            if not envios_lote:
                db.close()
                flash("No se encontraron envios en proceso para este lote", "warning")
                return redirect("/en_proceso")

            cantidad_envios_lote = len(envios_lote)
            df_validas = df[df["fila"].notna()].copy()
            cantidad_filas_archivo = len(df_validas)

            if cantidad_filas_archivo != cantidad_envios_lote:
                db.close()
                flash(
                    f"La cantidad de filas del archivo OF ({cantidad_filas_archivo}) "
                    f"no coincide con la cantidad de envios del lote "
                    f"({cantidad_envios_lote}). No se proceso nada.",
                    "danger",
                )
                return redirect("/en_proceso")

            filas_archivo = []
            for valor in df_validas["fila"].tolist():
                try:
                    filas_archivo.append(int(valor))
                except (ValueError, TypeError):
                    db.close()
                    flash("El archivo OF contiene una fila invalida en la columna 'fila'", "danger")
                    return redirect("/en_proceso")

            if len(filas_archivo) != len(set(filas_archivo)):
                db.close()
                flash("El archivo OF tiene filas repetidas. No se proceso nada.", "danger")
                return redirect("/en_proceso")

            ofs_archivo = []
            for _, fila in df_validas.iterrows():
                estado = str(fila.get("estado", "")).strip().upper()
                orden_flete = fila.get("orden flete")

                if estado == "OK" and not pd.isna(orden_flete):
                    orden_texto = str(orden_flete).strip()
                    if orden_texto:
                        ofs_archivo.append(orden_texto)

            if len(ofs_archivo) != len(set(ofs_archivo)):
                db.close()
                flash("El archivo OF contiene ordenes de flete duplicadas. No se proceso nada.", "danger")
                return redirect("/en_proceso")

            if ofs_archivo:
                ofs_existentes = (
                    db.query(Envio)
                    .filter(Envio.e_orden_flete.in_(ofs_archivo), Envio.e_lote != lote)
                    .all()
                )

                if ofs_existentes:
                    repetidas = sorted({e.e_orden_flete for e in ofs_existentes if e.e_orden_flete})
                    db.close()
                    flash(
                        f"Ya existen ordenes de flete registradas en el sistema: "
                        f"{', '.join(repetidas)}. No se proceso nada.",
                        "danger",
                    )
                    return redirect("/en_proceso")

            total_ok = 0
            total_error = 0
            total_sin_match = 0

            for _, fila in df_validas.iterrows():
                estado = str(fila.get("estado", "")).strip().upper()
                fila_excel = fila.get("fila")
                orden_flete = fila.get("orden flete")
                detalle = fila.get("detalle")

                try:
                    fila_excel = int(fila_excel)
                except (ValueError, TypeError):
                    continue

                envio = (
                    db.query(Envio)
                    .filter(
                        Envio.e_lote == lote,
                        Envio.e_fila_excel == fila_excel,
                        Envio.e_estado == "en_proceso",
                    )
                    .first()
                )

                if not envio:
                    total_sin_match += 1
                    continue

                detalle_texto = "" if pd.isna(detalle) else str(detalle).strip()
                orden_texto = "" if pd.isna(orden_flete) else str(orden_flete).strip()

                envio.e_resultado_of = estado
                envio.e_detalle_of = detalle_texto

                if estado == "OK":
                    envio.e_orden_flete = orden_texto
                    envio.e_estado = "historico"
                    total_ok += 1
                else:
                    envio.e_orden_flete = None
                    envio.e_estado = "en_proceso"
                    total_error += 1

            db.commit()
            db.close()

            flash(
                f"Archivo OF procesado correctamente. OK: {total_ok} | "
                f"ERROR: {total_error} | Sin coincidencia: {total_sin_match}",
                "success",
            )
            return redirect("/en_proceso")

        except Exception as e:
            db.rollback()
            db.close()
            logger.exception("Error al procesar archivo OF para lote %s", lote)
            flash(f"Error al procesar el archivo OF: {str(e)}", "danger")
            return redirect("/en_proceso")

    @app.route("/cancelar_lote/<lote>", methods=["POST"])
    def cancelar_lote(lote):
        db = SessionLocal()

        envios_lote = (
            db.query(Envio)
            .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
            .all()
        )

        if not envios_lote:
            db.close()
            flash("No se encontro el lote o ya no esta en proceso", "warning")
            return redirect("/en_proceso")

        for envio in envios_lote:
            envio.e_estado = "pendiente"
            envio.e_lote = None
            envio.e_fila_excel = None
            envio.e_fecha_exportacion = None
            envio.e_resultado_of = None
            envio.e_detalle_of = None
            envio.e_orden_flete = None
            envio.e_estado_correo = None

        db.commit()
        db.close()

        flash("Lote cancelado correctamente. Los envios volvieron a pendientes", "warning")
        return redirect("/en_proceso")

    @app.route("/eliminar_envio/<int:id>", methods=["POST"])
    def eliminar_envio(id):
        db = SessionLocal()
        envio = db.query(Envio).filter(Envio.id == id).first()

        if envio:
            db.delete(envio)
            db.commit()
            flash("Envio eliminado correctamente", "danger")

        db.close()
        return redirect("/envios")

    @app.route("/editar_envio/<int:id>", methods=["GET", "POST"])
    def editar_envio(id):
        db = SessionLocal()
        envio = db.query(Envio).filter(Envio.id == id).first()

        if not envio:
            db.close()
            flash("El envio no existe", "danger")
            return redirect("/envios")

        if request.method == "POST":
            data = _leer_form_envio()
            bultos_int, kilos_int, error = _validar_form_envio(data)

            if error:
                db.close()
                flash(error, "danger")
                return redirect(f"/editar_envio/{id}")

            _aplicar_data_envio(envio, data, bultos_int, kilos_int)

            db.commit()
            db.close()

            flash("Envio editado correctamente", "warning")
            return redirect("/envios")

        db.close()
        return render_template("editar_envio.html", envio=envio)

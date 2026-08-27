import io
import logging

from flask import flash, redirect, render_template, request, send_file

from database.conexion import SessionLocal
from services.carga_masiva import (
    construir_envio_desde_carga,
    eliminar_carga_temporal,
    generar_plantilla_carga_masiva,
    leer_carga_temporal,
    validar_archivo_carga_masiva,
    validar_registros_carga_masiva,
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
    "correo_destinatario",
    "tipo_envio",
    "bultos",
    "kilos",
    "observacion",
]

CAMPOS_CAMBIO_MASIVO = {"rut_destinatario", "tipo_envio", "kilos"}


def aplicar_cambio_masivo_carga(registros, indices, campo, valor):
    if not registros:
        raise ValueError("No hay filas disponibles")
    if not indices:
        raise ValueError("Selecciona al menos una fila")
    if len(indices) != len(set(indices)):
        raise ValueError("La seleccion contiene filas duplicadas")
    if campo not in CAMPOS_CAMBIO_MASIVO:
        raise ValueError("Campo de actualizacion no permitido")
    if any(index < 0 or index >= len(registros) for index in indices):
        raise ValueError("La seleccion contiene filas inexistentes")

    if campo == "rut_destinatario":
        if valor != "0":
            raise ValueError("El unico RUT masivo permitido es 0")
        valor_validado = "0"
    elif campo == "tipo_envio":
        if valor not in {"Domicilio", "Agencia"}:
            raise ValueError("Tipo de envio no permitido")
        valor_validado = valor
    else:
        try:
            kilos = int(valor)
        except (TypeError, ValueError):
            raise ValueError("Kilos debe ser un numero entero") from None
        if not 1 <= kilos <= 9999:
            raise ValueError("Kilos debe estar entre 1 y 9999")
        valor_validado = str(kilos)

    actualizados = [dict(registro) for registro in registros]
    for index in indices:
        actualizados[index][campo] = valor_validado
    return actualizados


def _leer_registros_carga_masiva_desde_form():
    total = int(request.form.get("total_filas", "0") or 0)
    registros = []

    for index in range(total):
        registro = {}
        for campo in CAMPOS_CARGA_MASIVA:
            registro[campo] = request.form.get(f"filas-{index}-{campo}", "").strip()
        registros.append(registro)

    return registros


def registrar_rutas_carga_masiva(app):
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

    @app.route("/aplicar_cambio_masivo_carga", methods=["POST"])
    def aplicar_cambio_masivo():
        try:
            registros = _leer_registros_carga_masiva_desde_form()
            indices_texto = request.form.getlist("filas_seleccionadas")
            indices = [int(indice) for indice in indices_texto]
            registros = aplicar_cambio_masivo_carga(
                registros,
                indices,
                request.form.get("campo_masivo", "").strip(),
                request.form.get("valor_masivo", "").strip(),
            )
        except (TypeError, ValueError) as exc:
            flash(str(exc), "danger")
            return redirect("/carga_masiva")

        db = SessionLocal()
        try:
            resultado = validar_registros_carga_masiva(registros, db)
        finally:
            db.close()

        flash(f"Se modificaron {len(indices)} registros seleccionados", "success")
        return render_template("carga_masiva.html", resultado=resultado)

import io

import pandas as pd
from flask import request, send_file

from database.conexion import SessionLocal
from routes.admin_helpers import requiere_admin
from services.admin_context import leer_filtros_auditoria
from services.auditoria import listar_auditoria, registrar_accion
from utils.fechas import timestamp_archivo_chile


def registrar_rutas_admin_auditoria(app):
    @app.route("/admin/auditoria/exportar")
    def admin_exportar_auditoria():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        filtros_auditoria = leer_filtros_auditoria(request.args)
        filtros_auditoria["limite"] = request.args.get("aud_limite", "200").strip()

        db = SessionLocal()
        try:
            registros = listar_auditoria(db, **filtros_auditoria)
            filas = [
                {
                    "Fecha": item.a_fecha.strftime("%d/%m/%Y %H:%M:%S") if item.a_fecha else "",
                    "Usuario": item.a_usuario,
                    "Accion": item.a_accion,
                    "Entidad": item.a_entidad,
                    "ID entidad": item.a_entidad_id,
                    "Detalle": item.a_detalle,
                }
                for item in registros
            ]
            registrar_accion(
                db,
                "exportar_auditoria",
                "auditoria",
                "",
                f"Registros exportados: {len(registros)}",
            )
            db.commit()
        finally:
            db.close()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(filas).to_excel(writer, index=False, sheet_name="Auditoria")

        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"auditoria_portal_{timestamp_archivo_chile()}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

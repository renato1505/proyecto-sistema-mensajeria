from flask import jsonify, request

from database.conexion import SessionLocal
from database.modelos import Envio


def registrar_rutas_historico_ajax(app):
    @app.route("/buscar_of_historico")
    def buscar_of_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 1:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_orden_flete)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_orden_flete.isnot(None),
                Envio.e_orden_flete.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])

    @app.route("/buscar_destinatarios_historico")
    def buscar_destinatarios_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 2:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_destinatario)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_destinatario.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])

    @app.route("/buscar_remitentes_historico")
    def buscar_remitentes_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 2:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_remitente)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_remitente.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])

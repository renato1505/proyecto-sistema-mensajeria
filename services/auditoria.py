from flask import session

from database.modelos import RegistroAuditoria


def usuario_actual_auditoria():
    return session.get("usuario_nombre") or "sistema"


def registrar_accion(db, accion, entidad, entidad_id="", detalle="", usuario=None):
    registro = RegistroAuditoria(
        a_usuario=usuario or usuario_actual_auditoria(),
        a_accion=str(accion or "")[:120],
        a_entidad=str(entidad or "")[:80],
        a_entidad_id=str(entidad_id or "")[:80],
        a_detalle=str(detalle or "")[:1500],
    )
    db.add(registro)
    return registro

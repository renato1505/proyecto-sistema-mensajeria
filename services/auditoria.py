from flask import session

from database.modelos import RegistroAuditoria
from utils.fechas import ahora_chile


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


def listar_auditoria(db, usuario="", accion="", entidad="", limite=80):
    query = db.query(RegistroAuditoria)

    usuario = (usuario or "").strip()
    accion = (accion or "").strip()
    entidad = (entidad or "").strip()
    try:
        limite = int(limite or 80)
    except (TypeError, ValueError):
        limite = 80
    limite = min(max(limite, 20), 200)

    if usuario:
        query = query.filter(RegistroAuditoria.a_usuario.ilike(f"%{usuario}%"))
    if accion:
        query = query.filter(RegistroAuditoria.a_accion.ilike(f"%{accion}%"))
    if entidad:
        query = query.filter(RegistroAuditoria.a_entidad.ilike(f"%{entidad}%"))

    return query.order_by(RegistroAuditoria.a_fecha.desc(), RegistroAuditoria.id.desc()).limit(limite).all()


def metricas_auditoria(db):
    hoy = ahora_chile().date()
    registros = db.query(RegistroAuditoria).all()
    acciones_hoy = 0
    usuarios = set()

    for registro in registros:
        fecha = registro.a_fecha.date() if registro.a_fecha else None
        if fecha == hoy:
            acciones_hoy += 1
        if registro.a_usuario:
            usuarios.add(registro.a_usuario)

    return {
        "total": len(registros),
        "hoy": acciones_hoy,
        "usuarios": len(usuarios),
    }


def listar_accesos_recientes(db, limite=20):
    acciones = ["login_exitoso", "login_fallido", "login_bloqueado"]
    try:
        limite = int(limite or 20)
    except (TypeError, ValueError):
        limite = 20
    limite = min(max(limite, 5), 80)

    return (
        db.query(RegistroAuditoria)
        .filter(RegistroAuditoria.a_accion.in_(acciones))
        .order_by(RegistroAuditoria.a_fecha.desc(), RegistroAuditoria.id.desc())
        .limit(limite)
        .all()
    )


def listar_eventos_recientes(db, limite=8):
    acciones = [
        "crear_usuario",
        "editar_usuario",
        "cambiar_clave_usuario",
        "generar_clave_recuperacion",
        "eliminar_usuario",
        "cambiar_estado_usuario",
        "desbloquear_login",
        "permiso_denegado",
        "eliminar_historico",
        "anular_historico",
        "crear_reporte",
        "cerrar_reporte",
    ]
    try:
        limite = int(limite or 8)
    except (TypeError, ValueError):
        limite = 8
    limite = min(max(limite, 4), 20)

    return (
        db.query(RegistroAuditoria)
        .filter(RegistroAuditoria.a_accion.in_(acciones))
        .order_by(RegistroAuditoria.a_fecha.desc(), RegistroAuditoria.id.desc())
        .limit(limite)
        .all()
    )


def actividades_por_usuario(db, usuarios, limite_por_usuario=4):
    actividades = {}
    for usuario in usuarios:
        codigo = (usuario.u_usuario or "").strip()
        if not codigo:
            continue
        actividades[usuario.id] = (
            db.query(RegistroAuditoria)
            .filter(RegistroAuditoria.a_usuario == codigo)
            .order_by(RegistroAuditoria.a_fecha.desc(), RegistroAuditoria.id.desc())
            .limit(limite_por_usuario)
            .all()
        )
    return actividades

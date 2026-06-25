from routes.auth import (
    bloqueos_por_usuario,
    listar_bloqueos_login,
    metricas_seguridad_login,
)
from services.auditoria import (
    actividades_por_usuario,
    listar_accesos_recientes,
    listar_auditoria,
    listar_eventos_recientes,
    metricas_auditoria,
)
from services.permisos import AREAS_BASE, ROLES_BASE, matriz_permisos
from services.recuperacion import (
    contar_solicitudes_pendientes,
    listar_solicitudes_recuperacion,
)
from services.usuarios import (
    asegurar_areas_base,
    conteo_usuarios_por_area,
    estadisticas_usuarios,
    listar_areas,
    listar_usuarios,
    salud_usuarios,
)


TABS_ADMIN = {"usuarios", "seguridad", "auditoria"}


def leer_tab_admin(args):
    tab = args.get("tab", "usuarios").strip().lower()
    return tab if tab in TABS_ADMIN else "usuarios"


def leer_filtros_auditoria(args):
    return {
        "usuario": args.get("aud_usuario", "").strip(),
        "accion": args.get("aud_accion", "").strip(),
        "entidad": args.get("aud_entidad", "").strip(),
        "limite": args.get("aud_limite", "80").strip(),
    }


def construir_contexto_admin(db, args, session_data):
    admin_tab = leer_tab_admin(args)
    filtros_auditoria = leer_filtros_auditoria(args)
    asegurar_areas_base(db)
    db.commit()
    usuarios = listar_usuarios(db)
    bloqueos_usuario = bloqueos_por_usuario()
    areas = listar_areas(db)

    return {
        "areas": areas,
        "areas_base": AREAS_BASE,
        "roles_base": ROLES_BASE,
        "usuarios_por_area": conteo_usuarios_por_area(db),
        "usuarios": usuarios,
        "salud_usuarios": salud_usuarios(usuarios, bloqueos_usuario),
        "metricas": estadisticas_usuarios(db),
        "eventos_recientes": listar_eventos_recientes(db),
        "actividades_usuarios": actividades_por_usuario(db, usuarios),
        "admin_tab": admin_tab,
        "auditoria": listar_auditoria(db, **filtros_auditoria),
        "auditoria_metricas": metricas_auditoria(db),
        "auditoria_filtros": filtros_auditoria,
        "seguridad_login": listar_bloqueos_login(),
        "seguridad_metricas": metricas_seguridad_login(),
        "accesos_recientes": listar_accesos_recientes(db),
        "solicitudes_recuperacion": listar_solicitudes_recuperacion(db, estado="pendiente"),
        "solicitudes_pendientes_count": contar_solicitudes_pendientes(db),
        "permisos_matriz": matriz_permisos(
            session_data.get("usuario_area"),
            session_data.get("usuario_rol"),
        ),
    }

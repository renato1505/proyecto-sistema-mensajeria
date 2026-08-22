PERMISOS_MODULOS = {
    "administracion": {
        "admin.panel": "Entrar a Administracion",
        "admin.usuarios": "Gestionar usuarios y areas",
        "admin.seguridad": "Revisar seguridad y permisos",
        "admin.auditoria": "Consultar auditoria",
    },
    "mensajeria": {
        "mensajeria.inicio": "Ver inicio de Mensajeria",
        "envios.crear": "Crear envios individuales",
        "carga_masiva.gestionar": "Cargar envios masivos",
        "pendientes.gestionar": "Revisar pendientes y generar CSV",
        "proceso.gestionar": "Gestionar lotes en proceso y OF",
        "historico.ver": "Ver historico",
        "historico.exportar": "Exportar o descargar historico",
        "historico.anular": "Anular ordenes de flete",
        "historico.eliminar": "Eliminar historico con respaldo",
        "reportes.ver": "Ver reportes y excepciones",
        "reportes.gestionar": "Gestionar reportes y excepciones",
        "avisos.ver": "Ver avisos por correo",
        "avisos.gestionar": "Gestionar avisos por correo",
        "catalogos.ver": "Ver catalogos operativos",
        "catalogos.gestionar": "Gestionar catalogos operativos",
    },
    "recepcion": {
        "recepcion.panel": "Modulo Recepcion reservado",
    },
    "seguridad": {
        "seguridad.panel": "Modulo Seguridad reservado",
    },
}

AREAS_BASE = {
    "administracion": "Administracion",
    "mensajeria": "Mensajeria",
    "recepcion": "Recepcion",
    "seguridad": "Seguridad",
}

ROLES_BASE = {
    "visita": "Visita",
    "usuario": "Usuario",
    "supervisor": "Supervisor",
    "admin": "Administrador",
}

PERMISOS_LECTURA = {
    "mensajeria.inicio",
    "historico.ver",
    "reportes.ver",
    "avisos.ver",
    "catalogos.ver",
}

PERMISOS_USUARIO_MENSAJERIA = PERMISOS_LECTURA | {
    "envios.crear",
    "carga_masiva.gestionar",
    "pendientes.gestionar",
    "proceso.gestionar",
    "historico.exportar",
    "avisos.gestionar",
    "catalogos.gestionar",
}


RUTAS_PERMISOS = [
    # Toda ruta nueva que muestre o modifique datos operativos debe quedar aca.
    # Si se omite, el menu puede ocultar la accion, pero la URL directa no queda
    # protegida por rol.
    ("/admin", "admin.panel"),
    ("/crear_envio", "envios.crear"),
    ("/nuevo_envio", "envios.crear"),
    ("/eliminar_envio", "pendientes.gestionar"),
    ("/carga_masiva", "carga_masiva.gestionar"),
    ("/plantilla_carga_masiva", "carga_masiva.gestionar"),
    ("/confirmar_carga_masiva", "carga_masiva.gestionar"),
    ("/revalidar_carga_masiva", "carga_masiva.gestionar"),
    ("/envios", "pendientes.gestionar"),
    ("/editar_envio", "pendientes.gestionar"),
    ("/generar_excel", "pendientes.gestionar"),
    ("/en_proceso", "proceso.gestionar"),
    ("/cargar_of", "proceso.gestionar"),
    ("/of_exito", "proceso.gestionar"),
    ("/of_correo", "proceso.gestionar"),
    ("/procesar_of_correo", "proceso.gestionar"),
    ("/cancelar_lote", "proceso.gestionar"),
    ("/historico", "historico.ver"),
    ("/buscar_of_historico", "historico.ver"),
    ("/buscar_destinatarios_historico", "historico.ver"),
    ("/buscar_remitentes_historico", "historico.ver"),
    ("/exportar_historico", "historico.exportar"),
    ("/descargar_envio_historico", "historico.exportar"),
    ("/descargar_historico_seleccionados", "historico.exportar"),
    ("/anular_historico_seleccionados", "historico.anular"),
    ("/eliminar_historico", "historico.eliminar"),
    ("/eliminar_historico_seleccionados", "historico.eliminar"),
    ("/eliminar_historico_filtrados", "historico.eliminar"),
    ("/reportes/crear", "reportes.gestionar"),
    ("/reportes", "reportes.ver"),
    ("/buscar_reportes_sugerencias", "reportes.ver"),
    ("/avisos", "avisos.ver"),
    ("/avisos_lote", "avisos.gestionar"),
    ("/enviar_avisos_lote", "avisos.gestionar"),
    ("/cancelar_avisos_lote", "avisos.gestionar"),
    ("/catalogos", "catalogos.ver"),
    ("/buscar_remitentes", "catalogos.ver"),
    ("/buscar_destinatarios", "catalogos.ver"),
    ("/buscar_comunas", "catalogos.ver"),
    ("/guardar_remitente", "catalogos.gestionar"),
    ("/guardar_destinatario", "catalogos.gestionar"),
]


def permisos_por_area(area, rol="usuario"):
    area = (area or "").strip().lower()
    rol = (rol or "usuario").strip().lower()

    if rol == "admin":
        permisos = set()
        for permisos_area in PERMISOS_MODULOS.values():
            permisos.update(permisos_area.keys())
        return permisos

    if rol == "visita":
        return PERMISOS_LECTURA if area == "mensajeria" else set(PERMISOS_MODULOS.get(area, {}).keys())

    if area == "mensajeria" and rol == "usuario":
        return set(PERMISOS_USUARIO_MENSAJERIA)

    if area == "mensajeria" and rol == "supervisor":
        return set(PERMISOS_MODULOS["mensajeria"].keys())

    return set(PERMISOS_MODULOS.get(area, {}).keys())


def usuario_puede(area, rol, permiso):
    return permiso in permisos_por_area(area, rol)


def permiso_para_ruta(path, metodo="GET"):
    metodo = (metodo or "GET").upper()

    if path.startswith("/reportes/") and path != "/reportes":
        if metodo == "GET" and path.endswith("/pdf"):
            return "reportes.ver"
        return "reportes.gestionar"

    if path.startswith("/catalogos/") and metodo != "GET":
        return "catalogos.gestionar"

    for prefijo, permiso in RUTAS_PERMISOS:
        if path == prefijo or path.startswith(f"{prefijo}/"):
            return permiso
    return None


def matriz_permisos(area_actual="", rol_actual="usuario"):
    permisos_actuales = permisos_por_area(area_actual, rol_actual)
    matriz = []
    for area, permisos in PERMISOS_MODULOS.items():
        matriz.append(
            {
                "area": area,
                "permisos": [
                    {
                        "codigo": codigo,
                        "nombre": nombre,
                        "activo": codigo in permisos_actuales,
                    }
                    for codigo, nombre in permisos.items()
                ],
            }
        )
    return matriz

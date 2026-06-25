NOVEDADES_PORTAL = [
    {
        "version": "Actualizacion mayor",
        "fecha": "25/06/2026",
        "titulo": "Portal mas seguro, visual y trazable",
        "descripcion": (
            "Se consolido una version mayor con nuevo inicio ejecutivo, "
            "administracion de usuarios, permisos por rol y reportes mas completos."
        ),
        "cambios": [
            {
                "titulo": "Nuevo diseno operativo",
                "detalle": "Inicio, menu lateral, hero, metricas y graficos con estilo ejecutivo.",
                "tipo": "pantalla",
            },
            {
                "titulo": "Administracion interna",
                "detalle": "Usuarios, areas, roles, recuperacion de clave, bloqueos y auditoria.",
                "tipo": "seguridad",
            },
            {
                "titulo": "Reportes reforzados",
                "detalle": "Casos por OF con movimientos, evidencia, PDF, cierre, anulacion y eliminacion respaldada.",
                "tipo": "historico",
            },
            {
                "titulo": "Trazabilidad sensible",
                "detalle": "Respaldos, eliminaciones y anulaciones muestran responsable, fecha y motivo.",
                "tipo": "seguridad",
            },
            {
                "titulo": "Permisos por rol",
                "detalle": "Visita, usuario, supervisor y administrador con accesos separados por area.",
                "tipo": "control",
            },
        ],
    },
    {
        "version": "Actualizacion operativa",
        "fecha": "16/06/2026",
        "titulo": "Mensajeria mas estable y completa",
        "descripcion": (
            "Se reforzo el flujo completo de Starken, avisos, historico y "
            "operacion cloud para que el trabajo diario sea mas claro y seguro."
        ),
        "cambios": [
            {
                "titulo": "Pantalla de exito OF",
                "detalle": "Rango de ordenes disponible para imprimir etiquetas.",
                "tipo": "pantalla",
            },
            {
                "titulo": "Avisos por correo",
                "detalle": "Funcionarios y destinatarios reciben mensajes con diseno formal.",
                "tipo": "correo",
            },
            {
                "titulo": "Historico reforzado",
                "detalle": "Anulacion de OF, eliminacion respaldada y mejores filtros.",
                "tipo": "historico",
            },
            {
                "titulo": "Telefonos mas simples",
                "detalle": "Formatos con +56, espacios o simbolos se normalizan solos.",
                "tipo": "telefono",
            },
            {
                "titulo": "Sesion y control",
                "detalle": "Cierre por inactividad y pruebas tecnicas de seguridad.",
                "tipo": "seguridad",
            },
        ],
    }
]


def obtener_novedades_portal():
    return NOVEDADES_PORTAL

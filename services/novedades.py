NOVEDADES_PORTAL = [
    {
        "version": "Actualización operativa",
        "fecha": "16/06/2026",
        "titulo": "Mensajería más estable y completa",
        "descripcion": (
            "Se reforzó el flujo completo de Starken, avisos, histórico y "
            "operación cloud para que el trabajo diario sea más claro y seguro."
        ),
        "cambios": [
            {
                "titulo": "Pantalla de éxito OF",
                "detalle": "Rango de órdenes disponible para imprimir etiquetas.",
                "tipo": "pantalla",
            },
            {
                "titulo": "Avisos por correo",
                "detalle": "Funcionarios y destinatarios reciben mensajes con diseño formal.",
                "tipo": "correo",
            },
            {
                "titulo": "Histórico reforzado",
                "detalle": "Anulación de OF, eliminación respaldada y mejores filtros.",
                "tipo": "historico",
            },
            {
                "titulo": "Teléfonos más simples",
                "detalle": "Formatos con +56, espacios o símbolos se normalizan solos.",
                "tipo": "telefono",
            },
            {
                "titulo": "Sesión y control",
                "detalle": "Cierre por inactividad y pruebas técnicas de seguridad.",
                "tipo": "seguridad",
            },
        ],
    }
]


def obtener_novedades_portal():
    return NOVEDADES_PORTAL

import secrets
import string

from database.modelos import SolicitudRecuperacionClave
from utils.fechas import ahora_chile
from utils.texto import normalizar_texto_operativo


ESTADOS_RECUPERACION = {"pendiente", "revisada", "resuelta", "rechazada"}


def enmascarar_correo(correo):
    correo = (correo or "").strip().lower()
    if "@" not in correo:
        return correo[:2] + "***" if correo else ""

    nombre, dominio = correo.split("@", 1)
    visible = nombre[:2] if len(nombre) > 2 else nombre[:1]
    return f"{visible}***@{dominio}"


def crear_solicitud_recuperacion(db, usuario, correo="", ip="", rut=""):
    usuario = normalizar_texto_operativo(usuario or "", upper=False).strip().lower()
    correo = (correo or "").strip().lower()
    rut = (rut or "").strip().upper()
    if not usuario:
        raise ValueError("El usuario es obligatorio.")
    if not rut:
        raise ValueError("El RUT es obligatorio.")

    solicitud = SolicitudRecuperacionClave(
        sr_usuario=usuario,
        sr_correo=correo,
        sr_correo_enmascarado=enmascarar_correo(correo),
        sr_rut=rut,
        sr_ip=(ip or "").strip()[:80],
        sr_estado="pendiente",
    )
    db.add(solicitud)
    return solicitud


def listar_solicitudes_recuperacion(db, limite=20, estado=""):
    try:
        limite = int(limite or 20)
    except (TypeError, ValueError):
        limite = 20
    limite = min(max(limite, 5), 80)

    query = db.query(SolicitudRecuperacionClave)
    estado = (estado or "").strip().lower()
    if estado in ESTADOS_RECUPERACION:
        query = query.filter(SolicitudRecuperacionClave.sr_estado == estado)

    return (
        query.order_by(
            SolicitudRecuperacionClave.sr_fecha_creacion.desc(),
            SolicitudRecuperacionClave.id.desc(),
        )
        .limit(limite)
        .all()
    )


def contar_solicitudes_pendientes(db):
    return (
        db.query(SolicitudRecuperacionClave)
        .filter(SolicitudRecuperacionClave.sr_estado == "pendiente")
        .count()
    )


def marcar_solicitud_revisada(solicitud, usuario_admin, nota=""):
    solicitud.sr_estado = "revisada"
    solicitud.sr_fecha_revision = ahora_chile()
    solicitud.sr_revisado_por = (usuario_admin or "admin")[:120]
    solicitud.sr_nota = (nota or "").strip()[:1000]
    return solicitud


def resolver_solicitud_con_clave(solicitud, usuario_admin, nota=""):
    solicitud.sr_estado = "resuelta"
    solicitud.sr_fecha_revision = ahora_chile()
    solicitud.sr_revisado_por = (usuario_admin or "admin")[:120]
    solicitud.sr_nota = (nota or "").strip()[:1000]
    solicitud.sr_clave_temporal_generada = True
    return solicitud


def rechazar_solicitud(solicitud, usuario_admin):
    solicitud.sr_estado = "rechazada"
    solicitud.sr_fecha_revision = ahora_chile()
    solicitud.sr_revisado_por = (usuario_admin or "admin")[:120]
    solicitud.sr_nota = "Solicitud rechazada por administrador."
    return solicitud


def generar_clave_temporal(longitud=10):
    longitud = max(8, min(int(longitud or 10), 20))
    alfabeto = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))

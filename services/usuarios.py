from werkzeug.security import generate_password_hash

from database.modelos import UsuarioSistema
from utils.fechas import ahora_chile


def obtener_usuario_por_nombre(db, usuario):
    usuario = (usuario or "").strip().lower()
    if not usuario:
        return None
    return db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario).first()


def cambiar_clave_propia(usuario_sistema, clave):
    if not clave or len(clave) < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres.")

    usuario_sistema.u_clave_hash = generate_password_hash(clave)
    usuario_sistema.u_debe_cambiar_clave = False
    usuario_sistema.u_fecha_actualizacion = ahora_chile()
    return usuario_sistema

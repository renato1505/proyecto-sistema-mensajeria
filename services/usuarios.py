import re

from werkzeug.security import generate_password_hash

from database.modelos import AreaOperativa, UsuarioSistema
from utils.fechas import ahora_chile
from utils.texto import normalizar_nombre_operativo, normalizar_texto_operativo
from utils.validaciones import normalizar_rut_usuario


ROLES_USUARIO = ["visita", "usuario", "supervisor", "admin"]
AREAS_OPERATIVAS_BASE = {
    "administracion": "Administracion",
    "mensajeria": "Mensajeria",
    "recepcion": "Recepcion",
    "seguridad": "Seguridad",
}


def normalizar_codigo(valor):
    texto = normalizar_texto_operativo(valor or "", upper=False).strip().lower()
    texto = re.sub(r"[^a-z0-9_]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto


def listar_areas(db, solo_activas=False):
    query = db.query(AreaOperativa)
    if solo_activas:
        query = query.filter(AreaOperativa.ar_activa.is_(True))
    return query.order_by(AreaOperativa.ar_nombre.asc()).all()


def asegurar_areas_base(db):
    for codigo, nombre in AREAS_OPERATIVAS_BASE.items():
        asegurar_area(db, codigo, nombre)


def conteo_usuarios_por_area(db):
    conteo = {}
    for usuario in listar_usuarios(db):
        conteo[usuario.u_area] = conteo.get(usuario.u_area, 0) + 1
    return conteo


def listar_usuarios(db):
    return db.query(UsuarioSistema).order_by(UsuarioSistema.u_usuario.asc()).all()


def estadisticas_usuarios(db):
    usuarios = listar_usuarios(db)
    total = len(usuarios)
    activos = sum(1 for usuario in usuarios if usuario.u_activo)
    admins = sum(1 for usuario in usuarios if usuario.u_rol == "admin")
    areas = len({usuario.u_area for usuario in usuarios if usuario.u_area})
    return {
        "total": total,
        "activos": activos,
        "inactivos": total - activos,
        "admins": admins,
        "areas": areas,
    }


def contar_admins_activos(db, excluir_usuario_id=None):
    query = db.query(UsuarioSistema).filter(
        UsuarioSistema.u_rol == "admin",
        UsuarioSistema.u_activo.is_(True),
    )
    if excluir_usuario_id:
        query = query.filter(UsuarioSistema.id != excluir_usuario_id)
    return query.count()


def es_ultimo_admin_activo(db, usuario_sistema):
    if not usuario_sistema or usuario_sistema.u_rol != "admin" or not usuario_sistema.u_activo:
        return False
    return contar_admins_activos(db, excluir_usuario_id=usuario_sistema.id) == 0


def salud_usuario(usuario_sistema, bloqueo=None):
    etiquetas = []
    nivel = "ok"
    bloqueo = bloqueo or {}

    if not usuario_sistema.u_activo:
        etiquetas.append({"texto": "Inactivo", "nivel": "danger"})
        nivel = "danger"
    if bloqueo.get("bloqueado"):
        etiquetas.append({"texto": "Acceso bloqueado", "nivel": "danger"})
        nivel = "danger"
    elif bloqueo.get("intentos"):
        etiquetas.append({"texto": f"{bloqueo.get('intentos')} intento(s) fallidos", "nivel": "warning"})
        if nivel != "danger":
            nivel = "warning"
    if usuario_sistema.u_debe_cambiar_clave:
        etiquetas.append({"texto": "Clave temporal", "nivel": "warning"})
        if nivel != "danger":
            nivel = "warning"
    if not usuario_sistema.u_ultimo_acceso:
        etiquetas.append({"texto": "Sin ultimo acceso", "nivel": "info"})
        if nivel == "ok":
            nivel = "info"
    if usuario_sistema.u_rol == "admin":
        etiquetas.append({"texto": "Admin", "nivel": "admin"})

    if not etiquetas:
        etiquetas.append({"texto": "OK", "nivel": "ok"})

    return {
        "nivel": nivel,
        "etiquetas": etiquetas,
    }


def salud_usuarios(usuarios, bloqueos=None):
    bloqueos = bloqueos or {}
    return {
        usuario.id: salud_usuario(usuario, bloqueos.get((usuario.u_usuario or "").strip().lower()))
        for usuario in usuarios
    }


def asegurar_area(db, codigo, nombre=None):
    codigo = normalizar_codigo(codigo)
    if not codigo:
        raise ValueError("El codigo de area es obligatorio.")

    area = db.query(AreaOperativa).filter(AreaOperativa.ar_codigo == codigo).first()
    if area:
        if nombre:
            area.ar_nombre = normalizar_nombre_operativo(nombre)
        return area

    area = AreaOperativa(
        ar_codigo=codigo,
        ar_nombre=normalizar_nombre_operativo(nombre or codigo.replace("_", " ")),
        ar_activa=True,
    )
    db.add(area)
    return area


def actualizar_area(area, nombre):
    nombre = normalizar_nombre_operativo(nombre or "")
    if not nombre:
        raise ValueError("El nombre del area es obligatorio.")

    area.ar_nombre = nombre
    return area


def eliminar_area(db, area):
    if area.ar_codigo in AREAS_OPERATIVAS_BASE:
        raise ValueError("Las areas base del portal no se pueden eliminar.")

    usados = db.query(UsuarioSistema).filter(UsuarioSistema.u_area == area.ar_codigo).count()
    if usados:
        raise ValueError("No se puede eliminar un area con usuarios asignados.")
    db.delete(area)


def crear_usuario(db, usuario, nombre, rut, clave, area, rol="usuario"):
    usuario = normalizar_codigo(usuario)
    nombre = normalizar_nombre_operativo(nombre or usuario)
    rut = normalizar_rut_usuario(rut)
    area = normalizar_codigo(area)
    rol = normalizar_codigo(rol) if normalizar_codigo(rol) in ROLES_USUARIO else "usuario"

    if not usuario:
        raise ValueError("El usuario es obligatorio.")
    if not rut:
        raise ValueError("El RUT del usuario es obligatorio.")
    if not clave or len(clave) < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres.")
    if not area:
        raise ValueError("El area es obligatoria.")

    existente = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario).first()
    if existente:
        raise ValueError("Ya existe un usuario con ese nombre.")

    usuario_sistema = UsuarioSistema(
        u_usuario=usuario,
        u_nombre=nombre,
        u_rut=rut,
        u_clave_hash=generate_password_hash(clave),
        u_area=area,
        u_rol=rol,
        u_activo=True,
        u_debe_cambiar_clave=True,
        u_fecha_actualizacion=ahora_chile(),
    )
    db.add(usuario_sistema)
    return usuario_sistema


def actualizar_usuario(usuario_sistema, nombre, rut, area, rol="usuario"):
    nombre = normalizar_nombre_operativo(nombre or usuario_sistema.u_nombre)
    rut = normalizar_rut_usuario(rut)
    area = normalizar_codigo(area)
    rol = normalizar_codigo(rol) if normalizar_codigo(rol) in ROLES_USUARIO else "usuario"

    if not nombre:
        raise ValueError("El nombre es obligatorio.")
    if not rut:
        raise ValueError("El RUT del usuario es obligatorio.")
    if not area:
        raise ValueError("El area es obligatoria.")

    usuario_sistema.u_nombre = nombre
    usuario_sistema.u_rut = rut
    usuario_sistema.u_area = area
    usuario_sistema.u_rol = rol
    usuario_sistema.u_fecha_actualizacion = ahora_chile()
    return usuario_sistema


def cambiar_clave_usuario(usuario_sistema, clave):
    if not clave or len(clave) < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres.")

    usuario_sistema.u_clave_hash = generate_password_hash(clave)
    usuario_sistema.u_debe_cambiar_clave = True
    usuario_sistema.u_fecha_actualizacion = ahora_chile()
    return usuario_sistema


def cambiar_clave_propia(usuario_sistema, clave):
    if not clave or len(clave) < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres.")

    usuario_sistema.u_clave_hash = generate_password_hash(clave)
    usuario_sistema.u_debe_cambiar_clave = False
    usuario_sistema.u_fecha_actualizacion = ahora_chile()
    return usuario_sistema


def cambiar_estado_usuario(usuario_sistema):
    usuario_sistema.u_activo = not usuario_sistema.u_activo
    usuario_sistema.u_fecha_actualizacion = ahora_chile()
    return usuario_sistema

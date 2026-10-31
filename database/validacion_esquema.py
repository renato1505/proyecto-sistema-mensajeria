"""Validación de lectura contra un contrato versionado explícito.

No importa main, configuración, conexión global ni metadata mutable del ORM.
Compatible significa satisfacer este contrato, no una auditoría exhaustiva.
"""
from dataclasses import dataclass, replace
import re

from sqlalchemy import column, inspect, select, table

from database.contrato_esquema import (
    COLUMNAS_V2, UNICOS_V2, FKS_V2, INDICES_PARCIALES_V2, CHECKS_V2,
    REVISIONES_V2,
)


@dataclass(frozen=True)
class ContratoEsquema:
    nombre: str = "mensajeria-v2-20261025_06"
    revision_requerida: str | None = "20261025_06"
    revisiones_aceptadas: tuple = ("20261025_06",)
    revisiones_conocidas: tuple = REVISIONES_V2
    columnas: tuple = COLUMNAS_V2
    unicos: tuple = UNICOS_V2
    fks: tuple = FKS_V2
    indices_parciales: tuple = INDICES_PARCIALES_V2
    checks: tuple = CHECKS_V2
    fixture_sqlite: bool = False


CONTRATO_V2 = ContratoEsquema()


def contrato_fixture_sqlite():
    """Excepción explícita de fixture: estructura completa sin historial Alembic.

    No se selecciona por variables de entorno ni se admite sobre PostgreSQL.
    """
    return replace(CONTRATO_V2, nombre="fixture-sqlite-v2",
                   revision_requerida=None, revisiones_aceptadas=(),
                   fixture_sqlite=True)


@dataclass(frozen=True)
class HallazgoEsquema:
    codigo: str
    mensaje: str


@dataclass(frozen=True)
class ResultadoEsquema:
    estado: str
    contrato: str
    revisiones: tuple
    hallazgos: tuple

    @property
    def compatible(self):
        return self.estado == "COMPATIBLE"

    def como_dict(self):
        return {
            "estado": self.estado, "contrato": self.contrato,
            "revisiones": list(self.revisiones),
            "hallazgos": [{"codigo": h.codigo, "mensaje": h.mensaje} for h in self.hallazgos],
        }


def _expresion_simple(sql):
    """Reconoce solo los predicados pequeños del contrato.

    Los literales se conservan como tokens opacos (incluidos caso, espacios y
    comillas escapadas). No se intenta demostrar equivalencia SQL general.
    None significa expresión no reconocida y nunca equivale a otra expresión.
    """
    patron = re.compile(
        r"\s+|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
        r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|::|>=|[().,\[\]=]"
    )
    texto = str(sql)
    tokens = []
    posicion = 0
    while posicion < len(texto):
        match = patron.match(texto, posicion)
        if match is None:
            return None
        valor = match.group()
        posicion = match.end()
        if valor.isspace():
            continue
        if valor.startswith("'"):
            tokens.append(("literal", valor))
        elif valor.startswith('"'):
            tokens.append(("palabra", valor[1:-1].replace('""', '"')))
        elif valor[0].isalpha() or valor[0] == "_":
            tokens.append(("palabra", valor.lower()))
        elif valor.isdigit():
            tokens.append(("numero", valor))
        else:
            tokens.append(("simbolo", valor))

    # Paréntesis de reflexión y casts textuales limitados a las formas de estado
    # reconocidas abajo. No eliminar caracteres dentro de cadenas.
    simples = []
    pila = []
    casts = False
    indice = 0
    while indice < len(tokens):
        tipo, valor = tokens[indice]
        if tipo == "simbolo" and valor == "::":
            casts = True
            indice += 1
            if tokens[indice:indice + 2] == [("palabra", "character"), ("palabra", "varying")]:
                indice += 2
            elif tokens[indice:indice + 1] == [("palabra", "text")]:
                indice += 1
            else:
                return None
            if tokens[indice:indice + 2] == [("simbolo", "["), ("simbolo", "]")]:
                indice += 2
            continue
        if tipo == "simbolo" and valor in ("(", "["):
            pila.append(valor)
        elif tipo == "simbolo" and valor in (")", "]"):
            if not pila or pila.pop() != {")": "(", "]": "["}[valor]:
                return None
        if (tipo, valor) not in (("simbolo", "("), ("simbolo", ")")):
            simples.append((tipo, valor))
        indice += 1
    if pila:
        return None

    # Calificaciones exactas conocidas. Otros esquemas/identificadores requieren
    # revisión, en vez de borrar cualquier prefijo.
    if simples[:2] in (
        [("palabra", "intentos_of"), ("simbolo", ".")],
        [("palabra", "retiro_envios"), ("simbolo", ".")],
    ):
        simples = simples[2:]
    palabra = lambda valor: ("palabra", valor)
    simbolo = lambda valor: ("simbolo", valor)
    numero = lambda valor: ("numero", valor)

    if (len(simples) == 5
            and simples[:2] == [palabra("io_estado"), palabra("in")]
            and simples[2][0] == simples[4][0] == "literal"
            and simples[3] == simbolo(",")):
        return ("estados", simples[2][1], simples[4][1])
    if (len(simples) == 9
            and simples[:5] == [palabra("io_estado"), simbolo("="), palabra("any"),
                               palabra("array"), simbolo("[")]
            and simples[5][0] == simples[7][0] == "literal"
            and simples[6] == simbolo(",") and simples[8] == simbolo("]")):
        return ("estados", simples[5][1], simples[7][1])
    if casts:
        return None
    if simples in (
        [palabra("re_vigente"), palabra("is"), palabra("true")],
        [palabra("re_vigente"), palabra("is"), numero("1")],
        [palabra("re_vigente"), simbolo("="), numero("1")],
    ):
        return ("retiro_vigente",)
    if (len(simples) == 3
            and simples[0] in [palabra(c) for c in (
                "re_bultos_snapshot", "io_secuencia", "av_intentos")]
            and simples[1] == simbolo(">=")
            and simples[2] == numero("0" if simples[0] == palabra("av_intentos") else "1")):
        return tuple(simples)
    return None


def _expresiones_equivalentes(primera, segunda):
    reconocida = _expresion_simple(primera)
    return reconocida is not None and reconocida == _expresion_simple(segunda)


def _revision(conexion, inspector, tablas, contrato, agregar):
    if "alembic_version" not in tablas:
        if contrato.revision_requerida is not None:
            agregar("REVISION_AUSENTE", "No existe el registro de revisión Alembic.")
        return ()
    if "version_num" not in {c["name"] for c in inspector.get_columns("alembic_version")}:
        agregar("REVISION_MANUAL", "El registro Alembic tiene una estructura inesperada.")
        return ()
    valores = tuple(conexion.execute(select(column("version_num")).select_from(table("alembic_version"))).scalars())
    # No reflejar texto desconocido de la base en mensajes/resultados (podría ser
    # información sensible o contenido accidental).
    conocidas = tuple(v for v in valores if v in contrato.revisiones_conocidas)
    if len(valores) != 1:
        agregar("REVISION_MANUAL", "El registro Alembic debe contener una sola revisión.")
    elif valores[0] not in contrato.revisiones_conocidas:
        agregar("REVISION_MANUAL", "La revisión no está reconocida por este contrato.")
    elif contrato.revision_requerida is not None and valores[0] not in contrato.revisiones_aceptadas:
        requerida = contrato.revisiones_conocidas.index(contrato.revision_requerida)
        if contrato.revisiones_conocidas.index(valores[0]) < requerida:
            agregar("REVISION_INSUFICIENTE", "La revisión es anterior a la requerida por esta aplicación.")
        else:
            agregar("REVISION_MANUAL", "La revisión no está autorizada para esta versión de aplicación.")
    return conocidas


def _restricciones(inspector, disponibles, contrato, agregar):
    for nombre, columnas in contrato.unicos:
        if nombre not in disponibles:
            continue
        candidatos = inspector.get_unique_constraints(nombre) + [
            i for i in inspector.get_indexes(nombre)
            if i.get("unique") and not any(
                clave.endswith("_where") and valor is not None
                for clave, valor in i.get("dialect_options", {}).items()
            )
        ]
        if not any(tuple(c.get("column_names", ())) == columnas for c in candidatos):
            agregar("REVISION_MANUAL", f"Falta una unicidad esencial en {nombre}: {', '.join(columnas)}.")
    for nombre, columnas, destino, referidas in contrato.fks:
        if nombre not in disponibles or destino not in disponibles:
            continue
        if not any(
            tuple(f.get("constrained_columns", ())) == columnas
            and f.get("referred_table") == destino
            and f.get("referred_schema") in (None, inspector.default_schema_name)
            and tuple(f.get("referred_columns", ())) == referidas
            and (f.get("options", {}).get("ondelete") or "").upper() == "RESTRICT"
            for f in inspector.get_foreign_keys(nombre)
        ):
            agregar("REVISION_MANUAL", f"Falta una relación protegida de {nombre} a {destino}.")
    for nombre, indice, columnas, expresiones in contrato.indices_parciales:
        if nombre not in disponibles:
            continue
        candidato = next((i for i in inspector.get_indexes(nombre) if i["name"] == indice), None)
        opciones = candidato.get("dialect_options", {}) if candidato else {}
        predicados = [v for k, v in opciones.items() if k.endswith("_where") and v is not None]
        if not (candidato and candidato.get("unique")
                and tuple(candidato.get("column_names", ())) == columnas
                and len(predicados) == 1
                and any(_expresiones_equivalentes(predicados[0], e) for e in expresiones)):
            agregar("REVISION_MANUAL", f"Índice parcial esencial ausente o diferente: {indice}.")
    for nombre, identificador, expresion in contrato.checks:
        if nombre in disponibles and not any(
            c.get("name") == identificador
            and _expresiones_equivalentes(c.get("sqltext", ""), expresion)
            for c in inspector.get_check_constraints(nombre)
        ):
            agregar("REVISION_MANUAL", f"Restricción esencial ausente o diferente: {identificador}.")


def _referencias(conexion, disponibles, agregar):
    if "puntos_retiro" not in disponibles:
        return
    puntos = table("puntos_retiro", column("pr_codigo"), column("pr_activo"),
                   column("pr_es_local"), column("pr_incluir_metricas_locales"))
    for codigo, local in (("MENSAJERIA_LOCAL", True), ("ACADEMIA", False)):
        filas = conexion.execute(select(puntos).where(puntos.c.pr_codigo == codigo)).mappings().all()
        if not filas:
            agregar("REFERENCIAS_INCOMPLETAS", f"Falta el punto de retiro obligatorio {codigo}.")
        elif len(filas) != 1:
            agregar("REVISION_MANUAL", f"El punto de retiro {codigo} no es único.")
        elif filas[0]["pr_activo"] in (False, 0):
            agregar("REFERENCIAS_INCOMPLETAS", f"El punto de retiro {codigo} está inactivo.")
        elif filas[0]["pr_activo"] not in (True, 1):
            agregar("REVISION_MANUAL", f"El estado activo de {codigo} requiere revisión.")
        elif (filas[0]["pr_es_local"] != local or filas[0]["pr_incluir_metricas_locales"] != local):
            agregar("REVISION_MANUAL", f"La clasificación logística de {codigo} requiere revisión.")


def validar_esquema(engine, contrato=CONTRATO_V2):
    """Inspecciona un Engine con conexión propia y rollback, sin reparaciones.

    Solo SQLite/PostgreSQL. PostgreSQL usa una transacción READ ONLY. No altera
    transacciones de un llamador ni propaga texto de excepciones del driver.
    No valida todos los tipos, defaults, CHECK ni datos operativos.
    """
    hallazgos = []
    revisiones = ()

    def agregar(codigo, mensaje):
        hallazgos.append(HallazgoEsquema(codigo, mensaje))

    try:
        dialecto = engine.dialect.name
        if dialecto not in {"sqlite", "postgresql"} or (contrato.fixture_sqlite and dialecto != "sqlite"):
            raise ValueError("Dialect not supported")
        if contrato.revision_requerida is None and not contrato.fixture_sqlite:
            raise ValueError("An explicit fixture contract is required")
        if contrato.revision_requerida is not None:
            if (contrato.revision_requerida not in contrato.revisiones_conocidas
                    or not contrato.revisiones_aceptadas
                    or any(r not in contrato.revisiones_conocidas for r in contrato.revisiones_aceptadas)):
                raise ValueError("Invalid revision policy")
            if any(contrato.revisiones_conocidas.index(r) < contrato.revisiones_conocidas.index(contrato.revision_requerida)
                   for r in contrato.revisiones_aceptadas):
                raise ValueError("Invalid revision policy")
        with engine.connect() as conexion:
            transaccion = conexion.begin()
            try:
                if dialecto == "postgresql":
                    conexion.exec_driver_sql("SET TRANSACTION READ ONLY")
                inspector = inspect(conexion)
                tablas = set(inspector.get_table_names())
                revisiones = _revision(conexion, inspector, tablas, contrato, agregar)
                completas = set()
                for nombre, columnas in contrato.columnas:
                    if nombre not in tablas:
                        agregar("ESTRUCTURA_INCOMPLETA", f"Falta la tabla indispensable {nombre}.")
                        continue
                    existentes = {c["name"] for c in inspector.get_columns(nombre)}
                    faltantes = set(columnas) - existentes
                    if faltantes:
                        agregar("ESTRUCTURA_INCOMPLETA",
                                f"Faltan columnas en {nombre}: {', '.join(sorted(faltantes))}.")
                    else:
                        completas.add(nombre)
                _restricciones(inspector, completas, contrato, agregar)
                _referencias(conexion, completas, agregar)
            finally:
                transaccion.rollback()
    except Exception:
        agregar("REVISION_MANUAL", "No se pudo verificar el esquema. Revisar conexión, permisos y estructura sin reparación automática.")

    # La ausencia de estructura/revisión conserva su diagnóstico incluso si
    # faltan otras garantías. Todos los hallazgos permanecen en el resultado.
    prioridad = ("REVISION_AUSENTE", "REVISION_INSUFICIENTE",
                 "ESTRUCTURA_INCOMPLETA", "REVISION_MANUAL", "REFERENCIAS_INCOMPLETAS")
    codigos = {h.codigo for h in hallazgos}
    estado = next((c for c in prioridad if c in codigos), "COMPATIBLE")
    return ResultadoEsquema(estado, contrato.nombre, revisiones, tuple(hallazgos))

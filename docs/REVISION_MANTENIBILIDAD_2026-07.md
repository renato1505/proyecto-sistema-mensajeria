# Revision de mantenibilidad - Julio 2026

Fecha de revision: 2026-07-08.

Objetivo: dejar el proyecto preparado para migracion de PC y continuidad en otro chat sin perder contexto tecnico ni operativo.

## Resultado general

El proyecto esta en buen estado funcional. La version productiva ya cubre el flujo completo de Mensajeria y se encuentra desplegada en Render. La base tecnica es mantenible, aunque existen archivos grandes que conviene dividir de forma gradual.

El foco recomendado ya no es agregar muchas funciones nuevas, sino:

- documentar;
- estabilizar;
- mejorar pruebas;
- reducir archivos grandes;
- formalizar migraciones;
- fortalecer respaldos y trazabilidad.

## Limpieza aplicada en esta revision

- Se ordenaron imports de `main.py`.
- Se agregaron comentarios utiles en `main.py` para context processors e inicializacion.
- Se corrigieron comentarios de `database/modelos.py` para evitar problemas de codificacion.
- Se agrego advertencia de mantenimiento en `services/permisos.py` para proteger rutas nuevas.
- Se actualizo `README.md` para ejecutar toda la suite de tests, no solo una prueba aislada.
- Se enlazo la documentacion de traspaso desde `docs/CONTINUIDAD_PROYECTO.md`.
- Se actualizo `docs/DESPLIEGUE_CLOUD.md` para reflejar el formato vigente de usuarios con area y rol.
- Se creo `docs/TRASPASO_NUEVO_CHAT.md`.
- Se creo `docs/MIGRACION_PC.md`.

No se realizo commit.

## Checks ejecutados

```powershell
python -m compileall -q main.py config database routes services scripts tests
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
git diff --check
```

Resultado:

- compilacion OK;
- 31 tests unitarios OK;
- smoke check OK;
- diff check sin errores.

## Estado Git despues de la revision

Cambios esperados:

- `README.md`
- `database/modelos.py`
- `docs/CONTINUIDAD_PROYECTO.md`
- `docs/DESPLIEGUE_CLOUD.md`
- `docs/MIGRACION_PC.md`
- `docs/TRASPASO_NUEVO_CHAT.md`
- `docs/REVISION_MANTENIBILIDAD_2026-07.md`
- `main.py`
- `services/permisos.py`

No deben aparecer:

- `.env`;
- logs;
- respaldos;
- archivos Excel reales;
- `static/uploads`;
- `venv`;
- `__pycache__`.

## Evaluacion por capa

### Rutas

La separacion por dominio esta razonable:

- `envios`;
- `carga_masiva`;
- `starken_lotes`;
- `historico`;
- `reportes`;
- `avisos`;
- `catalogos`;
- `auth`;
- `admin`.

Riesgo pendiente:

- `routes/auth.py` concentra login, bloqueo, sesiones, recuperacion y carga de usuarios. Funciona, pero a futuro podria dividirse en:
  - `auth_login.py`;
  - `auth_recuperacion.py`;
  - `auth_seguridad.py`;
  - `auth_context.py`.

### Servicios

La capa de servicios esta bien aprovechada. Las reglas importantes no estan todas metidas en rutas.

Servicios clave:

- `services/of_processor.py`;
- `services/starken.py`;
- `services/historico.py`;
- `services/avisos.py`;
- `services/reportes.py`;
- `services/reportes_pdf.py`;
- `services/permisos.py`;
- `services/usuarios.py`;
- `services/auditoria.py`.

Riesgo pendiente:

- `services/carga_masiva.py` sigue grande. Si se agregan mas reglas, separar en:
  - plantilla;
  - lectura Excel;
  - validacion;
  - normalizacion;
  - conversion a envios.

### Templates

Admin y Reportes ya fueron separados en parciales, lo que es positivo.

Pendientes:

- `templates/historico.html` sigue grande y contiene logica visual + JS.
- `templates/catalogos.html` sigue grande y contiene formularios + modales + JS.

Recomendacion:

- extraer JS de Historico a `static/js/historico.js`;
- extraer JS de Catalogos a `static/js/catalogos.js`;
- evitar seguir agregando scripts inline.

### CSS

Existe una capa visual compartida (`portal_theme.css`) y estilos por modulo. Esto es correcto.

Riesgo:

- `global.css` sigue siendo muy grande.

Recomendacion:

- no meter nuevos estilos especificos en `global.css`;
- usar `portal_theme.css` para patrones globales nuevos;
- usar CSS local por pantalla para detalles puntuales.

### Seguridad

Puntos fuertes:

- login obligatorio configurable;
- roles y areas;
- permisos por ruta;
- CSRF global;
- bloqueo temporal por intentos;
- recuperacion por usuario + RUT;
- auditoria de acciones sensibles;
- claves con hash para usuarios en BD.

Pendientes:

- intentos/bloqueos viven en memoria; si Render reinicia, se pierden;
- no hay politica persistente de seguridad en BD;
- `APP_USERS` es respaldo de arranque, pero si un usuario existe en BD, la BD manda.

### Base de datos

La app crea tablas y asegura columnas con `database/schema.py`.

Esto permitio avanzar rapido, pero no reemplaza migraciones formales.

Pendiente recomendado:

- evaluar Alembic antes de seguir agregando columnas criticas.

### Correos

El sistema opera con Gmail SMTP/IMAP. Esta funcionando, pero es un punto sensible en cloud.

Pendiente recomendado:

- migrar a proveedor transaccional cuando el volumen o criticidad suba.

## Reglas para futuras mejoras

1. No agregar ruta sin permiso en `services/permisos.py`.
2. No borrar registros sensibles sin respaldo previo.
3. No crear nuevas fechas con `datetime.now()` directo; usar `utils/fechas.py`.
4. No escribir claves reales en docs.
5. No duplicar reglas de normalizacion en cada formulario.
6. No mezclar nuevos modulos con Mensajeria si no estan listos.
7. No hacer push sin tests.

## Roadmap tecnico recomendado

### Bloque 1: migracion y estabilidad

- Confirmar nuevo PC con `docs/MIGRACION_PC.md`.
- Correr QA completo.
- Confirmar Render sigue estable.
- Verificar que `.env` local no se suba.

### Bloque 2: orden de codigo

- Extraer JS de Historico.
- Extraer JS de Catalogos.
- Dividir `services/carga_masiva.py`.
- Agregar pruebas para CSV Starken y OF.

### Bloque 3: administracion avanzada

- Novedades administrables.
- Dashboard Admin.
- Centro de respaldos.
- Politicas de seguridad persistentes.

### Bloque 4: expansion

- Definir si Recepcion y Seguridad seran modulos reales.
- Crear permisos y menus propios por area.
- Evitar copiar estructura de Mensajeria sin necesidad.

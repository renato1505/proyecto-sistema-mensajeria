# Continuidad del Proyecto

Este documento resume el contexto operativo y tecnico actual del Portal Operativo para que otro desarrollador pueda continuar sin perder el hilo.

Para una migracion de PC o continuidad en otro chat, leer tambien:

- `docs/TRASPASO_NUEVO_CHAT.md`: contexto completo de historia, estado actual, reglas, arquitectura y roadmap.
- `docs/MIGRACION_PC.md`: pasos tecnicos para levantar el entorno en otro computador.
- `docs/QA_CHECKLIST.md`: pruebas manuales y tecnicas antes de deploy.

## Contexto General

El proyecto nacio como un sistema interno para automatizar el flujo de Mensajeria de L'Oreal. Antes se trabajaba con planillas manuales para Starken, copiando datos, generando CSV, esperando ordenes de flete, registrando OF y avisando manualmente a cada funcionario.

El sistema actual centraliza ese flujo:

1. Registrar envios individuales.
2. Cargar envios masivos desde Excel.
3. Revisar pendientes antes de enviarlos a Starken.
4. Generar CSV Starken y elegir descargarlo o enviarlo por correo.
5. Cargar OF manualmente o desde correo.
6. Pasar registros correctos al historico.
7. Enviar respaldo interno a Mensajeria.
8. Mostrar pantalla de exito OF con rango primera/ultima OF.
9. Enviar avisos a funcionarios y destinatarios cuando corresponda.
10. Mantener historico con busqueda, exportacion, anulacion y eliminacion respaldada.

El sistema ya esta desplegado en Render bajo el concepto de Portal Operativo. El modulo real en uso es Mensajeria. La base de datos cloud ya fue creada y migrada. El coworker del usuario esta usando la version web, por lo que cualquier cambio debe probarse localmente antes de hacer push/deploy.

## Estado Actual

La app funciona localmente con Flask y PostgreSQL, y en cloud con Render + Postgres.

Rutas principales validadas por `tests/smoke_check.py`:

- `/`
- `/crear_envio`
- `/nuevo_envio`
- `/carga_masiva`
- `/catalogos`
- `/envios`
- `/en_proceso`
- `/historico`
- `/of_correo`
- `/reportes`
- `/admin`

La ruta/pestana `/estado_sistema` fue retirada porque no aportaba informacion operativa distinta al log o al estado observable del sistema.

El estilo visual oficial del portal es el aplicado en el inicio de Mensajeria: header lateral/topbar compacto, hero con imagen institucional, tarjetas blancas con borde suave, acentos dorados y paneles limpios. Las pantallas del modulo deben heredar esa linea desde `static/css/portal_theme.css` antes de agregar estilos locales nuevos.

Checks que deben correr antes de subir cambios:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
```

El checklist funcional completo esta en `docs/QA_CHECKLIST.md`.

## Estructura De Mantenibilidad

Durante la etapa de estabilizacion se empezaron a separar las pantallas mas grandes para reducir riesgo de mantenimiento.

### Capa Visual Compartida

`static/css/portal_theme.css` funciona como capa final comun del Portal Operativo. Su objetivo es unificar heroes, paneles, tablas, metricas, formularios, botones y modales sin duplicar reglas en cada pantalla.

Regla de mantenimiento:

- mantener en `portal_theme.css` solo patrones compartidos;
- dejar en cada CSS de pantalla solo detalles propios de esa vista;
- evitar agregar nuevas variantes de header o layout global en CSS locales.

### Administracion

`templates/admin.html` quedo como archivo orquestador. El contenido real se separo en:

- `templates/admin/_header_tabs.html`
- `templates/admin/_usuarios.html`
- `templates/admin/_seguridad.html`
- `templates/admin/_auditoria.html`
- `templates/admin/_modals.html`

Los estilos de Administracion se cargan desde `static/css/admin.css`, que ahora actua como indice:

- `static/css/admin/layout.css`
- `static/css/admin/usuarios.css`
- `static/css/admin/seguridad.css`
- `static/css/admin/auditoria.css`
- `static/css/admin/responsive.css`

La construccion de datos del panel Admin se movio a `services/admin_context.py`.

Las rutas de Admin quedaron separadas asi:

- `routes/admin.py`: panel principal y registro de submodulos.
- `routes/admin_usuarios.py`: usuarios y areas.
- `routes/admin_seguridad.py`: bloqueos, politica de acceso y recuperacion de clave.
- `routes/admin_auditoria.py`: exportacion de auditoria.
- `routes/admin_helpers.py`: helpers compartidos de acceso admin y confirmacion de usuario.

### Reportes

`templates/reportes.html` quedo como archivo orquestador. El contenido se separo en:

- `templates/reportes/_hero.html`
- `templates/reportes/_lista.html`
- `templates/reportes/_formulario.html`

El JavaScript inline de Reportes se movio a:

- `static/js/reportes.js`

Los estilos de Reportes se cargan desde `static/css/reportes.css`, que ahora actua como indice:

- `static/css/reportes/layout.css`
- `static/css/reportes/lista.css`
- `static/css/reportes/formularios.css`
- `static/css/reportes/modales-responsive.css`

Esta separacion no cambia comportamiento; solo deja el codigo listo para seguir creciendo sin concentrar toda la pantalla en un unico archivo gigante.

### Scripts Extraidos

Para reducir logica inline en templates se separaron scripts simples:

- `static/js/envios.js`: descarga AJAX del CSV Starken desde Pendientes.
- `static/js/en_proceso.js`: apertura/cierre del detalle de lote.
- `static/js/carga_masiva.js`: apertura/cierre del detalle de fila validada.

Los templates correspondientes solo cargan estos archivos desde `extra_js`.

Deuda tecnica pendiente:

- `templates/historico.html` aun concentra bastante JavaScript de seleccion, modales y autocompletado. Conviene moverlo a `static/js/historico.js` en una etapa dedicada.
- `templates/catalogos.html` aun concentra JavaScript de modales CRUD. Conviene moverlo a `static/js/catalogos.js` cuidando permisos de usuario visita.
- `templates/editar_envio.html` mantiene validaciones locales inline. Se puede extraer cuando se estabilice completamente el formulario.

### Selector De Envios

La opcion `Envios` del menu abre `/crear_envio`, una pantalla intermedia con dos flujos:

- envio manual (`/nuevo_envio`);
- envio masivo (`/carga_masiva`).

Esto reduce opciones visibles en el header y mantiene el menu mas limpio para futuras areas del portal.

### Backlog Visual Y Admin

Pendientes definidos por QA para una siguiente version controlada:

- crear novedades administrables desde `/admin`, en vez de mantenerlas fijas en `services/novedades.py`;
- crear inicio de Administracion con dashboards por area cuando existan Recepcion y Seguridad operativas;
- analizar un header exclusivo para administradores si el usuario admin debe navegar por varias areas;
- redisenar Historico con la nueva estetica del inicio y agregar campo persistente de usuario gestor del despacho;
- revisar si las anulaciones deben mostrarse en una bandeja propia o reporte de control.

Los puntos anteriores requieren cambios de modelo, permisos y QA funcional. No conviene mezclarlos con un deploy de estabilizacion.

## Cambios Recientes Importantes

### Campos nuevos en destinatarios/envios

Se agregaron campos opcionales:

- Correo destinatario.
- Observacion.

Estos deben verse y mantenerse en:

- Nuevo envio.
- Carga masiva.
- Edicion de envio.
- Catalogos.
- Pendientes.
- En proceso.
- Historico.
- Exportaciones Excel.
- Respaldos por correo.
- CSV Starken.

En el CSV de Starken la observacion debe ir en la columna `OBSERVACION_CLIENTE`, no en `OBSERVACION`.

La carga masiva debe aceptar encabezados equivalentes como `E-MAIL DESTI` para correo destinatario.

### Normalizacion de telefono

Se ajusto para aceptar telefonos pegados con formatos como:

- `+569 3190 5658`
- `+56 9 8508 9918`
- `56946554638`
- numeros con espacios o simbolos.

La normalizacion principal esta en `utils/validaciones.py` y tambien hay apoyo JS en los formularios.

### Normalizacion de OF y textos operativos

Se agrego `utils/texto.py` para centralizar:

- normalizacion de nombres;
- eliminacion de tildes en textos operativos;
- conversion de OF con sufijo `.0` a valor limpio;
- claves de comparacion para evitar duplicados por acento o mayusculas.

El arranque de la app ejecuta `services/normalizacion_operativa.py`, que limpia datos ya existentes en:

- `envios`;
- `remitentes`;
- `destinatarios`;
- `comunas`.

Reglas activas:

- remitentes y destinatarios: mayuscula inicial por palabra;
- OF: sin decimal de Excel;
- comunas, regiones, direcciones y observaciones: sin tildes para reducir duplicados funcionales.

### Historico

El historico ahora permite:

- Filtrar por estado OF: todos, vigentes, anulados.
- Anular seleccionados con motivo.
- Eliminar seleccionados con respaldo por correo.
- Eliminar filtrados con respaldo por correo.
- Descargar seleccionados.
- Exportar Excel.

La anulacion no elimina datos. Mantiene trazabilidad en el historico y genera respaldo Excel por correo antes de confirmar. El correo del sistema recibe el respaldo completo y cada remitente recibe solo sus propios registros anulados, evitando mezclar informacion entre funcionarios. El respaldo visible debe incluir responsable, motivo y fecha.

Eliminaciones de historico si deben enviar respaldo Excel por correo a los destinatarios configurados. El correo debe indicar responsable, filtros aplicados y fecha de respaldo.

La eliminacion de reportes exige motivo, genera PDF de respaldo y envia correo antes de borrar el caso. El correo y la auditoria deben indicar el responsable que ejecuto la accion.

### Correos

El sistema sigue usando Gmail SMTP con clave de aplicacion como solucion actual. Se intento preparar proveedor externo, pero por ahora Gmail funciona y es lo que se esta usando.

Hay correos HTML diferenciados para:

- aviso al funcionario;
- aviso formal al destinatario;
- respaldo interno del lote a Mensajeria;
- respaldo de eliminacion de historico.
- respaldo de anulacion de historico;
- respaldo de eliminacion de reportes.

Los avisos a destinatario se envian solo si el envio tiene correo destinatario registrado.

Las plantillas HTML de correos estan centralizadas en `services/email_templates.py`. La logica de negocio queda en `services/avisos.py` y `services/historico.py`.

Render puede bloquear o volver inestable SMTP tradicional segun proveedor o configuracion. Si vuelve a fallar, la mejora recomendada es migrar envio transaccional a un proveedor tipo Brevo/SendGrid/Mailgun usando API o SMTP autorizado.

No escribir claves reales en documentacion ni respuestas.

### Zona horaria Chile

Se detecto que Render opera en UTC, lo que estaba causando fechas y horas corridas en correos, lotes y registros.

Se agrego `utils/fechas.py` con zona `America/Santiago`.

Usar estas funciones para fechas nuevas:

- `ahora_chile()`
- `fecha_hora_chile_texto()`
- `timestamp_archivo_chile()`
- `a_hora_chile()`
- `desde_timestamp_chile()`

No usar `datetime.utcnow()` ni `datetime.now()` directamente en logica operativa.

Importante: esto corrige registros futuros. No se hizo migracion masiva de fechas antiguas para evitar alterar datos reales sin control.

### Pantalla de exito OF

Al procesar OF con registros OK, el flujo redirige a `/of_exito/<lote>`.

La pantalla muestra:

- lote;
- total;
- OK;
- errores;
- primera OF;
- ultima OF.

La primera y ultima OF se copian al portapapeles al hacer clic. La tarjeta se puede cerrar con X y se autocierra a los 5 minutos.

### Header

El header fue ajustado y actualmente esta aceptado por el usuario. Se retiro la pestana `Estado` para liberar espacio. Las etiquetas del menu se compactaron sin cortar texto:

- `Nuevo`;
- `Masiva`;
- `Proceso`.

### Sesion

El login tiene cierre por inactividad configurable con `SESSION_TIMEOUT_MINUTES`.
En cada request autenticado se refresca la ultima actividad. Si se supera el limite, se limpia la sesion y se redirige al login.

El login acepta claves antiguas en texto plano para compatibilidad y tambien hashes de Werkzeug (`pbkdf2:` o `scrypt:`). Para generar un hash local:

```powershell
python scripts\generar_hash_clave.py
```

El valor generado puede usarse en `APP_USERS` en lugar de la clave en texto plano.

`APP_USERS` soporta tres formatos:

- Formato antiguo compatible: `usuario:clave`.
- Formato con area: `usuario|area|clave`.
- Formato recomendado con rol: `usuario|area|rol|clave`.

Ejemplo:

```env
APP_USERS=admin|admin|admin|clave-segura;fcespedes|mensajeria|usuario|clave-temporal
```

Cuando el usuario inicia sesion, la app guarda en sesion:

- `usuario_nombre`;
- `usuario_area`.
- `usuario_rol`.

El login actual funciona con usuario y clave:

1. Ingresar usuario.
2. Ingresar clave.

Reglas activas:

- El area se obtiene desde la configuracion del usuario.
- Un usuario normal ve el menu de su modulo asignado.
- Un usuario admin ve el apartado de Administracion.
- El menu de Mensajeria no aparece para usuarios de Administracion.
- Tras varios intentos fallidos, el acceso queda bloqueado temporalmente para esa combinacion usuario/IP.

Existe el apartado `/admin` para usuarios con rol `admin`. Desde ahi se pueden crear areas y usuarios en base de datos. `APP_USERS` queda como mecanismo de arranque/respaldo para no perder acceso si aun no hay usuarios creados en la base.

### Auditoria Base

Existe la tabla `auditoria` y el servicio `services/auditoria.py` para registrar acciones sensibles con usuario de sesion, accion, entidad, entidad_id, detalle y fecha.

Acciones que ya registran auditoria:

- anulacion de registros historicos;
- eliminacion de historico seleccionado;
- eliminacion de historico filtrado;
- creacion de reportes;
- edicion de reportes;
- cierre de reportes;
- carga de evidencia en reportes;
- movimientos de reportes;
- administracion de usuarios y areas;
- desbloqueo manual de intentos de login.

El apartado `/admin` ya incluye una vista de auditoria para consultar acciones recientes y filtrarlas por usuario, accion o entidad. Esta pantalla permite revisar cambios sensibles sin entrar directamente a la base de datos.

La auditoria puede exportarse a Excel desde `Admin > Auditoria`. La exportacion respeta filtros y queda registrada como `exportar_auditoria`.

### Administracion y Seguridad

El modulo de Administracion permite:

- crear usuarios;
- editar nombre, area y rol;
- cambiar claves temporales;
- activar/desactivar usuarios;
- eliminar usuarios;
- crear areas operativas;
- revisar auditoria reciente;
- revisar intentos fallidos del login;
- liberar bloqueos temporales de acceso.

La ficha de usuario muestra ultimo acceso y ultima IP registrada. La seccion Seguridad muestra una bitacora de accesos recientes basada en `auditoria`, con login exitoso, fallido y bloqueado.

Los permisos por modulo estan centralizados en `services/permisos.py`. Esta capa controla menu, rutas criticas y registra `permiso_denegado` cuando un usuario intenta entrar a una seccion no autorizada. El rol `admin` puede acceder a todos los permisos definidos; el area `mensajeria` opera el modulo completo de Mensajeria; `recepcion` y `seguridad` quedan reservadas para futuros modulos.

Las claves creadas o cambiadas por el administrador quedan como temporales. El usuario debe reemplazarlas en `/cambiar_clave` antes de continuar usando el portal. El cambio queda registrado como `cambiar_clave_propia` en auditoria.

Las tarjetas de usuarios muestran salud de acceso: OK, clave temporal, sin ultimo acceso, inactivo y admin. La pantalla de usuarios incluye busqueda/filtros por texto, area, rol y estado. Ademas, el backend impide eliminar, desactivar o quitar el rol al ultimo administrador activo, bloquea desactivarse a si mismo y exige confirmacion escrita para eliminar usuarios o tocar privilegios admin.

Las solicitudes `Olvide mi clave` ahora tienen gestion propia en la tabla `solicitudes_recuperacion_clave`, ademas del evento de auditoria `solicitud_recuperacion`.

Admin > Seguridad permite:

- ver solicitudes pendientes, revisadas y resueltas;
- agregar nota interna;
- marcar una solicitud como revisada;
- generar una clave temporal desde la solicitud.

La clave temporal se muestra solo en la alerta inmediata del portal y no se guarda en auditoria. El usuario queda con `u_debe_cambiar_clave=True`, por lo que debe reemplazarla al ingresar.

Admin > Seguridad tambien muestra el contador de solicitudes pendientes.

El bloqueo por intentos fallidos se mantiene en memoria del servidor. Eso significa que protege durante la ejecucion actual del servicio, pero se limpia si Render reinicia el proceso. Para una etapa posterior conviene persistir estos bloqueos en base de datos si se requiere control mas formal.

### Pruebas unitarias

`tests/test_email_client_unit.py` cubre:

- payload/proveedor de correo;
- seguridad de redireccion login;
- armado basico de correos;
- primer nombre en avisos;
- cancelacion de avisos pendientes;
- plantilla de destinatario sin exponer RUT;
- normalizacion de telefonos copiados.
- normalizacion de OF con `.0`;
- normalizacion de nombres operativos.

## Precauciones de Desarrollo

- No hacer commit ni push sin que el usuario lo pida.
- La app cloud esta siendo usada en produccion informal por el coworker del usuario.
- Probar siempre en local antes de deploy.
- No modificar `.env.example` con valores reales.
- No mostrar ni copiar secretos del `.env`.
- No eliminar ni revertir cambios del usuario.
- No tocar datos reales de historico sin respaldo.
- No hacer migraciones destructivas sin confirmacion.

## Servidor Local

Para levantar local:

```powershell
python main.py
```

URL:

```text
http://127.0.0.1:5000/
```

Si los cambios visuales no aparecen, pedir `Ctrl + F5` por cache del navegador.

## Proximos Pasos Recomendados

1. Hacer revision estricta de calidad/mantenibilidad.
2. Mantener documentacion final de uso actualizada.
3. Revisar tema de correo transaccional estable para cloud.
4. Evaluar pantalla de ayuda y mantenimiento.
5. Revisar seguridad avanzada: usuarios, permisos futuros por modulo y auditoria.
6. Planificar expansion a otros modulos del Portal Operativo, como Recepcion o Seguridad.

## Nota de Calidad

El sistema ya aporta valor real porque reduce trabajo manual, errores de digitacion, perdida de OF y falta de trazabilidad. La prioridad ya no es "hacer que funcione", sino estabilizarlo como herramienta operativa:

- fechas correctas;
- correos confiables;
- UI consistente;
- trazabilidad;
- respaldos;
- codigo mantenible;
- documentacion clara.

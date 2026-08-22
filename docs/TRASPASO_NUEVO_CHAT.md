# Traspaso para nuevo chat o nuevo equipo

Este documento es el punto de partida recomendado si se continua el proyecto en otro chat, otro PC o con otra persona. Resume contexto, decisiones, reglas de negocio, arquitectura, estilo visual, riesgos y forma de trabajo.

## 1. Resumen corto

El proyecto es un Portal Operativo interno creado inicialmente para automatizar el proceso de Mensajeria de L'Oreal. El modulo real y productivo actual es Mensajeria. La app reemplaza un flujo manual con planillas Excel, correos y copia manual de ordenes de flete Starken.

Actualmente permite:

- registrar envios manuales;
- cargar envios masivos desde Excel;
- revisar pendientes;
- generar CSV Starken;
- cargar respuestas OF manualmente o desde correo;
- pasar envios correctos al historico;
- avisar por correo a funcionarios y destinatarios;
- anular OF sin borrar historico;
- eliminar historico solo con respaldo por correo;
- crear reportes/excepciones de casos Starken;
- adjuntar evidencia;
- generar PDF de reporte;
- administrar usuarios, areas, roles, recuperacion de clave, bloqueos y auditoria.

La aplicacion ya esta desplegada y en uso real en Render. Cualquier cambio debe probarse localmente antes de hacer push.

## 2. Historia operativa

Antes del sistema, el flujo era:

1. El funcionario enviaba un correo con datos del destinatario.
2. Mensajeria recibia la caja o producto.
3. Se revisaba embalaje.
4. Se llenaba una planilla Excel de Starken.
5. Se descargaba como CSV.
6. Se subia a la aplicacion de Starken.
7. Starken devolvia ordenes de flete.
8. Mensajeria copiaba OF manualmente.
9. Se imprimian etiquetas desde Starken.
10. Se pegaban etiquetas.
11. Starken retiraba.
12. Se avisaba manualmente al funcionario, uno por uno.

Problemas del flujo antiguo:

- mucha digitacion repetitiva;
- errores por copia/pegado;
- planilla poco mantenible;
- sin historico ordenado;
- sin respaldo confiable de OF;
- avisos manuales lentos;
- dificultad para buscar pedidos antiguos;
- sin trazabilidad de anulaciones o eliminaciones.

El sistema se creo para reducir esos puntos de error sin sobrecomplicar el uso diario.

## 3. Estado actual del producto

### Produccion

- Plataforma: Render.
- Base: PostgreSQL administrado.
- Runtime: Flask + Gunicorn.
- Repositorio: GitHub.
- El deploy normalmente ocurre despues de `git push` a `main`, segun configuracion de Render.

### Local

- Carpeta raiz del repo local: `sistema_mensajeria`.
- Ejecutar con:

```powershell
python main.py
```

- URL local:

```text
http://127.0.0.1:5000/
```

### Estado funcional

El modulo Mensajeria esta productivo. Las areas Recepcion y Seguridad existen como concepto futuro, pero no tienen flujos reales.

La seccion Admin existe y se usa para:

- crear usuarios;
- asignar area;
- asignar rol;
- cambiar claves temporales;
- activar/desactivar usuarios;
- revisar auditoria;
- revisar bloqueos;
- gestionar recuperaciones de clave.

## 4. Filosofia del proyecto

El objetivo no es crear una app generica para vender masivamente sin control. Es una herramienta interna, muy ajustada al flujo real de Mensajeria.

Principios:

- velocidad operativa antes que decoracion innecesaria;
- trazabilidad antes que borrar silenciosamente;
- respaldos antes de eliminar datos;
- normalizacion de datos para evitar duplicados;
- interfaz elegante, clara y corporativa;
- no pedir roles complejos si el proceso no los necesita;
- crecer por modulos: Mensajeria primero, luego Recepcion/Seguridad si corresponde.

## 5. Estilo visual oficial

El estilo visual aceptado actualmente es:

- estetica corporativa L'Oreal;
- fondo claro;
- tarjetas blancas suaves;
- bordes sutiles;
- acento dorado;
- tipografia limpia;
- hero visual con imagen institucional;
- sidebar/topbar compacto;
- iconos lineales;
- tablas limpias;
- modales en vez de formularios que muevan toda la pantalla;
- alertas flotantes, no empujar layout.

Archivos clave:

- `static/css/global.css`: base historica y componentes compartidos antiguos.
- `static/css/portal_theme.css`: capa visual comun mas nueva del Portal Operativo.
- `static/css/index.css`: inicio de Mensajeria.
- CSS por modulo: `historico.css`, `catalogos.css`, `reportes.css`, `admin.css`, etc.

Regla para futuros cambios visuales:

- no crear otro estilo paralelo;
- mantener acentos dorados y fondo claro;
- usar `portal_theme.css` para patrones compartidos;
- usar CSS local solo para detalles especificos de cada vista.

## 6. Flujo principal de Mensajeria

### 6.1 Envios

Ruta visual: `/crear_envio`

La opcion `Envios` abre una pantalla intermedia con dos opciones:

- envio manual: `/nuevo_envio`;
- envio masivo: `/carga_masiva`.

Esto se hizo para reducir opciones en el menu principal.

### 6.2 Envio manual

Ruta: `/nuevo_envio`

Datos principales:

- remitente;
- correo remitente;
- centro de costo;
- division;
- destinatario;
- RUT destinatario, puede ser `0`;
- direccion;
- comuna;
- region, se completa desde comuna cuando aplica;
- telefono con codigo pais;
- correo destinatario opcional;
- observacion opcional;
- tipo envio;
- bultos;
- kilos.

El telefono se normaliza para aceptar formatos con `+56`, espacios o simbolos.

### 6.3 Carga masiva

Ruta: `/carga_masiva`

Permite subir Excel con pedidos masivos. La idea es que un funcionario envie muchos pedidos sin copiar el remitente en cada fila.

Reglas:

- remitente comun;
- destinatarios por fila;
- correo destinatario opcional;
- observacion opcional;
- comuna puede determinar region;
- telefonos se normalizan;
- errores se revisan antes de confirmar.

La observacion para Starken debe mapear a `OBSERVACION_CLIENTE`.

### 6.4 Pendientes

Ruta: `/envios`

Los pedidos quedan en estado `pendiente`.

Acciones:

- revisar;
- editar;
- eliminar antes de generar CSV;
- generar CSV Starken.

### 6.5 Generar CSV Starken

Ruta de accion: `/generar_excel`

El sistema crea un lote y permite:

- descargar CSV;
- enviar CSV por correo.

Luego los envios pasan a `en_proceso`.

### 6.6 En proceso

Ruta: `/en_proceso`

Se agrupan envios por lote. Desde aqui se carga el archivo OF.

Opciones:

- subir OF manual;
- buscar OF en correo;
- cancelar lote.

El procesamiento OF valida que el archivo corresponda al lote. Si no coincide, bloquea.

### 6.7 Pantalla exito OF

Ruta: `/of_exito/<lote>`

Muestra:

- lote;
- total;
- OK;
- errores;
- primera OF;
- ultima OF.

La primera y ultima OF se copian al hacer clic. Esto ayuda a imprimir etiquetas en Starken por rango.

### 6.8 Avisos

Rutas:

- `/avisos`;
- `/avisos_lote/<lote>`;
- `/enviar_avisos_lote/<lote>`;
- `/cancelar_avisos_lote/<lote>`.

Los avisos no se envian automaticamente al funcionario apenas llega la OF, porque a veces Starken todavia no retira. Se dejan pendientes para gestion manual.

Cuando se envian:

- el funcionario recibe correo con Excel;
- el destinatario recibe correo formal si hay correo destinatario;
- el lote deja de aparecer como pendiente.

### 6.9 Historico

Ruta: `/historico`

Contiene envios cerrados con OF OK.

Permite:

- filtrar por mes;
- filtrar por OF;
- filtrar por remitente;
- filtrar por destinatario;
- filtrar por fechas;
- filtrar por vigente/anulada;
- descargar seleccionados;
- exportar filtrados;
- anular seleccionados;
- eliminar seleccionados o filtrados con respaldo.

Regla critica:

- anular no borra;
- eliminar exige clave y correo de respaldo previo;
- si el correo de respaldo falla, no se elimina.

### 6.10 Reportes y excepciones

Ruta: `/reportes`

Sirve para documentar problemas posteriores al despacho:

- robo/extravio;
- cambio de direccion;
- devolucion;
- excepcion de entrega;
- otro tipo de incidente con Starken.

Cada reporte se asocia a una OF historica.

Funciones:

- crear reporte;
- agregar movimientos;
- agregar evidencia;
- cerrar caso;
- registrar OF de retorno si aplica;
- anular reporte;
- eliminar reporte con respaldo PDF.

El PDF de reporte usa ReportLab y se genera desde `services/reportes_pdf.py`.

## 7. Normalizacion de datos

La normalizacion es una decision de negocio importante.

Objetivos:

- evitar duplicados por tildes;
- evitar duplicados por mayusculas/minusculas;
- limpiar OF con `.0`;
- limpiar telefonos pegados desde Excel/correos;
- reducir errores H2H de Starken.

Archivos:

- `utils/texto.py`;
- `utils/validaciones.py`;
- `services/normalizacion_operativa.py`.

Reglas actuales:

- nombres con primera letra por palabra;
- correos en minuscula;
- tildes eliminadas en textos operativos;
- OF sin `.0`;
- observaciones sin caracteres problematicos para H2H;
- direccion se conserva con mas libertad porque Starken la necesita legible.

## 8. Seguridad y usuarios

### 8.1 Login

Archivo: `routes/auth.py`

El login se activa con:

```text
LOGIN_REQUIRED=1
```

Usuarios pueden venir desde:

1. Base de datos `usuarios_sistema`.
2. Variable `APP_USERS` como respaldo si no existen en BD.
3. `APP_ACCESS_PASSWORD` como legado si no hay usuarios.

Nota importante:

- Si un usuario existe en BD, esa credencial tiene prioridad sobre `APP_USERS`.
- Si hay problemas de acceso admin en cloud, revisar usuario admin en BD y variable `APP_USERS` de Render.

### 8.2 Roles

Roles actuales:

- `visita`: solo lectura;
- `usuario`: uso operativo diario sin acciones criticas;
- `supervisor`: acceso completo al modulo Mensajeria;
- `admin`: administracion completa.

### 8.3 Areas

Areas base:

- `administracion`;
- `mensajeria`;
- `recepcion`;
- `seguridad`.

Solo Mensajeria tiene flujo real. Las otras areas son preparacion para futuro.

### 8.4 Permisos

Archivo: `services/permisos.py`

Controla:

- menu visible;
- rutas protegidas;
- registro de permiso denegado.

Si se agrega una ruta nueva, revisar `RUTAS_PERMISOS`.

### 8.5 Recuperacion de clave

El usuario solicita recuperacion desde login usando:

- usuario;
- RUT.

Admin revisa en `Admin > Seguridad` y puede:

- rechazar;
- generar clave temporal.

La clave temporal se muestra una vez y luego solo queda hash en BD.

## 9. Auditoria

Archivo: `services/auditoria.py`

Tabla: `auditoria`

Registra:

- usuario;
- accion;
- entidad;
- entidad_id;
- detalle;
- fecha Chile.

Ejemplos:

- login exitoso;
- login fallido;
- bloqueo login;
- crear usuario;
- editar usuario;
- cambiar clave;
- eliminar usuario;
- anular historico;
- eliminar historico;
- crear reporte;
- cerrar reporte;
- eliminar reporte;
- permiso denegado.

La auditoria se ve en Admin y se puede exportar.

## 10. Correos

Proveedor actual estable:

- Gmail SMTP con clave de aplicacion.

Proveedor alternativo preparado:

- Brevo API o SMTP, pero no esta como flujo principal.

Archivos:

- `services/email_client.py`: envio real segun proveedor.
- `services/email_templates.py`: HTML de correos.
- `services/avisos.py`: avisos y respaldo lote.
- `services/historico.py`: respaldos de historico/anulaciones.
- `services/reportes_respaldo.py`: respaldo de eliminacion de reporte.
- `services/correo_of.py`: lectura IMAP para OF desde correo.

Regla cloud:

- no depender de archivos locales para respaldo critico;
- respaldar por correo antes de eliminar;
- si el correo falla, no borrar.

## 11. Base de datos y modelos

Archivo: `database/modelos.py`

Modelos principales:

- `Envio`: tabla central de pedidos.
- `Remitente`: catalogo remitentes.
- `Destinatario`: catalogo destinatarios frecuentes.
- `Comuna`: comunas/regiones.
- `AreaOperativa`: areas del portal.
- `UsuarioSistema`: usuarios login.
- `ExcepcionEnvio`: reportes/casos.
- `MovimientoExcepcion`: linea de tiempo de reportes.
- `EvidenciaExcepcion`: archivos de evidencia.
- `RegistroAuditoria`: auditoria.
- `SolicitudRecuperacionClave`: recuperacion de clave.

Migraciones:

- No hay Alembic todavia.
- `database/schema.py` asegura columnas faltantes al iniciar.
- Esto fue practico para crecer rapido, pero a futuro conviene migraciones versionadas.

## 12. Estructura tecnica

### Rutas

- `routes/paginas.py`: inicio, pendientes, en proceso.
- `routes/envios.py`: envio manual y edicion.
- `routes/carga_masiva.py`: plantilla, carga, revalidacion, confirmacion.
- `routes/starken_lotes.py`: CSV, OF, correo OF, pantalla exito.
- `routes/historico.py`: historico, exportar, anular, eliminar.
- `routes/historico_ajax.py`: sugerencias historico.
- `routes/catalogos.py`: catalogos.
- `routes/catalogos_ajax.py`: autocompletado/guardado rapido.
- `routes/avisos.py`: avisos de correo.
- `routes/reportes.py`: reportes/excepciones.
- `routes/auth.py`: login, sesion, bloqueo, recuperacion.
- `routes/admin.py`: panel admin.
- `routes/admin_usuarios.py`: usuarios/areas.
- `routes/admin_seguridad.py`: seguridad/recuperacion.
- `routes/admin_auditoria.py`: exportacion auditoria.

### Servicios

- `services/starken.py`: formato CSV.
- `services/of_processor.py`: procesamiento OF.
- `services/lotes.py`: cruce lote/correo/archivo.
- `services/carga_masiva.py`: Excel masivo.
- `services/catalogos_operativos.py`: validaciones catalogos.
- `services/dashboard.py`: metricas inicio.
- `services/reportes.py`: reglas de reportes.
- `services/reportes_pdf.py`: PDF ReportLab.
- `services/usuarios.py`: usuarios/areas.
- `services/permisos.py`: permisos.
- `services/admin_context.py`: contexto admin.
- `services/novedades.py`: novedades fijas del portal.

## 13. Archivos grandes y deuda tecnica

Archivos mas grandes al momento del traspaso:

- `static/css/global.css`;
- `static/css/historico.css`;
- `static/css/index.css`;
- `templates/historico.html`;
- `templates/catalogos.html`;
- `services/carga_masiva.py`;
- `routes/reportes.py`;
- `routes/auth.py`;
- `static/js/nuevo_envio.js`.

No son necesariamente errores, pero son candidatos a dividir si se siguen modificando.

Deuda recomendada:

1. Extraer JavaScript de `templates/historico.html` a `static/js/historico.js`.
2. Extraer JavaScript de `templates/catalogos.html` a `static/js/catalogos.js`.
3. Dividir `services/carga_masiva.py` en lectura, validacion y plantilla si sigue creciendo.
4. Persistir intentos/bloqueos de login en BD.
5. Crear migraciones con Alembic cuando el modelo se estabilice.
6. Hacer novedades administrables desde Admin.
7. Crear panel de respaldos/auditoria critica.
8. Mejorar pruebas unitarias de OF, CSV y avisos.

## 14. QA obligatorio antes de push

Siempre correr:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
```

Pruebas manuales minimas:

1. Login admin.
2. Login usuario mensajeria.
3. Crear envio manual.
4. Carga masiva pequena.
5. Generar CSV.
6. Procesar OF de prueba.
7. Revisar pantalla exito.
8. Revisar historico.
9. Anular registro de prueba.
10. Crear reporte de prueba.
11. Agregar evidencia.
12. Generar PDF.
13. Revisar Admin > Auditoria.

No hacer push si:

- falla correo de respaldo en eliminacion;
- se corta menu en desktop;
- usuario visita puede ejecutar acciones;
- OF queda con `.0`;
- hora no corresponde a Chile;
- `.env`, logs o respaldos aparecen en `git status`.

## 15. Migracion a otro PC

Pasos recomendados:

1. Instalar Python compatible.
2. Instalar PostgreSQL o tener acceso a la BD cloud.
3. Clonar repositorio.
4. Crear entorno virtual.
5. Instalar dependencias.
6. Copiar `.env` desde respaldo seguro, nunca desde Git.
7. Validar `DATABASE_URL`.
8. Ejecutar:

```powershell
python -m pip install -r requirements.txt
python -m compileall -q main.py config database routes services scripts tests
python tests\smoke_check.py
python main.py
```

9. Entrar a `http://127.0.0.1:5000/`.
10. Probar login.

Si se trabaja con datos cloud reales, tener mucho cuidado con eliminaciones/anulaciones.

## 16. Reglas para el proximo chat

Instrucciones practicas:

- Leer primero este archivo.
- Revisar `git status --short`.
- No hacer commit/push sin permiso explicito.
- No tocar `.env` salvo que el usuario lo pida.
- No subir respaldos, logs, excels reales ni `static/uploads`.
- Antes de editar una pantalla grande, revisar su CSS/JS asociado.
- Mantener estilo visual del Portal Operativo.
- Preferir cambios chicos y probables.
- Despues de cada cambio visual importante, reiniciar servidor local.
- Despues de cambios de seguridad o flujo critico, correr tests.
- Si una accion elimina datos, debe tener respaldo y auditoria.

## 17. Proximas mejoras sugeridas

Prioridad alta:

- Novedades administrables desde Admin.
- Centro de respaldos y eventos criticos.
- Persistir bloqueos/intentos de login en BD.
- Mejorar pruebas de OF/CSV/avisos.
- Extraer JS de Historico.

Prioridad media:

- Redisenar Historico con el estilo nuevo del inicio.
- Dashboard de Admin.
- Enviar PDF de reporte por correo desde la app.
- Mejorar busquedas/autocompletados en Admin/Catalogos.
- Crear estrategia formal de backup PostgreSQL.

Prioridad futura:

- Modulo Recepcion.
- Modulo Seguridad.
- Roles mas granulares por permiso individual.
- Migraciones Alembic.
- Dominio propio.
- Proveedor transaccional definitivo para correos.

## 18. Estado emocional del proyecto

El proyecto esta en etapa productiva temprana. Ya no es prototipo: se usa con pedidos reales y resuelve un dolor operativo concreto. La prioridad ahora es estabilidad, documentacion y trazabilidad antes de sumar muchas pantallas nuevas.

Si otro chat continua, no debe redisenar todo desde cero ni cuestionar reglas ya validadas por uso real. Debe avanzar como mantenimiento profesional de una herramienta en produccion.

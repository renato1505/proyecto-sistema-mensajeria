# Continuidad del Proyecto

Este documento resume el contexto operativo y tecnico actual del Portal Operativo para que otro chat o desarrollador pueda continuar sin perder el hilo.

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
- `/nuevo_envio`
- `/carga_masiva`
- `/catalogos`
- `/envios`
- `/en_proceso`
- `/historico`
- `/of_correo`

La ruta/pestana `/estado_sistema` fue retirada porque no aportaba informacion operativa distinta al log o al estado observable del sistema.

Checks que deben correr antes de subir cambios:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python tests\test_email_client_unit.py
python tests\smoke_check.py
```

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

La anulacion no envia correo. Es solo una marca interna para mantener trazabilidad sin romper el historico.

Eliminaciones de historico si deben enviar respaldo Excel por correo a los destinatarios configurados.

### Correos

El sistema sigue usando Gmail SMTP con clave de aplicacion como solucion actual. Se intento preparar proveedor externo, pero por ahora Gmail funciona y es lo que se esta usando.

Hay correos HTML diferenciados para:

- aviso al funcionario;
- aviso formal al destinatario;
- respaldo interno del lote a Mensajeria;
- respaldo de eliminacion de historico.

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

# Despliegue cloud

Referencia para preparar un despliegue futuro expresamente autorizado.
Esta guía no certifica configuración ni estado actual de Render y no autoriza
conectar, migrar o desplegar. La validación local está en
[Desarrollo](DESARROLLO.md) y [QA](QA_CHECKLIST.md).

## Configuración verificable en el repositorio

[requirements.txt](../requirements.txt) contiene las dependencias Python.
[Procfile](../Procfile) declara:

```text
web: gunicorn main:app
```

El comando de instalación es `pip install -r requirements.txt`.
El proceso web es `gunicorn main:app`; importa la aplicación y puede modificar
esquema y datos. Revisar esos efectos antes de habilitar el servicio.

El repositorio no demuestra qué rama despliega Render, qué auto-deploy está
habilitado ni qué proveedor de correo está activo. Verificarlo en una revisión
autorizada de la plataforma, sin exponer secretos. No asumir que un push a
`refactor/v2-foundation` deba desplegar ni cambiar `main` para hacerlo.

## Variables y acceso

Configurar secretos en el entorno del servicio, nunca en archivos versionados.
No reutilizar claves de demo. El destino PostgreSQL debe ser explícito y aprobado.

| Variable | Requisito |
| --- | --- |
| `DATABASE_URL` | URL PostgreSQL del destino aprobado, gestionada como secreto |
| `SECRET_KEY` | Secreto propio y seguro, distinto del fallback de desarrollo |
| `LOGIN_REQUIRED` | `1` |
| `RENDER` / `APP_ENV` | Render declara `true`; fuera de Render usar `production` |
| `FLASK_DEBUG` | `0` |
| `SESSION_TIMEOUT_MINUTES` | Política de inactividad acordada |
| `CLAVE_ELIMINACION_HISTORICO` | Secreto separado si se habilita esa operación |
| `LOGS_DIR`, `RESPALDOS_LOTES_DIR` | Rutas según política de persistencia |

La aplicación rechaza producción sin secreto válido o login habilitado.
La conexión requiere una URL no vacía. Estas validaciones no prueban que una URL
corresponda al entorno correcto.

Debe existir una cuenta activa con hash Werkzeug en `usuarios_sistema`.
No hay Admin web para crear usuarios ni credenciales de fallback por
`APP_USERS`/`APP_ACCESS_PASSWORD`. La provisión inicial exige un procedimiento
administrativo revisado; el script de reset solo actúa sobre usuarios existentes.
Ver [Autenticación](AUTENTICACION_V2.md).

## Transporte de correo e IMAP

Los transportes implementados son:

- `EMAIL_PROVIDER=smtp`: Gmail SMTP con `CORREO_EMISOR` y `CORREO_CLAVE_APP`.
- `EMAIL_PROVIDER=brevo`: API con `BREVO_API_KEY`, `CORREO_EMISOR` y,
  si corresponde, `BREVO_SENDER_NAME`.
- `EMAIL_PROVIDER=brevo_smtp`: `BREVO_SMTP_HOST`, `BREVO_SMTP_PORT`,
  `BREVO_SMTP_LOGIN` y `BREVO_SMTP_PASSWORD`, además del emisor.

Definir y verificar `CORREO_DESTINO_STARKEN` y
`CORREO_RESPALDO_MENSAJERIA`; no confiar en un destinatario por defecto.
No se ha comprobado aquí cuál transporte usa el servicio remoto.
Cambiar de transporte es una decisión separada de integrar Avisos V2.

La lectura OF por Gmail IMAP utiliza credenciales de correo aunque el envío use
Brevo: revisar `OF_IMAP_HOST`, `OF_IMAP_PORT`,
`OF_CORREO_FILTRO_REMITENTE` y `OF_CORREO_FILTRO_TEXTO`.
No activar credenciales reales en pruebas locales.

Un resultado aceptado por el proveedor no acredita entrega final.
Los avisos legacy pueden duplicarse al reintentar tras fallo parcial.
El motor V2 aún no está integrado a la interfaz y no debe activarse en paralelo.

## Orden de adopción y migraciones

**Bloqueo previo:** el startup ejecuta `Base.metadata.create_all()`,
`asegurar_columnas_operativas()` y `normalizar_datos_operativos()`.
La normalización puede reescribir envíos y fusionar/eliminar remitentes.
No arrancar workers nuevos para averiguar si falta esquema.

Antes de un despliegue que incluya nuevas tablas:

1. Identificar revisión de código, destino, esquema y versión Alembic existentes.
2. Obtener un respaldo completo consistente y demostrar restauración en una copia
   aislada autorizada; un Excel operativo no satisface este requisito.
3. Auditar la copia y resolver diferencias de baseline/metadata.
4. Probar la cadena Alembic y conservar conteos/datos legacy en esa copia.
5. Verificar comportamiento PostgreSQL, FK, índices, concurrencia y rollback.
6. Aprobar ventana, acceso y plan de reversión antes de modificar el destino.
7. Aplicar el procedimiento Alembic aprobado **antes de arrancar/importar**
   la nueva versión web y verificar esquema y revisión.
8. Iniciar servicio y realizar verificación autorizada sin envíos/OF de prueba reales.

Los comandos y decisiones de baseline están en [Migraciones](MIGRACIONES.md).
No hay aquí un comando universal de recuperación ni un permiso implícito para
ejecutar `upgrade` o `stamp` contra Render. Si `create_all()` ya creó tablas
sin avanzar Alembic, detenerse y auditar; nunca resolverlo con `stamp` ciego.

La revisión `20261025_06` es aditiva y no hace backfill; el downgrade elimina
las cuatro tablas H2H y puede perder datos. Preferir una reversión de aplicación
compatible, evaluada sobre copia, a borrar tablas que ya contengan evidencia.

## Persistencia de archivos y recuperación

El almacenamiento local del servicio puede ser efímero. Revisar logs,
`respaldos_lotes/`, `respaldos_historico/` y `tmp_cargas/` y definir custodia,
retención y almacenamiento persistente según necesidad. No confundir correo
de respaldo de lote o histórico con restauración íntegra de base y evidencias.

`scripts/migrar_bd_cloud.py` es un clonador legacy parcial de cuatro modelos.
Incluso su diagnóstico crea esquema de destino y no respalda todos los datos V2.
No usarlo como respaldo/restauración ni ejecutar opciones destructivas como parte
de este procedimiento. Falta formalizar y ensayar recuperación integral.

## Verificación posterior autorizada

Revisar login, sesión/CSRF, lectura de pantallas activas, revisión Alembic y
logs sin publicar datos personales. Las pruebas de escritura deben quedarse
en datos ficticios aislados. Las de correo, importación IMAP y Starken requieren
un plan separado con destinatarios y efectos aprobados.
No ejecutar el smoke contra la base productiva: importa la app y puede escribir.

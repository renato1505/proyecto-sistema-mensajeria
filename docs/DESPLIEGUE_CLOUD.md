# Despliegue Cloud

Esta guia resume los pasos para publicar el Portal Operativo en un servicio cloud y acceder desde navegador mediante una URL.

## Objetivo

Pasar desde ejecucion local:

```text
http://127.0.0.1:5000
```

a una URL web protegida:

```text
https://tu-servicio.onrender.com
```

## Plataforma recomendada inicial

Para una primera publicacion simple se recomienda Render o Railway.

Render es una buena primera opcion porque permite:

- Conectar repositorio GitHub.
- Crear Web Service Python.
- Crear PostgreSQL administrado.
- Configurar variables de entorno.
- Desplegar automaticamente al hacer push.

## Requisitos previos

Antes de desplegar:

1. El proyecto debe estar actualizado en GitHub.
2. `.env` no debe subirse al repositorio.
3. La app debe usar PostgreSQL.
4. Debe existir una clave fuerte en `SECRET_KEY`.
5. Debe activarse login con `LOGIN_REQUIRED=1`.
6. Deben definirse los usuarios en `APP_USERS`.

## Variables de entorno obligatorias

Configurar en el panel cloud:

```text
DATABASE_URL=postgresql+psycopg2://...
SECRET_KEY=clave-larga-y-segura
FLASK_DEBUG=0
LOGIN_REQUIRED=1
APP_USERS=mensajeria:clave-mensajeria;recepcion:clave-recepcion;seguridad:clave-seguridad

CORREO_EMISOR=correo-del-sistema@gmail.com
CORREO_DESTINO_STARKEN=correo-destino-starken
CORREO_RESPALDO_MENSAJERIA=mensajeria.alcantara@loreal.com
EMAIL_PROVIDER=brevo
BREVO_API_KEY=api-key-brevo
BREVO_SENDER_NAME=Portal Operativo

# Solo si se usa EMAIL_PROVIDER=smtp
CORREO_CLAVE_APP=clave-app-gmail

OF_IMAP_HOST=imap.gmail.com
OF_IMAP_PORT=993
OF_CORREO_FILTRO_REMITENTE=infoweb@starken.cl
OF_CORREO_FILTRO_TEXTO=

CLAVE_ELIMINACION_HISTORICO=clave-para-eliminar-historico
```

## Configuracion de servicio web

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn main:app
```

El archivo `Procfile` tambien contiene:

```text
web: gunicorn main:app
```

## Base de datos

Crear una base PostgreSQL en la plataforma cloud y copiar su URL de conexion en `DATABASE_URL`.

El sistema crea tablas base al iniciar y ejecuta columnas operativas faltantes mediante `database/schema.py`.

## Consideraciones de archivos locales

En plataformas cloud, las carpetas locales pueden no ser persistentes despues de un redeploy.

Revisar especialmente:

- `respaldos_lotes`
- `respaldos_historico`
- `logs`
- `tmp_cargas`

Para uso cloud estable se recomienda:

- Mantener respaldo por correo.
- Usar base de datos para informacion critica.
- Evaluar disco persistente o almacenamiento externo si se requiere conservar archivos.

En Render se recomienda enviar correos por API HTTPS:

```text
EMAIL_PROVIDER=brevo
BREVO_API_KEY=...
BREVO_SENDER_NAME=Portal Operativo
```

El modo `smtp` queda disponible para desarrollo local, pero puede fallar en cloud por restricciones de red o bloqueos de proveedores.

En produccion cloud, la eliminacion de historico no debe depender de `respaldos_historico`.
Antes de borrar registros, el sistema envia un Excel de respaldo a:

- `CORREO_RESPALDO_MENSAJERIA`
- `CORREO_EMISOR`

Si ese correo no se puede enviar, la eliminacion se bloquea.

## Seguridad minima

No publicar la app sin:

- `LOGIN_REQUIRED=1`.
- `APP_USERS` con claves fuertes.
- `SECRET_KEY` fuerte.
- HTTPS activo.
- `.env` fuera de Git.

El sistema maneja datos personales como nombres, correos, telefonos, direcciones, RUT y ordenes de flete.

## Flujo sugerido de despliegue

1. Crear cuenta en Render o Railway.
2. Crear base PostgreSQL.
3. Crear Web Service desde GitHub.
4. Configurar build/start command.
5. Agregar variables de entorno.
6. Desplegar.
7. Abrir URL generada.
8. Probar login.
9. Probar rutas principales.
10. Cargar datos iniciales o migrar base local.

## Pruebas posteriores

Despues de desplegar validar:

- Login.
- Nuevo envio.
- Carga masiva.
- Generacion CSV.
- En proceso.
- Procesamiento OF.
- Historico.
- Avisos.
- Catalogos.
- Envio de correos.

## Pendiente para produccion estable

- Definir estrategia de respaldo de base de datos.
- Definir estrategia de respaldo de archivos Excel/CSV.
- Crear usuario/clave de acceso robusta.
- Evaluar dominio propio.
- Evaluar almacenamiento persistente para respaldos.

# Autenticacion V2

La unica fuente de acceso es la tabla `usuarios_sistema`. Las contrasenas deben estar almacenadas con un hash reconocido por Werkzeug. Una cuenta con texto plano o un formato desconocido no puede iniciar sesion y debe restablecerse mediante el procedimiento externo.

## Reset administrativo de contrasena

Ejecutar desde una terminal administrativa que tenga configurada la `DATABASE_URL` correcta:

```bash
python scripts/reset_password.py --usuario operador
```

El script muestra el destino sin credenciales y exige escribir exactamente `host/base` antes de solicitar la nueva contrasena dos veces mediante entrada oculta. No crea usuarios y realiza rollback ante errores.

En Render, abrir una Shell del servicio que comparte las variables de entorno del Web Service y ejecutar el mismo comando. Confirmar cuidadosamente el nombre de la base mostrado. Para automatizar solo la confirmacion del destino, sin exponer la contrasena:

```bash
python scripts/reset_password.py --usuario operador --confirmar-destino host/nombre_base
```

La contrasena siempre se solicita de forma interactiva y nunca se imprime ni registra.

## Configuracion productiva

Render define `RENDER=true`, por lo que la aplicacion trata ese entorno como produccion. Tambien puede declararse `APP_ENV=production` fuera de Render.

En produccion son obligatorios:

- `DATABASE_URL` valida;
- `SECRET_KEY` propia, no el fallback local;
- `LOGIN_REQUIRED=1`.

La aplicacion falla al arrancar si en produccion falta una `SECRET_KEY` segura o el login esta deshabilitado. Desarrollo y tests pueden seguir usando el fallback local y SQLite aislado.

## Variables obsoletas en Render

`APP_USERS` y `APP_ACCESS_PASSWORD` ya no tienen consumidores. Pueden eliminarse del panel de Render despues de verificar que existe una cuenta activa en `usuarios_sistema` y de probar el script de reset contra el destino correcto.

La antigua tabla de solicitudes de recuperacion se conserva solo para una migracion futura; la aplicacion ya no crea ni resuelve nuevas solicitudes.

El bloqueo de intentos sigue viviendo en memoria del proceso. Un reinicio o escalado de instancias pierde ese estado; su persistencia queda pendiente para una fase posterior.

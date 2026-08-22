# Migracion a otro PC

Esta guia sirve para mover el entorno de desarrollo del Portal Operativo a otro computador sin perder contexto ni exponer datos sensibles.

## 1. Que se debe migrar

Se debe migrar:

- codigo fuente desde GitHub;
- archivo `.env` por canal seguro;
- acceso a PostgreSQL local o cloud;
- credenciales de Render/GitHub si se administrara despliegue;
- acceso al correo del sistema si se probaran correos;
- documentacion dentro de `docs/`.

No se recomienda migrar manualmente:

- `venv/`;
- `__pycache__/`;
- `logs/`;
- `respaldos_lotes/`;
- `respaldos_historico/`;
- `respaldos_migracion/`;
- `tmp_cargas/`;
- archivos Excel reales;
- `static/uploads/` salvo que se necesiten evidencias historicas locales.

Estas carpetas estan ignoradas por Git.

## 2. Instalar base del entorno

En el nuevo PC instalar:

- Python compatible;
- Git;
- PostgreSQL si se usara base local;
- editor de codigo;
- acceso a internet para instalar dependencias.

## 3. Clonar repositorio

```powershell
git clone https://github.com/renato1505/proyecto-sistema-mensajeria.git
cd proyecto-sistema-mensajeria\sistema_mensajeria
```

Si el repo ya existe:

```powershell
git pull
```

## 4. Crear entorno virtual

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Configurar `.env`

Copiar `.env.example` como `.env` y completar valores reales.

Variables criticas:

```text
DATABASE_URL=
SECRET_KEY=
LOGIN_REQUIRED=
APP_USERS=
SESSION_TIMEOUT_MINUTES=
CORREO_EMISOR=
CORREO_CLAVE_APP=
CORREO_RESPALDO_MENSAJERIA=
CLAVE_ELIMINACION_HISTORICO=
```

Si se trabaja contra Render Postgres, usar la URL cloud en `DATABASE_URL`.

Si se trabaja localmente, usar la base local.

## 6. Base de datos

Para base local:

1. Crear base PostgreSQL.
2. Configurar `DATABASE_URL`.
3. Iniciar app una vez para crear tablas.
4. Cargar catalogos si corresponde.

Para base cloud:

1. Usar la `DATABASE_URL` de Render.
2. No ejecutar scripts destructivos.
3. Probar con usuario seguro.

## 7. Validar instalacion

Desde `sistema_mensajeria`:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
```

Luego ejecutar:

```powershell
python main.py
```

Abrir:

```text
http://127.0.0.1:5000/
```

## 8. Prueba manual minima

1. Login.
2. Inicio.
3. Envios.
4. Pendientes.
5. Historico.
6. Reportes.
7. Admin.

Si se probaran correos:

```powershell
python tests\test_correo.py --confirmar
```

Esta prueba envia correo real.

## 9. Precauciones

- No subir `.env`.
- No subir respaldos.
- No subir Excel con datos reales.
- No borrar historico real desde pruebas.
- No hacer push sin correr QA.
- No cambiar variables de Render sin anotar que se cambio.

## 10. Primer mensaje recomendado para otro chat

Si se continua con otro chat, enviar:

```text
Lee primero docs/TRASPASO_NUEVO_CHAT.md, docs/ARQUITECTURA.md, docs/OPERACION.md y docs/ADMINISTRACION.md. El proyecto ya esta en produccion en Render y el modulo activo es Mensajeria. No hacer commit ni push sin permiso. Mantener estilo visual y reglas de respaldo/auditoria.
```

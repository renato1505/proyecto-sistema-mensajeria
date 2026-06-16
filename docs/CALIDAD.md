# Calidad y seguridad

## Controles implementados

- Variables sensibles separadas en `.env`.
- `.env`, respaldos, logs y entorno virtual excluidos de Git.
- CSRF global para POST, PUT, PATCH y DELETE.
- Cierre de sesion por inactividad configurable con `SESSION_TIMEOUT_MINUTES`.
- Validacion de entradas principales antes de guardar.
- RUT operativo: acepta `0` cuando no fue informado.
- Respaldos antes de eliminar historico.
- Eliminacion de historico bloqueada si falla el correo de respaldo.
- Anulacion de OF sin eliminar datos historicos.
- Hora operativa centralizada en `America/Santiago` mediante `utils/fechas.py`.
- Logs tecnicos rotativos en `logs/sistema_mensajeria.log`.
- Smoke test seguro sin envio de correo ni cambio de estados.
- Pruebas unitarias para cliente de correo, plantillas, avisos y validaciones.

## Checks recomendados antes de subir cambios

```powershell
python -m compileall -q main.py config database routes services scripts tests
python tests\test_email_client_unit.py
python tests\smoke_check.py
python scripts\aplicar_indices.py
```

## Reglas para GitHub

- No subir `.env`.
- No subir archivos Excel reales.
- No subir respaldos ni logs.
- Revisar cambios antes de hacer commit.
- Mantener `.env.example` solo con valores de ejemplo.

## Riesgos controlados

- La app no usa roles porque es una herramienta interna operada por dos personas.
- La seguridad inicial depende del login interno, control de credenciales y correo configurado.
- La eliminacion historica exige clave y genera respaldo previo.
- Los correos dependen actualmente de Gmail SMTP/IMAP. Si Render o Gmail bloquean envios, migrar a proveedor transaccional.

## Mejoras futuras

- Migraciones de base de datos con Alembic.
- Auditoria de acciones importantes en una tabla dedicada.
- Ampliar pruebas unitarias para generacion CSV Starken y carga masiva.
- Separacion futura por modulos/areas si se expande a Recepcion o Seguridad.

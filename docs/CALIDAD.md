# Calidad y seguridad

## Controles implementados

- Variables sensibles separadas en `.env`.
- `.env`, respaldos, logs y entorno virtual excluidos de Git.
- CSRF global para POST, PUT, PATCH y DELETE.
- Validacion de entradas principales antes de guardar.
- RUT operativo: acepta `0` cuando no fue informado.
- Respaldos antes de eliminar historico.
- Logs tecnicos rotativos en `logs/sistema_mensajeria.log`.
- Smoke test seguro sin envio de correo ni cambio de estados.

## Checks recomendados antes de subir cambios

```powershell
python -m compileall -q main.py config database routes services scripts tests
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
- La seguridad depende del control fisico del equipo y del correo configurado.
- La eliminacion historica exige clave y genera respaldo previo.

## Mejoras futuras

- Migraciones de base de datos con Alembic.
- Pruebas unitarias para validaciones y generacion CSV Starken.
- Auditoria de acciones importantes en una tabla dedicada.
- Pantalla interna de estado del sistema.

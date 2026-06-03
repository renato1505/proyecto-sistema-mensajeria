# Guia para subir a GitHub

## Antes del primer commit

Ejecutar checks:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python tests\smoke_check.py
```

Revisar que estos archivos no se suban:

- `.env`
- `venv/`
- `logs/`
- `respaldos_lotes/`
- `respaldos_historico/`
- Archivos Excel reales con datos de funcionarios, remitentes o destinatarios.

## Comandos base

```powershell
git init
git add .
git status
git commit -m "Version inicial del sistema de mensajeria"
git branch -M main
git remote add origin URL_DEL_REPOSITORIO
git push -u origin main
```

## Recomendaciones

- Crear el repositorio como privado.
- Revisar `git status` antes de cada commit.
- No pegar claves reales en commits, issues ni README.
- Mantener `.env.example` con datos ficticios.
- Cambiar inmediatamente cualquier clave que se haya subido por error.


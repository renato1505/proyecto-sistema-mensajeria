# Documento histórico: GITHUB.md

> Archivado el 27 de octubre de 2026 durante la limpieza L1.
> El contenido original se conserva íntegro debajo de este aviso. Describe una etapa anterior,
> puede citar archivos retirados, autenticación obsoleta y comandos que escriben o destruyen datos.
> **No ejecutar sus procedimientos como guía vigente**, ni siquiera comandos llamados diagnóstico o smoke.
> Las rutas citadas en el original son referencias históricas desde la raíz del repositorio.
> Consultar [README](../../README.md), [Desarrollo](../DESARROLLO.md),
> [Estado del proyecto](../ESTADO_PROYECTO.md) y [Migraciones](../MIGRACIONES.md).

---

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


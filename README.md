# Portal Operativo

Aplicacion Flask para centralizar procesos operativos internos. El modulo principal actual es Mensajeria: registra envios, genera archivos CSV para Starken, carga respuestas OF y mantiene historico descargable.

Actualmente el modulo opera con normalizacion de telefonos, OF, nombres y textos operativos para reducir duplicados por acentos, mayusculas inconsistentes o valores pegados desde Excel.

## Flujo principal

1. Registrar envios en estado pendiente.
2. Revisar y editar pendientes antes de enviarlos a Starken.
3. Generar CSV Starken y elegir si se descarga o se envia por correo.
4. Cargar archivo OF manualmente o desde correo.
5. Mover envios OK al historico y enviar respaldo a Mensajeria.
6. Enviar avisos a funcionarios cuando corresponda.
7. Exportar o respaldar historico cuando corresponda.

## Preparacion

1. Crear o activar un entorno virtual de Python.
2. Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

3. Copiar `.env.example` como `.env` y completar las claves reales.
4. Verificar que PostgreSQL tenga creada la base `sistema_mensajeria`.
5. Aplicar indices si es una instalacion nueva o si se actualizo el modelo:

```powershell
python scripts\aplicar_indices.py
```

## Ejecutar

```powershell
python main.py
```

La aplicacion queda disponible normalmente en:

```text
http://127.0.0.1:5000/
```

## Checks de calidad

Antes de subir cambios o probar una version nueva:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python tests\test_email_client_unit.py
python tests\smoke_check.py
```

La prueba de correo envia un correo real, por eso exige confirmacion:

```powershell
python tests\test_correo.py --confirmar
```

## Scripts destructivos

Estos scripts borran y recargan catalogos completos. Por seguridad exigen confirmacion explicita:

```powershell
python scripts\cargar_comunas.py --confirmar
python scripts\cargar_remitentes.py --confirmar
```

## Datos sensibles

No subir ni compartir `.env`, respaldos ni archivos Excel con datos reales. Esos archivos pueden contener correos, telefonos, direcciones y datos internos.

## Documentacion

- `docs/OPERACION.md`: procedimiento de uso diario.
- `docs/ARQUITECTURA.md`: mapa tecnico del flujo, modulos y estados.
- `docs/CALIDAD.md`: controles, checks y recomendaciones para GitHub.
- `docs/GITHUB.md`: guia para subir el repositorio sin exponer datos sensibles.
- `docs/CONTINUIDAD_PROYECTO.md`: contexto actual para continuar el desarrollo en otro chat o sesion.
- `docs/REVISION_CALIDAD_2026-06.md`: revision estricta de calidad, riesgos y prioridades.

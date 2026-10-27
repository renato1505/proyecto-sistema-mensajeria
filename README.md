# Sistema de Mensajería V2

Herramienta interna para registrar envíos, preparar archivos Starken, procesar
respuestas de órdenes de flete (OF) y conservar seguimiento operativo. Reemplaza
planillas y avisos manuales repetitivos con validación y trazabilidad por envío.

## Funcionalidades actuales

- Envíos individuales y carga masiva Excel con revisión antes de confirmar.
- Catálogos de remitentes y destinatarios y autocompletado de comunas.
- Selección de pendientes y generación de CSV Starken por lote.
- Importación de respuestas OF manual o asistida por correo.
- Bloqueos ante resultados H2H ambiguos para evitar regeneraciones accidentales.
- Registro de retiros físicos V2, búsqueda y selección de envíos elegibles.
- Histórico filtrable, exportación, anulación y eliminación con respaldo.
- Avisos legacy a funcionarios y destinatarios, gestionados por el operador.
- Login contra usuarios de base de datos, CSRF y vencimiento por inactividad.

La persistencia de intentos OF y conciliaciones H2H está implementada, pero aún
no se integra al flujo operativo. La conciliación manual y la integración de
Avisos V2 están pendientes. Admin y Reportes no son módulos activos.

## Arquitectura e instalación

Flask, Jinja y JavaScript; SQLAlchemy y Alembic; SQLite para desarrollo aislado
y PostgreSQL como destino de despliegue. Gunicorn inicia el servicio mediante
[Procfile](Procfile). Las dependencias están en [requirements.txt](requirements.txt).

Se necesita Git, Python con entorno virtual y las dependencias instaladas.
La última validación registrada utilizó Python 3.14 del `venv`.
Seguir [desarrollo local](docs/DESARROLLO.md) para instalar y probar sin
credenciales reales. Para explorar la interfaz con datos ficticios, usar la
[demo operativa](docs/DEMO_OPERATIVA_V2.md).

**Antes de arrancar:** importar o ejecutar `main.py` puede crear tablas,
agregar columnas y normalizar datos existentes. No es una operación de lectura.
Nunca usar una base real para verificar una instalación o ejecutar pruebas.

## Documentación vigente

| Necesidad | Documento |
| --- | --- |
| Preparar otro equipo y trabajar con Git | [Desarrollo](docs/DESARROLLO.md) |
| Usar el sistema | [Operación](docs/OPERACION.md) |
| Comprender módulos, datos y límites | [Arquitectura](docs/ARQUITECTURA.md) |
| Login y restablecimiento externo | [Autenticación V2](docs/AUTENTICACION_V2.md) |
| Esquema, baseline y decisiones técnicas | [Migraciones](docs/MIGRACIONES.md) |
| Preparar un despliegue autorizado | [Despliegue cloud](docs/DESPLIEGUE_CLOUD.md) |
| Pruebas y verificaciones manuales | [Checklist QA](docs/QA_CHECKLIST.md) |
| Ensayar sin servicios externos | [Demo operativa V2](docs/DEMO_OPERATIVA_V2.md) |
| Continuar el proyecto y revisar pendientes | [Estado del proyecto](docs/ESTADO_PROYECTO.md) |

## Estado actual

Base consolidada en `refactor/v2-foundation`:
`e7cf93e4ebf318ac11d5d9158a769840ca173412`.
Fases 1.1, 1.1.1, 1.2B y 1.2B.1 consolidadas. Última ejecución registrada:
**273 pruebas aprobadas**; este cambio documental no vuelve a ejecutarlas.
La etapa L1 actualiza documentación y queda pendiente de revisión y commit.

Los nueve originales de guías fusionadas e informes se conservan en
[el archivo histórico](docs/historico/) y se identifican desde
[Estado del proyecto](docs/ESTADO_PROYECTO.md#archivo-documental).
Son antecedentes y no procedimientos vigentes. No subir `.env`, bases,
respaldos, logs, archivos operativos ni datos personales a Git.

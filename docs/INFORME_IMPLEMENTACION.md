# Informe de Implementacion

# Sistema de Gestion de Mensajeria

**Proyecto:** Sistema Automatizado de Gestion de Mensajeria  
**Area:** Recepcion y Mensajeria  
**Responsable operativo:** Renato Valenzuela  
**Organizacion:** L'Oreal Chile  
**Estado:** Sistema funcional en mejora continua  
**Fecha:** Junio 2026

## 1. Resumen Ejecutivo

El presente documento describe la implementacion y evolucion del Sistema de Gestion de Mensajeria, una herramienta interna desarrollada para optimizar el proceso de registro, control, procesamiento y seguimiento de envios gestionados por el area de Mensajeria.

El proyecto nace como respuesta a un flujo operativo altamente manual, basado principalmente en correos, planillas Excel y carga posterior en la plataforma de Starken. Dicho flujo, aunque funcional, generaba una alta dependencia de tareas repetitivas, copia manual de datos, revision individual de ordenes de flete y envio manual de notificaciones a funcionarios.

La version actual del sistema permite registrar envios individuales, realizar cargas masivas desde Excel, generar archivos compatibles con Starken, administrar lotes en proceso, procesar ordenes de flete, mantener historial interno, gestionar catalogos de remitentes y destinatarios, y enviar avisos a funcionarios con respaldo operativo.

Actualmente el sistema ya ha sido utilizado con datos reales de pedidos procesados y entregados exitosamente, por lo que se considera una herramienta funcional, operativa y en etapa de mejora continua.

## 2. Contexto del Area

El area de Mensajeria gestiona solicitudes de envio realizadas por funcionarios de distintas divisiones de la compania. Estas solicitudes pueden corresponder a envios a domicilio o envios a agencia, dependiendo de la necesidad del solicitante y de la disponibilidad de informacion del destinatario.

El flujo operativo involucra la recepcion de productos o cajas, verificacion basica del embalaje, registro de informacion del remitente y destinatario, generacion de archivos para Starken, recepcion de ordenes de flete, impresion de etiquetas, entrega al proveedor logistico y comunicacion posterior al funcionario solicitante.

El equipo operativo es reducido, por lo que la automatizacion de tareas repetitivas tiene un impacto directo en la eficiencia diaria del area.

## 3. Flujo Operativo Anterior

Antes de la implementacion del sistema, el proceso se realizaba de forma principalmente manual:

1. El funcionario enviaba por correo la informacion del destinatario.
2. El funcionario entregaba el producto o caja al area de Mensajeria.
3. Mensajeria revisaba que el paquete estuviera correctamente embalado.
4. Los datos eran ingresados manualmente en una planilla Excel.
5. La planilla era exportada como archivo CSV.
6. El archivo era cargado manualmente en la plataforma de Starken.
7. Se esperaba la recepcion de las ordenes de flete.
8. Las ordenes de flete eran revisadas manualmente.
9. Se ingresaba a Starken para imprimir etiquetas.
10. Las etiquetas eran pegadas en los paquetes.
11. Starken retiraba los pedidos.
12. Mensajeria copiaba manualmente la orden de flete correspondiente a cada destinatario.
13. Se enviaba un correo individual a cada funcionario informando su orden de flete.

Este flujo permitia completar la operacion, pero dejaba varios puntos expuestos a errores humanos, perdida de tiempo y baja trazabilidad interna.

## 4. Problemas Identificados

### 4.1 Procesos manuales repetitivos

El flujo anterior exigia copiar informacion desde correos, ingresar datos en planillas, generar archivos, revisar ordenes de flete y redactar correos de notificacion uno por uno.

### 4.2 Riesgo de errores de digitacion

La carga manual de nombres, direcciones, telefonos, comunas, regiones y datos de remitente aumentaba la probabilidad de errores antes de llegar a Starken.

### 4.3 Falta de trazabilidad interna

Aunque Starken mantiene su propio registro, el area de Mensajeria no contaba con una base interna estructurada que permitiera consultar historico, lotes, ordenes de flete, remitentes, destinatarios y respaldos.

### 4.4 Dificultad para comunicar ordenes de flete

El envio de ordenes de flete a funcionarios dependia de una revision manual y del envio individual de correos.

### 4.5 Baja capacidad de analisis

Al no existir una base de datos interna, era dificil analizar cantidad de envios, volumen por division, destinos frecuentes, comportamiento mensual o carga operativa del area.

## 5. Objetivo del Proyecto

Desarrollar e implementar una herramienta interna que permita optimizar la gestion de envios del area de Mensajeria, reduciendo tareas manuales, disminuyendo errores, centralizando informacion y mejorando la trazabilidad de los pedidos.

Los objetivos especificos son:

- Digitalizar el registro de envios.
- Permitir carga masiva desde una plantilla estructurada.
- Generar archivos compatibles con Starken.
- Mantener control interno por lote.
- Procesar ordenes de flete.
- Mantener historial consultable.
- Administrar remitentes y destinatarios frecuentes.
- Enviar avisos a funcionarios.
- Respaldar la informacion critica del proceso.

## 6. Solucion Implementada

El Sistema de Gestion de Mensajeria centraliza el flujo operativo en una aplicacion web interna. La herramienta permite manejar el ciclo completo de un envio desde su registro hasta su cierre en historico.

La solucion actual incluye:

- Registro individual de envios.
- Carga masiva mediante plantilla Excel.
- Validacion de datos antes de procesar.
- Autocompletado de remitentes, destinatarios y comunas.
- Asignacion automatica de region segun comuna.
- Generacion de CSV para Starken.
- Opcion de descargar CSV o enviarlo por correo.
- Agrupacion de pedidos por lote.
- Vista de pedidos en proceso.
- Procesamiento de ordenes de flete.
- Lectura asistida de correos OF.
- Cruce de archivo procesado con lote correspondiente.
- Historico filtrable y exportable.
- Catalogo administrativo de remitentes y destinatarios.
- Respaldo automatico para Mensajeria.
- Avisos pendientes a funcionarios.
- Indicador visual de carga durante procesos.

## 7. Flujo Operativo Actual

El flujo actual se estructura de la siguiente manera:

1. Se registra un envio individual o se realiza una carga masiva desde Excel.
2. Los pedidos quedan en estado pendiente para revision.
3. Mensajeria valida la informacion antes de generar el archivo Starken.
4. El sistema genera el CSV compatible con Starken.
5. El usuario puede descargar el CSV o enviarlo por correo.
6. Los pedidos pasan a estado en proceso y quedan asociados a un lote.
7. Cuando Starken devuelve las ordenes de flete, estas se procesan en el sistema.
8. El sistema cruza las ordenes de flete con el lote correspondiente.
9. Los pedidos correctos pasan a historico.
10. Se genera respaldo interno para Mensajeria.
11. Los avisos a funcionarios quedan pendientes hasta que Mensajeria decida enviarlos.
12. Al enviar avisos, el funcionario recibe el detalle de sus pedidos y ordenes de flete.

## 8. Funcionalidades Implementadas

### 8.1 Nuevo envio

Permite registrar pedidos de manera individual con informacion de remitente, destinatario, tipo de envio, bultos y kilos.

### 8.2 Carga masiva

Permite importar multiples pedidos desde una plantilla Excel estandarizada. El sistema valida errores y permite corregir datos antes de confirmar la carga.

### 8.3 Pendientes

Centraliza los pedidos listos para revision antes de generar el archivo Starken.

### 8.4 En proceso

Agrupa pedidos por lote y permite controlar que lotes estan esperando ordenes de flete.

### 8.5 Procesamiento de OF

Permite cargar archivos de ordenes de flete y asignar automaticamente la informacion al lote correspondiente.

### 8.6 OF desde correo

Permite buscar correos enviados por Starken, identificar el archivo procesado y asociarlo al lote correcto.

### 8.7 Historico

Permite consultar envios cerrados, filtrar informacion, exportar registros y eliminar historico con respaldo previo.

### 8.8 Catalogos

Permite visualizar, filtrar, agregar, editar y eliminar remitentes y destinatarios frecuentes.

### 8.9 Avisos

Permite enviar correos a funcionarios con el detalle de sus pedidos y ordenes de flete cuando corresponda.

### 8.10 Respaldo interno

El sistema genera respaldo para Mensajeria, permitiendo conservar informacion relevante fuera de la base operativa.

## 9. Beneficios Obtenidos

### 9.1 Reduccion de tareas manuales

El sistema disminuye el tiempo dedicado a copiar informacion, ordenar planillas, cruzar datos y redactar avisos individuales.

### 9.2 Menor riesgo de error

Las validaciones, autocompletados, filtros y cruces por lote reducen errores de digitacion y errores de asociacion entre destinatario y orden de flete.

### 9.3 Trazabilidad interna

Cada envio queda registrado con datos de remitente, destinatario, lote, estado, orden de flete y fecha de creacion.

### 9.4 Mejor control operativo

La separacion entre pendiente, en proceso, historico y avisos permite entender rapidamente en que etapa esta cada pedido.

### 9.5 Mejor comunicacion

Los funcionarios pueden recibir informacion estructurada de sus pedidos, evitando correos manuales uno a uno.

### 9.6 Escalabilidad

El sistema fue ordenado modularmente para permitir futuras mejoras sin depender de una sola planilla o archivo complejo.

## 10. Estado Actual del Sistema

El sistema se encuentra en una etapa funcional avanzada. Ya permite completar el flujo principal de Mensajeria y ha sido probado con datos reales de pedidos previamente gestionados y entregados exitosamente.

Actualmente puede considerarse una version operativa interna en mejora continua. No corresponde a una version final cerrada, ya que el objetivo es seguir incorporando mejoras visuales, operativas, documentales y tecnicas.

## 11. Mejoras Recomendadas

### Prioridad alta

- Completar documentacion formal de uso, operacion e instalacion.
- Definir procedimiento de respaldo y restauracion de base de datos.
- Preparar traslado del sistema a otro equipo o entorno estable.
- Incorporar migraciones formales de base de datos.
- Agregar pruebas unitarias para carga masiva, OF, avisos y generacion CSV.

### Prioridad media

- Incorporar dashboard de metricas operativas.
- Medir envios por division, comuna, region y mes.
- Registrar auditoria de acciones relevantes.
- Mejorar reportes mensuales.
- Incorporar estado de retiro por Starken.

### Prioridad futura

- Integracion mas profunda con correo.
- Gestion avanzada de agencias Starken.
- Sugerencia de agencia segun comuna o direccion.
- Panel de indicadores para jefatura o control interno.

## 12. Conclusion

La implementacion del Sistema de Gestion de Mensajeria representa una mejora significativa respecto al flujo anterior basado en correos, planillas y revision manual.

El sistema permite reducir tareas repetitivas, ordenar la informacion, disminuir errores y entregar mayor trazabilidad al proceso completo de envios. Ademas, crea una base interna de informacion que antes no existia, permitiendo proyectar futuras mejoras de control, analisis y reportabilidad.

El proyecto ya cumple con el objetivo principal de optimizar la operacion diaria del area y se encuentra en condiciones de seguir evolucionando hacia una herramienta interna cada vez mas completa, estable y estrategica para la gestion de Mensajeria.

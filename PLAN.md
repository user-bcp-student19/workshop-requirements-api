# Plan de correccion

## Alcance y seleccion

Seleccion confirmada por el usuario: **H-02 y H-04**, ambos pendientes y de severidad alta en [HALLAZGOS.md](HALLAZGOS.md). H-02 se prioriza por la exposicion de informacion ajena; H-04 por la escritura de archivos controlada por el cliente y su alcance acotado.

Este documento es una propuesta: no modifica codigo, pruebas, dependencias, contratos ni estados. [HALLAZGOS.md](HALLAZGOS.md) sigue siendo el unico registro de seguimiento. H-01, H-03, H-05, H-06 y H-07 no se consideran resueltos por este plan.

Fuentes obligatorias: [docs/ENDPOINTS.md](docs/ENDPOINTS.md), [docs/GOOD_PRACTICES.md](docs/GOOD_PRACTICES.md) y [REGLAS.md](REGLAS.md). No se inspeccionaran ni modificaran otros componentes del workspace.

## Contratos y reglas comunes

- Conservar las cinco rutas, metodos, entradas declaradas, codigos satisfactorios, claves y tipos de respuesta. Mantener create_app(db_path, upload_dir) y los valores predeterminados de configuracion.
- Mantener owner como query opcional y como campo aceptado en el cuerpo. Su capacidad de seleccionar otra identidad es un comportamiento inseguro descrito en ENDPOINTS, no una obligacion del contrato. Se ignorara su valor para decidir el propietario efectivo; no se eliminara el parametro ni se introducira un 403 para estas peticiones.
- Mantener los valores predeterminados y conversiones actuales del cuerpo de tareas, incluido null explicito convertido en "None" en los campos que no controlan la autorizacion. No introducir enumeraciones, restricciones de titulo ni rechazos de campos adicionales en este cambio.
- Mantener 401 para autenticacion invalida y 422 para entradas estructuralmente invalidas. Los nuevos rechazos de archivos peligrosos conservaran el sobre JSON con detail y mensajes genericos; no expondran excepciones ni rutas internas adicionales.
- Adoptar modelos Pydantic solo en las rutas tocadas, conservando nombres como createdAt, fileName y storedAt. Para mantener la coercion legacy, usar validacion previa explicita: un str de Pydantic por si solo no reproduce todos los str(...) actuales. Distinguir campo ausente de null. No publicar limites de dominio nuevos en Task.
- Separar las responsabilidades de las rutas tocadas: ruta para HTTP y modelos, servicio para identidad o reglas de archivos, repositorio para SQLite o almacenamiento. No dejar SQL dentro de las rutas ni separar ahora todo el monolito.
- Usar funciones pequenas con nombres de proposito, una unica funcion para obtener el propietario efectivo y una unica politica de archivos. Preferir validaciones con salida temprana y condiciones combinadas; no anidar decisiones ni duplicar validaciones entre ruta y servicio.
- Declarar constantes con nombre para estados predeterminados, extensiones, tamanos, tamano de bloque y mensajes introducidos. Las cifras de seguridad propuestas abajo son decisiones de este plan, no convenciones existentes.
- No agregar dependencias: FastAPI, Pydantic y la biblioteca estandar cubren estas correcciones. No cambiar los requisitos fijados ni atribuirles nuevas garantias de seguridad.

## H-02: autorizacion ligada a la identidad

### Hallazgo y problema

Corresponde a H-02 de [HALLAZGOS.md](HALLAZGOS.md). list_tasks y summary seleccionan owner desde el cliente; create_task permite atribuir tareas a otra persona. Ninguna ruta verifica un privilegio para hacerlo. Evidencia: [app/main.py:69](app/main.py#L69), [app/main.py:83](app/main.py#L83), [app/main.py:92](app/main.py#L92).

### Caracterizacion antes de tocar la implementacion

Ampliar primero [tests/test_api.py](tests/test_api.py), reutilizando TestClient, headers y tmp_path. Ejecutar estas pruebas contra el codigo actual antes de extraer funciones:

- GET /api/tasks sin owner, con owner vacio y con owner igual al usuario: HTTP 200, tareas propias, orden ascendente, claves y tipos exactos de Task.
- GET /api/summary con las mismas variantes: owner, total, byStatus y highPriorityOpen exactos; incluir una identidad sin tareas y combinaciones HIGH con DONE y ARCHIVED.
- POST /api/tasks sin owner o con owner propio: HTTP 201, persistencia visible en listado y resumen, claves de respuesta, valores predeterminados, campos adicionales ignorados y coerciones actuales de los demas campos.
- Identidades student y trainer obtienen sus propios datos; el rol por si solo no es requisito de una ruta. Verificar 401 con token invalido y 422 sin cuerpo obligatorio.

Las pruebas de caracterizacion conservan comportamiento legitimo y deben pasar antes del refactor. Separadamente, escribir regresiones de seguridad que fallen inicialmente: consultar tasks o summary indicando otro owner debe devolver solo datos de la identidad; crear con owner ajeno, null o vacio debe almacenar el usuario autenticado. Verificar respuesta y persistencia. No convertir la fuga actual en una expectativa permanente.

### Cambio propuesto

1. Centralizar en el servicio la seleccion del propietario: siempre identity["username"]. Todas las operaciones de tareas y resumen deben usar esa misma funcion; no derivar permisos del campo owner ni crear excepciones para TRAINER u otro rol no autorizadas por las convenciones.
2. Conservar owner en la firma HTTP y en el modelo de entrada, pero no trasladar su valor al repositorio como propietario efectivo. La respuesta Task.owner y summary.owner reflejaran la identidad usada realmente.
3. Extraer el SQL de las tres rutas a un repositorio reducido. Pasar el usuario y los valores como parametros SQLite `?`, incluido el id de la lectura posterior al INSERT. Es un soporte necesario de la separacion exigida por las convenciones, no un proyecto adicional de refactor ni un cierre automatico de H-03.
4. Mantener commit y lectura de la tarea creada bajo responsabilidad del repositorio. Conservar por ahora el ciclo de vida de conexion de create_app; no redisenar concurrencia ni migrar el esquema.
5. Tipar Task, entrada de creacion y Summary con Pydantic sin cambiar serializacion ni coercciones documentadas. Mantener una sola conversion fila-modelo. Agregar el resumen con contadores y una condicion combinada para HIGH distinto de DONE/ARCHIVED.

### Archivos a tocar durante la implementacion

- [tests/test_api.py](tests/test_api.py): caracterizacion y regresiones del propietario efectivo.
- [app/main.py](app/main.py): conectar modelos, servicio y repositorio en las tres rutas; conservar la fabrica y las demas rutas.
- `app/models.py` (nuevo propuesto): modelos Pydantic de las operaciones tocadas y adaptacion compatible del cuerpo.
- `app/services.py` (nuevo propuesto): resolucion unica del propietario y agregacion del resumen.
- `app/repositories.py` (nuevo propuesto): consultas parametrizadas y mapeo de filas. Reutilizarlo en H-04, sin nuevas jerarquias de clases innecesarias.

### Verificacion y limite de la correccion

Ejecutar primero las pruebas de caracterizacion y luego las regresiones de H-02; comprobar tambien identidades con comillas para no confundir autorizacion con interpolacion SQL. Comparar rutas, parametros y esquemas OpenAPI antes/despues, explicando solo los cambios de seguridad previstos, sin eliminar owner.

H-01 sigue pendiente: legacy_identity permite falsificar la identidad de origen. Esta correccion impide seleccionar otro owner directamente, pero no constituye autorizacion robusta extremo a extremo mientras el token no se verifique criptograficamente. La autenticacion real es un prerrequisito para esa garantia, no una ampliacion implicita de esta seleccion. No se anadira una biblioteca JWT ni se asumiran claves o claims del backend en este plan.

## H-04: carga segura de archivos

### Hallazgo y problema

Corresponde a H-04 de [HALLAZGOS.md](HALLAZGOS.md). Se forma el destino con file.filename, se lee el contenido completo y se escribe sin controles propios. Esto permite destinos no autorizados, sobreescrituras y consumo excesivo de recursos. Evidencia: [app/main.py:109](app/main.py#L109), [app/main.py:110](app/main.py#L110), [app/main.py:111](app/main.py#L111).

### Caracterizacion antes de tocar la implementacion

Ampliar primero [tests/test_api.py](tests/test_api.py), reutilizando test_uploads_requirement y tmp_path:

- Cargar requirements.txt con contenido conocido: HTTP 201; claves exactas owner, fileName, storedAt y size, valores y tipos actuales, contenido identico en disco y nombre simple conservado.
- Verificar storedAt tanto con directorio absoluto como relativo, manteniendo su representacion str actual para nombres simples. Todos los directorios temporales, incluso los relativos, quedaran dentro de este repositorio y se limpiaran al finalizar.
- Repetir la carga con otra identidad y comprobar owner; verificar 401 sin token valido y 422 sin file. Mantener el campo multipart file, sin convertirlo a JSON ni cambiar su nombre.

Escribir ademas regresiones de seguridad, inicialmente fallidas cuando corresponda: rutas relativas con ascenso, rutas absolutas POSIX y Windows, separadores de ambos sistemas, nombres vacios, nombres reservados de Windows, extensiones rechazadas, limites de tamano, nombres repetidos y errores de escritura. Verificar que no se escribe fuera del directorio ni se modifica un archivo previo. Son entradas locales de prueba, no solicitudes a servicios ajenos.

### Cambio propuesto

1. Concentrar en el servicio la politica de carga. Propuesta explicita para la implementacion: ALLOWED_REQUIREMENT_EXTENSIONS = {".txt", ".md", ".pdf"}, MAX_REQUIREMENT_BYTES = 10 MiB y UPLOAD_CHUNK_BYTES = 64 KiB. Estas decisiones no estan fijadas en GOOD_PRACTICES: confirmar su adecuacion con el responsable antes de implementar; no presentarlas como requisitos existentes ni ampliar extensiones automaticamente.
2. Validar el nombre considerando Windows y POSIX independientemente del SO del proceso. Rechazar rutas absolutas, segmentos de ascenso, separadores, nombres vacios, dispositivos reservados y caracteres de control; normalizar los nombres simples aceptables y verificar su extension normalizada. No limitarse a Path.name ni aceptar que una ruta maliciosa se vuelva segura silenciosamente.
3. Confinar el destino al directorio de cargas resuelto, sin permitir subdirectorios elegidos por el cliente. Conservar nombres simples seguros cuando esten disponibles; ante colision, generar un sufijo con la biblioteca estandar y crear de forma exclusiva, sin truncar destinos ni seguir enlaces preexistentes. Validar tambien casos con enlaces si el SO permite crearlos en pruebas.
4. Leer UploadFile en bloques, contar bytes reales y abortar al superar el maximo, sin confiar solo en Content-Length ni acumular todo en memoria. Escribir en un archivo exclusivo del directorio controlado; retirar cualquier archivo parcial y cerrar recursos tanto en rechazo como en error. Publicar la respuesta de exito solo al completar la escritura.
5. El limite del servicio no impide que el parser multipart reciba antes un cuerpo enorme. Agregar una proteccion ASGI restringida a POST /api/requirements, anterior al parseo, que cuente bytes recibidos incluso sin Content-Length. Propuesta: MAX_REQUIREMENT_REQUEST_BYTES = MAX_REQUIREMENT_BYTES + 64 KiB de sobre multipart, con constante separada; confirmar este margen junto con la politica. No alterar otras rutas ni instalar middleware externo.
6. Para nombres seguros y contenido permitido, conservar HTTP 201 y el modelo de respuesta. fileName seguira siendo el nombre recibido, owner vendra de la identidad, size sera el numero de bytes y storedAt sera str del destino seguro real. La normalizacion o una colision pueden cambiar el destino, no las claves o tipos del contrato.
7. Proponer HTTP 413 por exceso de tamano, 422 por nombre o extension no permitidos y 500 por un fallo interno de almacenamiento. Usar detail generico mediante HTTPException; no devolver str(exception). Los errores de limpieza deben conservar la causa para diagnostico interno sin ocultarla ni exponerla al cliente.

### Archivos a tocar durante la implementacion

- [tests/test_api.py](tests/test_api.py): caracterizacion de carga y regresiones, incluidos limite exacto, un byte por encima, cuerpos sin Content-Length, colisiones y limpieza ante fallo.
- [app/main.py](app/main.py): delegar la carga al servicio, declarar su respuesta Pydantic y registrar el limite de cuerpo solo para esta ruta.
- `app/models.py` (nuevo propuesto, compartido con H-02): modelo de respuesta de carga con las cuatro claves actuales.
- `app/services.py` (nuevo propuesto, compartido): politica, normalizacion y validacion temprana; constantes de seguridad con nombre.
- `app/repositories.py` (nuevo propuesto, compartido): creacion exclusiva, escritura incremental y limpieza del almacenamiento. La ruta no administrara archivos directamente.
- `app/upload_limits.py` (nuevo propuesto): control ASGI de bytes de entrada antes del parser; separado de las reglas de negocio y limitado al endpoint de carga.

### Verificacion y limite de la correccion

Comprobar primero la caracterizacion y despues las regresiones de H-04. Verificar 201 para el archivo permitido justo en el limite, 413 al excederlo, rechazo antes de escribir en casos invalidos y ausencia de residuos tras errores o desconexion. Probar que un limite de cuerpo no bloquea respuestas ni altera los otros cuatro endpoints. No silenciar scanners ni excepciones de pruebas.

La politica no promete analisis antivirus ni proteccion contra administradores locales que controlen el directorio. No agregar descarga, persistencia SQLite de metadatos ni controles por rol. Los CVEs del parser siguen dentro de H-05 y no se consideran corregidos por limitar bytes.

## Secuencia y criterios de salida

1. Antes de modificar implementacion, escribir y ejecutar la caracterizacion en tests/test_api.py para ambos hallazgos con SQLite y uploads temporales dentro del repositorio. Aislar con mocks cualquier acceso externo; no depender del backend ni leer su codigo.
2. Escribir las regresiones de seguridad separadas y comprobar que detectan el comportamiento inseguro actual. No mantener expectativas de fuga o escritura arbitraria como contratos.
3. Implementar H-02 y validar su conjunto enfocado antes de comenzar H-04. Extraer solo las capas necesarias y reutilizar los mismos modulos compartidos.
4. Confirmar la politica propuesta de archivos, implementar H-04 y ejecutar sus pruebas enfocadas; luego ejecutar la suite completa con `python -m pytest`.
5. Comprobar cobertura del codigo modificado de al menos 85%, incluidas ramas de rechazo y limpieza, usando las herramientas de cobertura disponibles en el proyecto. Si falta la herramienta, justificar su instalacion antes de agregar una dependencia; no dar por cumplido el umbral sin medirlo.
6. Comparar rutas, entradas, respuestas y valores predeterminados con docs/ENDPOINTS.md sin editarlo. No usar una igualdad ciega del OpenAPI generado si la tipificacion elimina schemas genericos: revisar compatibilidad real de nombres, requeridos, tipos y casos caracterizados.
7. Solo tras implementar y verificar cada hallazgo, actualizar su fila en HALLAZGOS.md con la evidencia correspondiente. No duplicar estados en PLAN.md ni cerrar otros IDs por efectos colaterales. Revisar `git diff` desde este repositorio y conservar cambios ajenos.

Esta fase entrega exclusivamente PLAN.md; ninguna de las acciones de implementacion o pruebas anteriores se ejecuta al redactarlo.
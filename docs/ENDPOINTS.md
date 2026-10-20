# Endpoints y flujos actuales

Documento derivado de [app/main.py](../app/main.py) mediante lectura estatica. No introduce endpoints ni cambia contratos. Describe el estado actual, incluidas debilidades internas que deben corregirse conservando rutas, metodos y formatos de intercambio. El seguimiento de hallazgos reside exclusivamente en [HALLAZGOS.md](../HALLAZGOS.md).

## Rutas

Las cinco rutas dependen de legacy_identity y reciben el encabezado Authorization. No hay paginacion implementada.

| Metodo | Ruta | Entrada | Respuesta satisfactoria | Implementacion |
|---|---|---|---|---|
| GET | /api/tasks | Query opcional owner: string; ausente o vacio usa el usuario autenticado. | 200; lista de objetos Task, ordenada por id ascendente. | [app/main.py:67](../app/main.py#L67) |
| POST | /api/tasks | Cuerpo JSON obligatorio de tipo objeto; campos descritos abajo. | 201; objeto Task creado. | [app/main.py:77](../app/main.py#L77) |
| GET | /api/summary | Query opcional owner: string; ausente o vacio usa el usuario autenticado. | 200; objeto con owner, total, byStatus y highPriorityOpen. | [app/main.py:90](../app/main.py#L90) |
| POST | /api/requirements | multipart/form-data con campo file obligatorio. | 201; objeto con owner, fileName, storedAt y size. | [app/main.py:107](../app/main.py#L107) |
| GET | /api/backend-health | Sin cuerpo ni parametros de consulta declarados. | 200; objeto con requestedBy, status y body, incluso cuando falla la consulta externa. | [app/main.py:114](../app/main.py#L114) |

### Task

La serializacion devuelve id (entero), title, description, status, owner, priority y createdAt (cadenas). createdAt corresponde a created_at de SQLite, generado con datetime('now'); no lleva sufijo de zona horaria. Referencia: [app/main.py:56](../app/main.py#L56).

POST /api/tasks toma title y description con valor predeterminado "", status con "TODO", priority con "MEDIUM" y owner con el usuario autenticado. Cada valor presente se convierte con str; no se validan enumeraciones, longitudes ni campos adicionales. Un null explicito se convierte actualmente en la cadena "None" y no activa el valor predeterminado. Referencia: [app/main.py:78](../app/main.py#L78).

### Summary

owner es una cadena; total es el numero de tareas del owner seleccionado; byStatus es un objeto de conteos enteros por cada estado encontrado. highPriorityOpen cuenta tareas con priority igual a "HIGH" y status distinto de "DONE" y "ARCHIVED". Sin tareas devuelve total y highPriorityOpen en 0 y byStatus vacio. Referencia: [app/main.py:91](../app/main.py#L91).

### Carga de requerimientos

owner procede de la identidad; fileName es el nombre recibido; storedAt es la representacion str de la ruta de destino; size es el numero entero de bytes leidos. Actualmente se devuelve la ruta de almacenamiento y no se persisten metadatos de la carga en SQLite. Referencia: [app/main.py:108](../app/main.py#L108).

### Estado del backend

requestedBy es el usuario autenticado. Si la peticion externa termina, status es el codigo HTTP del backend y body es su contenido decodificado como UTF-8. Ante cualquier Exception dentro del bloque try, status vale 0 y body contiene str(error); el HTTP de esta API sigue siendo 200. Referencia: [app/main.py:115](../app/main.py#L115).

## Flujo del token

1. Cada ruta inyecta legacy_identity mediante Depends; recibe Authorization, con "" como valor predeterminado.
2. Se elimina el texto literal "Bearer " con replace y se decodifica el resto como Base64 y UTF-8.
3. Se separan cuatro partes por el caracter `|`: usuario, rol, expiracion Unix en segundos y secreto. Se compara el secreto con LEGACY_SECRET y se rechaza si la expiracion es menor que int(time.time()). No hay verificacion criptografica de firma, emisor o audiencia.
4. Se devuelve un dict con username y role. Las rutas usan username; no comprueban role para autorizar owner.
5. Cualquier Exception durante la interpretacion produce HTTP 401 con JSON {"detail": "Invalid token: " + str(error)}. El detalle concreto depende del error.

Referencia: [app/main.py:14](../app/main.py#L14), [app/main.py:17](../app/main.py#L17). Este documento no establece el formato legacy como requisito de seguridad futuro.

## Flujo de SQLite

create_app selecciona db_path, o WORKSHOP_DB_PATH, o ./data/workshop.db, y crea su directorio. Abre una conexion por instancia de aplicacion con check_same_thread=False y row_factory sqlite3.Row, conservada en el cierre de las rutas y app.state.connection. No es una conexion nueva por peticion. Referencia: [app/main.py:29](../app/main.py#L29), [app/main.py:35](../app/main.py#L35), [app/main.py:46](../app/main.py#L46).

Se crea tasks con id autoincremental y columnas de texto no nulas title, description, status, owner, priority y created_at. Si la tabla esta vacia se insertan dos tareas de student y una de trainer y se hace commit. Referencia: [app/main.py:37](../app/main.py#L37).

GET /api/tasks ejecuta SELECT filtrado por owner y serializa cada fila. POST /api/tasks ejecuta INSERT, commit y SELECT por lastrowid. GET /api/summary ejecuta SELECT de status y priority por owner y agrega los datos en Python. Actualmente las consultas dinamicas concatenan valores. Referencia: [app/main.py:70](../app/main.py#L70), [app/main.py:84](../app/main.py#L84), [app/main.py:93](../app/main.py#L93).

El evento shutdown cierra la conexion. La instancia global app se construye al importar el modulo, por lo que importar puede crear directorios y la base de datos. Referencia: [app/main.py:123](../app/main.py#L123), [app/main.py:130](../app/main.py#L130).

## Flujo de archivos y acceso externo

create_app selecciona upload_dir, o WORKSHOP_UPLOAD_DIR, o ./uploads, y crea el directorio. La carga calcula Path(selected_uploads) / str(file.filename), lee el archivo entero con await file.read() y lo escribe con write_bytes. No hay controles propios de confinamiento, extension o tamano; si el destino existe se sobrescribe. Estos son comportamientos actuales inseguros, no obligaciones del contrato. Referencia: [app/main.py:31](../app/main.py#L31), [app/main.py:109](../app/main.py#L109).

backend_health consulta con urllib3.PoolManager el valor de AUTH_HEALTH_URL o http://localhost:8080/q/health mediante GET y timeout=3.0. No reenvia el token al backend. Este mapeo no requirio leer ni modificar otros componentes. Referencia: [app/main.py:116](../app/main.py#L116).

## Errores y documentacion automatica

Las entradas que no cumplen las declaraciones de FastAPI, por ejemplo un cuerpo obligatorio ausente o un multipart sin file, usan su respuesta de validacion 422 con detail. Salvo autenticacion y backend_health, no hay capturas locales para errores de SQL o escritura; no existe un formato de error propio declarado para ellos. Estas respuestas se documentan por lectura, no por pruebas de ejecucion en esta revision.

FastAPI tambien registra sus rutas automaticas /openapi.json, /docs, /docs/oauth2-redirect y /redoc, sin la dependencia legacy_identity de las rutas de negocio. Referencia: [app/main.py:45](../app/main.py#L45).
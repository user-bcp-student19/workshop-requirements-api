# Pruebas de API

Esta matriz se limita a las cinco rutas y respuestas de `docs/ENDPOINTS.md`.
Los errores se prueban con clientes y archivos temporales; `backend-health`
usa un mock para no realizar llamadas de red.

| endpoint | caso | tipo | resultado esperado |
|---|---|---|---|
| `GET /api/tasks` | `test_lists_seeded_tasks` | Camino feliz | HTTP 200; dos tareas student, orden ascendente y claves/tipos del modelo documentado. |
| `GET /api/tasks` | `test_empty_owner_filter_uses_authenticated_user` | Borde | `owner=` vacío usa la identidad autenticada y devuelve sus tareas. |
| `GET /api/tasks` | `test_all_endpoints_reject_invalid_token` | Error | HTTP 401 con `detail` para token inválido. |
| `POST /api/tasks` | `test_creates_task_and_summary` | Camino feliz | HTTP 201; tarea y claves documentadas; el resumen refleja la tarea persistida. |
| `POST /api/tasks` | `test_creates_task_with_default_values` | Borde | HTTP 201 con valores por defecto para description, status, priority y owner. |
| `POST /api/tasks` | `test_all_endpoints_reject_invalid_token` | Error | HTTP 401 con `detail` para token inválido. |
| `POST /api/tasks` | `test_create_task_requires_json_body` | Error | HTTP 422 con `detail` si falta el cuerpo requerido. |
| `POST /api/tasks` | `test_create_task_requires_object_body` | Error | HTTP 422 con `detail` si el cuerpo no es un objeto. |
| `GET /api/summary` | `test_creates_task_and_summary` | Camino feliz | HTTP 200 con owner, total, conteo por estado y highPriorityOpen correctos. |
| `GET /api/summary` | `test_summary_for_identity_without_tasks_is_empty` | Borde | HTTP 200; total 0, byStatus vacío y highPriorityOpen 0. |
| `GET /api/summary` | `test_all_endpoints_reject_invalid_token` | Error | HTTP 401 con `detail` para token inválido. |
| `POST /api/requirements` | `test_uploads_requirement_and_returns_metadata` | Camino feliz | HTTP 201; metadatos completos, tamaño exacto y bytes idénticos en el directorio temporal. |
| `POST /api/requirements` | `test_uploads_empty_file_as_zero_bytes` | Borde | HTTP 201 y size 0 para un archivo vacío. |
| `POST /api/requirements` | `test_all_endpoints_reject_invalid_token` | Error | HTTP 401 con `detail` para token inválido. |
| `POST /api/requirements` | `test_upload_requires_file_field` | Error | HTTP 422 con `detail` cuando falta el campo multipart `file`. |
| `GET /api/backend-health` | `test_backend_health_returns_upstream_response` | Camino feliz | HTTP 200 con requestedBy, status upstream 200 y body decodificado. |
| `GET /api/backend-health` | `test_backend_health_preserves_upstream_error_status` | Borde | La API responde HTTP 200 y conserva status upstream 503 y su body. |
| `GET /api/backend-health` | `test_all_endpoints_reject_invalid_token` | Error | HTTP 401 con `detail` para token inválido; no se consulta el upstream. |
| `GET /api/backend-health` | `test_backend_health_returns_zero_when_upstream_raises` | Error upstream | La API responde HTTP 200 con status 0 y el texto de la excepción, según el contrato actual. |

## Código ejecutable

El código completo ejecutado está en [tests/test_api.py](../tests/test_api.py).
Incluye los helpers `token` y `headers`, una fixture por prueba que crea SQLite
y uploads dentro de `tmp_path`, y mocks de `urllib3.PoolManager` en las pruebas
de `backend-health`. Los casos parametrizados de token inválido ejercitan las
cinco rutas.

## Comandos ejecutados

Directorio de ejecución: raíz del repositorio `workshop-requirements-api/`.
Intérprete que pudo ejecutar la suite: Python global 3.13.15; `pytest==9.0.2`
y `pytest-cov==7.0.0` estaban instalados globalmente. No se instalaron ni
modificaron dependencias.

| comando | código de salida | resultado |
|---|---:|---|
| `python -m pytest --cov=app --cov-report=term-missing` (línea base) | 0 | 4 passed; cobertura total 91%. |
| `python -m pytest --cov=app --cov-report=term-missing` (suite ampliada) | 0 | 18 passed; cobertura total 96%. |

### Medición de cobertura

Método: `pytest-cov` sobre `app`, usando `coverage.py` con ramas activadas por
`pyproject.toml` (`branch = true`, `source = ["app"]`). Se ejecutó el comando
anterior con `--cov-report=term-missing`; el reporte final indicó:

| alcance | sentencias | ramas | cobertura |
|---|---:|---:|---:|
| `app/main.py` | 95/96 | 16 ramas; 3 parciales | 96% |
| **TOTAL app** | **95/96** | **16 ramas; 3 parciales** | **96%** |

El porcentaje supera la meta de 85%. Las líneas no cubiertas fueron la rama de
token expirado y dos caminos de salida de `summary` que no se recorrieron en
esta matriz.

## Fallos de ejecución

- El intento con `\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing`
  terminó con código 1: el entorno virtual del repo no tiene pytest (`No module
  named pytest`). La suite se ejecutó con el intérprete global disponible, sin
  instalar paquetes.
- Una primera edición parcial de `tests/test_api.py` terminó con código 2 al
  colectar, por `IndentationError`; se reconstruyó el archivo y la suite final
  pasó. No queda un fallo de test abierto.
- La ejecución final emitió 39 warnings deprecativos de FastAPI `on_event` y
  Starlette/AnyIO. No se silenciaron.

## Pendientes

- H-02 sigue siendo un defecto del código: `owner` permite seleccionar tareas
  y resumen ajenos, y el cuerpo puede atribuir una tarea a otro owner. Esta
  suite no codifica esa fuga como resultado esperado ni afirma que esté
  corregida.
- H-04 sigue siendo un defecto del código: el nombre de carga no se confina ni
  valida. No se añadió una expectativa de status para nombres peligrosos porque
  el contrato actual no define ese rechazo ni sus códigos; las pruebas válidas
  mantienen todos los archivos bajo `tmp_path`.
- No se probó una desconexión durante la carga ni una caída real del backend;
  las excepciones de upstream se simulan de forma determinista.

## Pruebas propuestas

- Para H-02, tras acordar e implementar la autorización: regresiones que envíen
  `owner` de otra identidad a list/summary y en create_task, verificando que la
  respuesta y la persistencia se limiten siempre al username autenticado.
- Para H-04, después de definir en el contrato límites y respuestas: pruebas de
  traversal POSIX/Windows, colisiones, extensiones, límite exacto y exceso,
  ausencia de escritura fuera de `upload_dir` y limpieza tras fallo.
- Para subir cobertura restante: token expirado y los caminos alternativos de
  `summary`, sin cambiar el comportamiento declarado.

## Documentos consultados

- `docs/ENDPOINTS.md` — rutas, entradas, respuestas y comportamientos actuales.
- `docs/GOOD_PRACTICES.md` — criterios de seguridad y estructura.
- `REGLAS.md` — meta de cobertura y restricciones de laboratorio.
- `HALLAZGOS.md` — confirmación de H-02 y H-04 como pendientes.
- `pyproject.toml`, `requirements-dev.txt` y `tests/test_api.py` — configuración
  de pruebas, herramientas instaladas y suite existente.
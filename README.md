# SpecRel — Red de referencias cruzadas entre secciones de especificaciones

Aplicación de escritorio (Windows, Python 3.12 + PyQt6) para registrar y visualizar las
relaciones entre secciones de especificaciones tipo MasterFormat de un proyecto.

- **Tabla de relaciones** (izquierda): `Sección A | Tipo de relación | Sección B`, con
  autocompletado por número o descripción, creación automática de secciones y prevención de duplicados.
- **Mapa de referencias** (pestaña 2D): lienzo libre con nodos octogonales coloreados por categoría y
  flechas ortogonales que salen por arriba/derecha y entran por abajo/izquierda. Los nodos se mueven
  libremente, las conexiones los siguen y la geometría de cada línea puede ajustarse a mano.
- **Vista 3D**: nube de nodos y aristas (pyqtgraph + OpenGL) para explorar la red completa.
- **Análisis**: secciones huérfanas, secciones con mayor interacción, impacto de modificar una sección
  y grupos aislados, con resaltado en el mapa.
- **Un archivo por proyecto** (`.specrel`, SQLite). Sin base de datos central ni red. Los cambios se
  guardan automáticamente (la barra de estado muestra la hora del último guardado); "Guardar" (Ctrl+S) solo
  confirma, y "Guardar copia como…" duplica el proyecto en otro archivo (no admite el mismo archivo abierto).
- **Exportación** del mapa a PNG, SVG o portapapeles.

## Ejecutar en desarrollo

```powershell
py -3.12 -m venv venv
.\venv\Scripts\pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\venv\Scripts\python main.py
```

Pruebas:

```powershell
.\venv\Scripts\python -m pytest -q
```

## Variables de entorno (`.env`)

| Variable | Descripción |
|---|---|
| `DEBUG_MODE` | `true` para trazas adicionales |
| `DEFAULT_CATALOG_PATH` | Catálogo (CSV/XLSX/SQLite MasterFormat) que se importa al crear un proyecto nuevo |
| `RECENT_FILES_MAX` | Cantidad de proyectos recientes a recordar |
| `OPENGL_SOFTWARE` | `true` fuerza OpenGL por software (escritorio remoto, drivers antiguos) |

## Manual integrado

**Ayuda → Manual de uso** (F1) abre el manual dentro de la aplicación en el tema de la pestaña activa, con
índice, buscador e imágenes. El contenido está en `assets/help/*.md` (Markdown) con su índice
`assets/help/index.json`; las imágenes se regeneran con `scripts/help_screenshots.py`. La barra de estado
muestra una pista la primera vez que se activa *Conectar*, *Ajustar a rejilla* o se ocultan avance y
responsables.

## Uso rápido

1. **Archivo → Nuevo proyecto…**: elija dónde guardar el `.specrel`, indique código y nombre.
2. Escriba en *Sección A* (p. ej. `31 23 00 Excavación`), elija el tipo de relación, escriba
   *Sección B* y presione **Enter**. Las secciones inexistentes se crean con la categoría por defecto.
3. En el mapa: arrastre nodos; rueda = zoom; botón medio o Espacio + arrastre = desplazar;
   **C** o el botón *Conectar* (o Alt + arrastre) crea relaciones entre nodos; doble clic en una
   flecha agrega un punto de quiebre; clic derecho abre opciones (tipo, dirección, puertos, eliminar).
4. **Edición → Categorías…** para cambiar nombres y colores. Cada sección puede además tener un
   color propio (doble clic en el nodo → "Color: Personalizar", o clic derecho → "Color de la sección");
   "Usar el color de la categoría" lo quita. **Importar catálogo…** para alimentar el
   autocompletado desde CSV/XLSX o desde `master_format.db` (tabla `master_format`).
5. **Archivo → Exportar** (o el botón *Exportar* de la barra): mapa 2D y vista 3D a PNG, SVG o
   portapapeles. El PNG 3D se renderiza al doble de resolución con la cámara actual; el SVG 3D es una
   proyección vectorial (círculos, líneas y etiquetas) de esa misma cámara.

## Elegir secciones MasterFormat

La aplicación incluye el catálogo MasterFormat 2020 (8.790 secciones, `assets/data/masterformat_2020.sqlite`,
generado con `scripts/build_master_catalog.py` a partir de `info/master_format_data.xlsx`).

- En **Sección A / Sección B** se escribe para filtrar y se **elige** de la lista; el texto libre no crea
  secciones. Un código con espacios mal puestos (`0330 00`) encuentra igual `03 30 00` y Enter lo toma.
- El **panel «Secciones MasterFormat»** (F4) muestra el árbol División › nivel 2 › 3 › 4 con buscador.
  Doble clic agrega la sección al proyecto; también se puede arrastrar al mapa para ubicarla, o usar el
  clic derecho para ponerla como Sección A o B. Un punto verde marca las que ya están en el proyecto y
  «⚠» los títulos que el catálogo trae con ruido de extracción.
- Los códigos que no están en MasterFormat (p. ej. `4.28.33`) se crean con **Sección personalizada…**.
  Si el número coincide con el catálogo, el cuadro sugiere la entrada canónica.
- Los títulos vienen en inglés y son editables por sección. **Edición → Catálogo MasterFormat →
  Reemplazar…** acepta un Excel/CSV con columnas `codigo_display`/`Número`, `nombre`/`Descripción`, opcional
  `title_es` y `nivel`; la copia se guarda en `%APPDATA%\SpecRel\` y aplica a todos los proyectos.
  «Restaurar catálogo incluido» vuelve al empaquetado.

### Editar el catálogo

- **Desde el panel** (clic derecho → *Editar catálogo*): editar título (inglés y español), agregar una sección
  hija (el padre y la clasificación se derivan del número), ocultar una sección o eliminar una agregada, y
  restaurar la entrada original. La casilla «Mostrar ocultas» permite recuperar secciones ocultas. Las
  ediciones se guardan en `%APPDATA%\SpecRel\catalog_edits.json`, aplican a todos los proyectos, no tocan
  el catálogo incluido y se revierten con *Quitar todas las ediciones del catálogo*. Las secciones ya
  creadas en los proyectos nunca cambian por editar el catálogo.
- **Con Excel**: *Edición → Catálogo MasterFormat → Exportar catálogo a Excel…* produce un libro con
  Número, Descripción, `title_es`, Nivel, Categoría, Calidad y Oculta; edítelo y cárguelo con
  *Reemplazar catálogo MasterFormat…*. La copia queda en el perfil del usuario.
- **Para todos los usuarios**: edite `info/master_format_data.xlsx`, `scripts/title_overrides.csv` o
  `scripts/category_rules.csv`, ejecute `scripts/build_master_catalog.py` y recompile.

## Estatus, avance, responsables y observaciones

Cada sección del proyecto tiene además **estatus** (lista configurable: No iniciada, En elaboración, En
revisión, Aprobada, Emitida), **avance** (0–100 %), **responsables** (unidades como INIO, INIG, INIE, INI-PY,
INIC; lista configurable con color) y **observaciones**.

- En el mapa, sobre cada octágono aparecen los responsables como círculos con su código y color, y debajo
  la barra de avance con el porcentaje (coloreada según el estatus) y el nombre del estatus. **Ver →
  Mostrar avance y responsables** (F6) los oculta para exportar mapas limpios.
- Se editan con doble clic en el nodo, con el clic derecho (submenús Estatus, Responsables y Avance) o en
  la pestaña **Secciones**, que lista todas las secciones con columnas editables en línea, filtro y orden.
- **Edición → Responsables…** y **Edición → Estatus…** administran las listas (agregar, editar, color,
  borrar con aviso de uso, reordenar). Se guardan dentro del `.specrel`; los proyectos nuevos nacen con
  las listas iniciales.
- La pestaña Análisis muestra el avance promedio y una tabla de avance por responsable.
- Las tablas Excel/CSV incluyen Estatus, Avance, Responsables (códigos separados por coma) y Observaciones;
  al importar se crean los estatus y responsables desconocidos.

## Clasificación de secciones (colores)

Cada sección del catálogo trae una **clasificación por defecto** que define su color al crearla:

| Categoría | Color | Ramas MasterFormat |
|---|---|---|
| Técnica / constructiva | verde | Divisiones 03 a 49, 01 75, 01 80–01 89, 02 01/03/05, 02 40–02 87 |
| Contractual | amarillo | División 00; 01 10–01 33, 01 60–01 66, 01 70/71/73/77/78/79 |
| Auxiliar / apoyo | azul | 01 35, 01 40–01 45, 01 50–01 58, 01 74, 01 76, 01 90–01 94; 02 20–02 32; y en toda división `XX 01` (operación y mantenimiento), `XX 06` (schedules), `XX 08` (commissioning) |

Las reglas están en `scripts/category_rules.csv` (prefijo más largo gana; `??` = cualquier división) y se
aplican al construir el catálogo. Para corregirlas sin recompilar: en el panel MasterFormat, clic derecho →
**Clasificación por defecto** → categoría → "solo esta sección" o "esta sección y su rama". Las correcciones
se guardan en `%APPDATA%\SpecRel\category_overrides.json` y valen para todos los proyectos; un recuadro azul
alrededor de la muestra indica que el nodo fue corregido. **Edición → Catálogo MasterFormat → Aplicar
clasificación del catálogo…** reasigna las secciones ya creadas (conserva colores personalizados). Los
colores y nombres de las categorías se editan en **Categorías…**; una sección puede además tener color propio.

## Reporte de secciones en Excel

**Archivo → Exportar → Reporte de secciones (Excel)…** (Ctrl+R) genera un libro de solo lectura con hojas
Resumen (indicadores y tablas por estatus, responsable y categoría), Secciones (estatus, avance con barra de
datos, responsables, observaciones, grados de referencia), Por responsable (una fila por sección y unidad),
Relaciones y, opcionalmente, Mapa con la imagen del mapa 2D. Generado por `models/report_export.py`.

## Armar un proyecto desde Excel o CSV

1. **Archivo → Tablas → Guardar plantilla de Excel…** (también desde la pantalla de inicio). La plantilla
   tiene las hojas `Secciones` (Número, Descripción, Categoría, Color), `Relaciones` (Sección A, Relación,
   Sección B) e `Instrucciones`, con filas de ejemplo. La columna Relación tiene lista desplegable.
2. Complete las tablas. Las secciones se pueden escribir como `03 30 00` o `03 30 00 - Concreto`; en
   Relación se aceptan los tres textos de la app y también `->`, `<-`, `<->` o `mutua`.
3. Cree o abra un proyecto y use **Archivo → Tablas → Importar tablas (CSV/Excel)…** (Ctrl+I). Las
   secciones nuevas se crean, las existentes se actualizan y las categorías desconocidas se crean. Nada
   se elimina. Al final se muestra un resumen.
4. **Exportar tablas a Excel…** guarda el proyecto actual en el mismo formato, editable y re-importable.

## Convenciones del modelo

- Se guarda una sola relación por par de secciones. "← Es referenciada por" se almacena invertida como
  "Hace referencia a →". Registrar la relación inversa a una existente propone convertirla en mutua.
- *Impacto*: si **B** cambia, se ven afectadas las secciones que hacen referencia a B (ancestros en el
  grafo). "Depende de" lista las secciones a las que B hace referencia.

## Archivos en OneDrive

SQLite no convive bien con carpetas sincronizadas mientras la sincronización está activa. El archivo
usa `journal_mode=DELETE`, `synchronous=NORMAL`, un `busy_timeout` corto (1,5 s) y un reintento, pero se
recomienda marcar el `.specrel` como "Mantener siempre en este dispositivo" o trabajar en una carpeta
local; la aplicación lo recuerda en la barra de estado al abrir un proyecto desde OneDrive. Si aun así el
archivo está bloqueado, el cambio no se guarda y se muestra un aviso (la aplicación no se cierra). Al abrir
un proyecto se conservan 3 copias de respaldo (`.bak1`…`.bak3`) junto al archivo.

## Rendimiento y trabajo en segundo plano

Reglas que mantienen la interfaz respondiendo (fase 8):

- El hilo principal solo hace trabajo corto. Lo pesado y puro corre en `QThreadPool` mediante
  `utils/workers.py` (`run_in_background`, `run_with_progress`): leer tablas Excel, exportar tablas y el
  reporte (sobre un `ProjectModel.snapshot()`, nunca sobre el modelo vivo ni su conexión SQLite),
  construir un catálogo reemplazado y calcular la disposición 3D (`layout3d`). Scipy se precalienta en un
  hilo al arrancar.
- Los oyentes costosos (autocompletado, análisis, marcas del árbol, 3D, repintado de nodos) se coalescen
  con `utils/debounce.Debouncer`: una importación de 300 filas los ejecuta una vez, no 300.
- Las importaciones escriben en una sola transacción (`ProjectModel.bulk()`) y muestran un diálogo de
  progreso; abrir proyectos y poblar el mapa muestran cursor de espera.
- El autocompletado no ordena en Python: el modelo ya viene ordenado y las consultas numéricas muestran
  primero solo coincidencias por prefijo. Filtrar cuesta ~10 ms por tecla (antes ~330 ms).
- Diagnóstico: con `DEBUG_MODE=true` en el `.env`, `utils/perf.FreezeWatchdog` registra en
  `%APPDATA%\SpecRel\perf.log` cualquier bloqueo del hilo principal mayor de 400 ms con la pila del
  código responsable. Pida ese archivo al usuario que reporte «No responde».

## Empaquetado

```powershell
.\venv\Scripts\pyinstaller specrel.spec --noconfirm
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.1.0 setup.iss
```

El workflow `.github/workflows/release.yml` ejecuta pruebas, PyInstaller e Inno Setup y publica el
instalador al crear una etiqueta `vX.Y.Z`.

## Estructura

```
config/       settings.py, palette.py
models/       schema, database, entities, relation_normalizer, repositories, graph_engine,
              layout_engine, catalog_importer, project_model, relations_table_model,
              section_completer_model
utils/        debounce.py (coalescencia), workers.py (hilos + progreso), perf.py (vigilante de bloqueos)
views/        main_window.py, styles/theme.qss, components/ (tabla, diálogos, análisis, 3D, canvas/)
controllers/  main, relations, canvas, analysis, view3d, export
tests/        pruebas unitarias (modelo, router) y de humo (GUI offscreen)
```

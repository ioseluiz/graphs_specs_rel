# Preguntas frecuentes

## ¿Qué hace el botón «Conectar»?

Activa un modo para crear relaciones directamente en el mapa: arrastre desde una sección hasta otra y
elija el tipo de relación en el menú que aparece. Presione Esc para salir. También puede mantener Alt y
arrastrar sin activar el modo. Vea *Mapa de referencias*.

## ¿Qué hace «Ajustar a rejilla»?

Cuando está activado, el nodo que usted arrastra se acomoda al punto más cercano de una cuadrícula de 10
píxeles al soltarlo. Sirve para que los nodos queden alineados en filas y columnas y las flechas salgan rectas.
No mueve nodos por sí solo ni cambia los que ya estaban colocados. «Mostrar rejilla» solo muestra u oculta las
líneas del fondo. Vea *Mapa de referencias*.

## Escribí una sección y no se creó

Los campos Sección A y B solo aceptan secciones elegidas de la lista, para evitar errores de tipeo. Escriba
parte del número o del título y elija una opción. Si la sección no es MasterFormat (por ejemplo `4.28.33`),
use **Sección personalizada…**.

## ¿Cómo invierto una relación o cambio su tipo? Elegí «Es referenciada por» y la fila volvió a decir «Hace referencia a»

La fila siempre muestra *origen → destino*. Al invertir, A y B se intercambian y la celda vuelve a decir
«Hace referencia a →»: el cambio se aplicó, y la barra de estado muestra el antes y el después. Lo más directo
es el icono **⇄** de la fila, la opción *Invertir dirección* de la celda Relación, o en el mapa la tecla **R**
con la flecha seleccionada (o clic derecho sobre ella). Para pasar a mutua o volver a dirigida use la celda
Relación o el clic derecho en la flecha. Vea *Relaciones*.

## Registré «A → B» y la app me preguntó si quería una relación mutua

Ya existía «B → A». Solo puede haber una relación entre dos secciones; la app propone unirlas en una
referencia mutua ↔ en lugar de duplicarlas.

## Las flechas se cruzan o pasan sobre otros nodos

Es intencional: la aplicación no mueve sus nodos ni impide cruces. Para corregir un trazado, arrastre los
nodos, agregue puntos de quiebre con doble clic sobre la flecha o fije el puerto de salida/entrada desde el
clic derecho.

## El archivo está bloqueado o «posiblemente OneDrive»

SQLite no convive bien con carpetas sincronizadas mientras OneDrive trabaja. Espere unos segundos y
reintente, marque el archivo como «Mantener siempre en este dispositivo» o trabaje en una carpeta local.
Si el archivo está bloqueado en el momento de un cambio, la aplicación avisa y ese cambio no se guarda;
repita la acción cuando termine la sincronización. Al abrir un proyecto se guardan tres copias de respaldo
`.bak1`–`.bak3` junto al archivo.

## La aplicación se detiene o muestra «No responde»

Las operaciones largas (leer un Excel, generar el reporte, reemplazar el catálogo, calcular la
disposición 3D) se ejecutan en segundo plano y muestran un diálogo de progreso o el mensaje «Calculando
disposición 3D…»; la ventana sigue respondiendo. Al importar tablas grandes, el mapa se va poblando con
una barra de avance. Si aun así nota pausas:

- Con el proyecto en OneDrive, marque el archivo como «Mantener siempre en este dispositivo».
- En proyectos muy grandes, oculte responsables y avance (F6) para agilizar el mapa.
- Para diagnosticar, cree un archivo `.env` junto al ejecutable con `DEBUG_MODE=true`: cada pausa mayor
  de 0,4 s queda registrada en `%APPDATA%\SpecRel\perf.log` (la ruta se muestra en *Ayuda → Acerca de*).
  Envíe ese archivo con su reporte.

## Los títulos del catálogo están en inglés

El catálogo MasterFormat 2020 se distribuye en inglés. Puede editar el título de una sección del proyecto
(doble clic en el nodo) o agregar el título en español en el catálogo (clic derecho → *Editar catálogo →
Editar título…*). Algunos títulos aparecen como «(título por verificar)» porque llegaron incompletos en la
fuente; edítelos igual.

## ¿Dónde se guarda mi trabajo? ¿Por qué no hay «Guardar como»?

En el archivo `.specrel` del proyecto, automáticamente después de cada cambio; la barra de estado muestra la
hora del último guardado. **Guardar** (Ctrl+S) confirma e indica la ruta. **Guardar copia como…** crea un
duplicado en otro archivo y no admite el mismo archivo abierto (ya está guardado). Las correcciones al
catálogo y a su clasificación se guardan en su perfil de usuario (`%APPDATA%\SpecRel`).

## No veo la vista 3D

Requiere OpenGL. Cree un archivo `.env` junto a `SpecRel.exe` con `OPENGL_SOFTWARE=true`. Vea *Vista 3D*.

## ¿Cómo obtengo un reporte de avance por responsable?

**Archivo → Exportar → Reporte de secciones (Excel)…** (Ctrl+R). La hoja *Resumen* trae la tabla por
responsable (secciones, avance promedio, al 100 %, en curso) y la hoja *Por responsable* lista cada sección con
su unidad, para filtrar. Vea *Exportar e importar*.

## ¿Cómo llevo el mapa a un informe?

**Archivo → Exportar → Mapa 2D como PNG** para imagen, **SVG** para editar, o *Copiar al portapapeles* para
pegar directamente en Word o PowerPoint. Oculte avance y responsables (F6) si quiere un mapa limpio.

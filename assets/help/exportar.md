# Exportar e importar

## Imágenes del mapa y de la vista 3D

**Archivo → Exportar** (o el botón *Exportar* de la barra, que exporta la pestaña activa como PNG):

| Opción | Resultado |
|---|---|
| Mapa 2D como PNG | Imagen nítida del mapa completo, sin rejilla ni selección |
| Mapa 2D como SVG | Vectorial, editable en Inkscape, Illustrator o Visio |
| Copiar mapa 2D | Al portapapeles, para pegar en Word o PowerPoint |
| Vista 3D como PNG / SVG / copiar | Con la cámara actual |

Para un mapa sin responsables ni barras de avance, desactive antes *Ver → Mostrar avance y responsables* (F6).

## Reporte de secciones en Excel

**Archivo → Exportar → Reporte de secciones (Excel)…** (Ctrl+R) genera un libro para leer y compartir:

| Hoja | Contenido |
|---|---|
| Resumen | Datos del proyecto y fecha; indicadores (secciones, relaciones, avance promedio, al 100 %, en curso, sin avance, sin responsable); tablas por estatus, por responsable y por categoría, con sus colores |
| Secciones | Una fila por sección: número, descripción, categoría, estatus, avance con barra, responsables, observaciones, cuántas referencia y por cuántas es referenciada, última actualización. Con filtros y paneles congelados |
| Por responsable | Una fila por sección y responsable, para filtrar por unidad o armar tablas dinámicas |
| Relaciones | Sección A, sentido (→ o ↔), Sección B y sus categorías |
| Mapa (opcional) | Imagen actual del mapa 2D, tal como se ve (con o sin avance y responsables según F6) |

El diálogo propone el nombre `{código}_reporte_secciones_{fecha}.xlsx` en la carpeta del proyecto y puede
abrir el archivo al terminar. Si Excel tiene abierto un reporte anterior con el mismo nombre, ciérrelo antes.
Este reporte es de solo lectura; para editar en Excel y reimportar use *Tablas → Exportar tablas a Excel…*.

## Armar un proyecto desde Excel o CSV

1. **Archivo → Tablas → Guardar plantilla de Excel…** (también en la pantalla de inicio). La plantilla tiene
   las hojas *Secciones* (Número, Descripción, Categoría, Color, Estatus, Avance, Responsables,
   Observaciones), *Relaciones* (Sección A, Relación, Sección B) e *Instrucciones*.
2. Complete las tablas. Las secciones pueden escribirse como `03 30 00` o `03 30 00 - Concreto`. En
   Relación acepta los textos de la app y también `->`, `<-`, `<->`, `mutua`. Responsables: códigos separados
   por coma.
3. Abra o cree un proyecto y use **Archivo → Tablas → Importar tablas (CSV/Excel)…** (Ctrl+I). Las secciones
   nuevas se crean, las existentes se actualizan, y los estatus, responsables y categorías desconocidos se
   crean. Nada se elimina. Al final se muestra un resumen.

## Exportar las tablas del proyecto

**Archivo → Tablas → Exportar tablas a Excel…** guarda secciones y relaciones en el formato de la plantilla:
sirve como reporte y para editar en Excel y volver a importar.

## Catálogo MasterFormat

**Edición → Catálogo MasterFormat → Exportar catálogo a Excel…** y **Reemplazar catálogo MasterFormat…**
permiten revisar y sustituir el catálogo completo (ver *Secciones y catálogo*).

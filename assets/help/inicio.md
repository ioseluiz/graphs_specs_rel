# Inicio rápido

**SpecRel** registra y dibuja las relaciones entre las secciones de las especificaciones de un proyecto
(formato MasterFormat). Sirve para ver de un vistazo qué sección hace referencia a cuál, quién es responsable
de cada una, cuánto avance lleva y qué impacto tendría cambiarla.

![Mapa de referencias](img/mapa.png)

## Cómo se organiza la pantalla

- **Panel izquierdo «Secciones MasterFormat»** (F4): el catálogo completo para buscar y elegir secciones.
- **Entrada de relaciones**: Sección A, tipo de relación y Sección B. Enter agrega la relación.
- **Relaciones registradas**: la tabla con todas las relaciones; se editan y eliminan ahí.
- **Pestañas de la derecha**: *Mapa de referencias* (lienzo libre), *Vista 3D*, *Secciones* (tabla de
  secciones con estatus, avance y responsables) y *Análisis*.

## Un proyecto en cinco pasos

1. **Archivo → Nuevo proyecto…** Elija dónde guardar el archivo `.specrel` e indique código y nombre.
   Cada proyecto es un único archivo; no hay base de datos central. **Atajo:** si ya tiene las secciones y
   relaciones en la plantilla de Excel, arrastre el archivo sobre la ventana (o pulse *Crear mapa desde
   Excel/CSV…*): el proyecto se crea junto al Excel y el mapa aparece acomodado. Vea *Exportar e importar*.
2. En **Sección A** escriba parte del número o del título, por ejemplo `31 23` o `excav`, y elija de la
   lista. Repita en **Sección B**.
3. Elija el **tipo de relación** (→ o ←) y presione **Enter** o **Agregar**. Las secciones que no existían
   en el proyecto se crean solas con la clasificación y el color del catálogo. Si dos secciones se referencian
   entre sí, registre ambas direcciones: serán dos flechas.
4. En el **Mapa** acomode las secciones arrastrándolas. Las flechas siguen a los nodos. También puede crear
   relaciones directamente en el mapa con **Conectar**.
5. Registre **estatus, avance y responsables** de cada sección (doble clic en el nodo o pestaña *Secciones*)
   y exporte el mapa como imagen desde **Archivo → Exportar**.

## Guardado

Todos los cambios se escriben **automáticamente** en el archivo del proyecto en el momento en que los hace;
la barra de estado muestra la hora del último guardado. **Guardar** (Ctrl+S) solo confirma que todo está
escrito e indica la ruta del archivo. **Guardar copia como…** crea un duplicado en otro archivo; no sirve
para «guardar» el proyecto abierto, que ya está guardado. Al abrir un proyecto se conservan tres copias de
respaldo (`.bak1`, `.bak2`, `.bak3`) junto al archivo.

## Dónde encontrar ayuda

- Presione **F1** en cualquier momento: se abre este manual en el tema de la pestaña activa.
- Pase el mouse sobre cualquier botón para ver una descripción breve.
- La barra de estado (abajo) muestra pistas al activar un modo, por ejemplo *Conectar*.

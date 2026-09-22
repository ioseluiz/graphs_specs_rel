# Relaciones

Una relación une dos secciones e indica **quién hace referencia a quién**. Se registra en la entrada de la
izquierda o directamente en el mapa con *Conectar*.

![Entrada de relaciones](img/entrada.png)

## Los dos tipos

| Usted elige | Significa | Se dibuja |
|---|---|---|
| **Hace referencia a →** | A menciona a B (A → B) | flecha de A hacia B |
| **← Es referenciada por** | B menciona a A (B → A) | flecha de B hacia A |

El tipo define el sentido sin importar en qué campo puso cada sección. Por eso
«33 40 00 ← Es referenciada por 31 23 00» se guarda y se muestra como «31 23 00 → 33 40 00».

**Cada dirección es una flecha independiente.** Si A hace referencia a B **y** B hace referencia a A, registre
las dos relaciones: en el mapa verá dos flechas, cada una con su inicio y su punta. (En versiones anteriores esto
era una sola línea «mutua» con dos puntas; los proyectos antiguos se convierten automáticamente en dos flechas
al abrirlos.)

## Registrar una relación

1. Elija **Sección A** de la lista (vea *Secciones y catálogo*).
2. Elija el **tipo**.
3. Elija **Sección B** y presione **Enter** o **Agregar**.

Si alguna sección no existía en el proyecto, se crea automáticamente con la clasificación del catálogo y
aparece en el mapa cerca de la otra.

## Relaciones duplicadas

Solo puede existir **una** relación por cada dirección entre dos secciones:

- Si repite exactamente la misma relación (A → B otra vez), la app avisa que ya existe y la selecciona.
- La relación **inversa** (B → A) no es un duplicado: se agrega como segunda flecha sin preguntar.
- Desde el mapa, el clic derecho sobre una flecha ofrece **Agregar flecha inversa** cuando aún no existe.

## Seleccionar una flecha

Al hacer clic sobre una flecha, esta se dibuja más gruesa con un halo azul y un punto en su origen, y las dos
secciones que une se remarcan (borde azul y relleno más oscuro). La barra de estado indica «Flecha seleccionada:
A → B» y la fila correspondiente se selecciona en la tabla. Clic en un espacio vacío quita la selección.

## Invertir la dirección

La fila de la tabla y la flecha del mapa muestran **siempre** la relación como *origen → destino*. Por eso, al
invertir, las columnas A y B se intercambian y la celda *Relación* sigue diciendo «Hace referencia a →»: el
cambio sí se aplicó (la barra de estado lo confirma con el antes y el después, y la fila se resalta un momento).

![Acciones de la fila](img/acciones.png)

Tiene tres caminos:

1. **Icono ⇄ en la fila** (columna de acciones): invierte la dirección con un clic.
2. **Celda «Relación»**: un clic abre la lista con *Hace referencia a →* e *Invertir dirección (B → A)*.
3. **En el mapa**: clic derecho sobre la flecha muestra la relación actual con sus números y la opción
   *Invertir dirección*. Con la flecha seleccionada, la tecla **R** también la invierte.

Si ya existe la flecha en sentido contrario, invertir queda deshabilitado (sería un duplicado exacto); elimine
una de las dos o selecciónela desde el mismo menú.

## Editar y eliminar

- En **Relaciones registradas**, doble clic en *Sección A* o *Sección B* permite cambiar la sección; la
  flecha se mueve al nuevo destino.
- El lápiz ✎ edita las secciones; el bote 🗑 elimina (con confirmación). También puede seleccionar filas y
  presionar **Supr**.
- En el mapa, clic derecho sobre una flecha: además de lo anterior, *Agregar punto de quiebre*, *Restablecer
  ruta*, *Puerto de salida / entrada* y *Eliminar relación*.
- Seleccionar una fila resalta la flecha en el mapa, y seleccionar una flecha o nodo resalta sus filas.
- Las **observaciones** de una relación (columna Observaciones de la plantilla) se muestran al pasar el mouse
  sobre la flecha.

## Estilo de la flecha

Cada flecha puede tener **color, trazo y grosor** propios, como en otras aplicaciones de diagramas. Clic derecho
sobre la flecha → **Estilo de la flecha**:

- **Color**: paleta de ocho colores, *Personalizar…* (cualquier color) o *Color predeterminado* (azul).
- **Trazo**: continua, discontinua, punteada o punto y raya. La punta de la flecha siempre es sólida.
- **Grosor**: Fina (1 px), Normal (1,6 px), Gruesa (2,5 px) o Muy gruesa (4 px).
- **Estilo de línea…** abre un cuadro con los tres controles y una vista previa.
- **Restablecer estilo** vuelve al estilo predeterminado.

Si selecciona varias flechas (Ctrl + clic o arrastre de selección) y hace clic derecho sobre una de ellas, el
submenú dice «Estilo de las N flechas seleccionadas» y el cambio se aplica a todas.

Al seleccionar una flecha con color propio, el color se oscurece y aparece el halo; el resaltado rojo del
Análisis de impacto prevalece sobre cualquier estilo. La tabla *Relaciones registradas* muestra una muestra de
la línea entre los códigos A y B. La vista 3D refleja solo el color. El estilo se exporta en PNG/SVG y viaja por la
plantilla Excel en las columnas opcionales **Color | Trazo | Grosor** de la hoja Relaciones.

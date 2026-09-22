# Cláusulas del pliego

Además de las secciones MasterFormat, el mapa puede incluir **cláusulas del pliego de cargos** (numeración
`4.28.N`) y sus **subcláusulas** (`4.28.N.M`). Son un tipo de nodo distinto:

| | Sección MasterFormat | Cláusula |
|---|---|---|
| Forma | octágono | rectángulo redondeado |
| Color | según su categoría | rosado (categoría fija «Cláusula») |
| Estatus, avance, responsables | sí | **no** |
| Relaciones (flechas) | sí | sí, en ambos sentidos |
| Etiqueta | número y descripción | numeración y título (completo al pasar el mouse) |

Una cláusula **solo se conecta y muestra su etiqueta**. No aparece en los promedios de avance, en la hoja
«Por responsable» del reporte ni en las listas por estatus.

## Dónde están

En el panel lateral **Secciones MasterFormat** (F4), al final del árbol, bajo la raíz **«Cláusulas 4.28»**: cada
cláusula despliega sus subcláusulas. El buscador del panel y los campos *Sección A / Sección B* también las
encuentran: escriba parte de la numeración (`4.28.61`) o del título (`pago final`).

## Agregar una cláusula al mapa

- **Doble clic** sobre la cláusula en el panel, o **arrástrela** al lugar del mapa donde la quiere.
- Elíjala en *Sección A* o *Sección B* de la entrada de relaciones: se crea al registrar la relación.
- Desde Excel: en la plantilla, una fila cuyo Número sea una numeración de cláusula (o cuya Categoría diga
  «Cláusula») se carga como cláusula; las columnas Estatus, Avance y Responsables se ignoran y se informa en el
  resumen. Vea *Exportar e importar*.

## Qué se puede editar

Doble clic en el nodo (o *Editar cláusula…* en el clic derecho): título, color y observaciones. La categoría es
fija y no hay estatus, avance ni responsables; en la pestaña *Secciones* esas celdas aparecen vacías y no se
editan. La tecla **F6** (mostrar avance y responsables) no cambia las cláusulas.

## Actualizar la lista de cláusulas

La lista viene incluida en la aplicación (la entregó el cliente). Para reemplazarla:
**Edición → Catálogo MasterFormat → Reemplazar catálogo de cláusulas…** y elija un Excel o CSV con las columnas
**Numeración | Título | Tipo** (Tipo: `Cláusula` o `Subcláusula`; si falta, se deduce de la numeración). La copia se
guarda en su perfil de usuario y se usa en todos los proyectos; **Restaurar cláusulas incluidas** vuelve a la
lista original.

Consejos para el Excel:

- La columna Numeración debe ser **texto**: una celda numérica `4.10` llega como `4.1`.
- Los números de página pegados al título («50PAGO FINAL») se limpian automáticamente.
- `4.28.3.1` y `4.28.31` son numeraciones distintas: la aplicación las distingue.

## Proyectos anteriores

Al abrir un proyecto creado con una versión anterior, las secciones con numeración `4.28.x` se convierten en
cláusulas: pierden estatus, avance y responsables y pasan a la categoría «Cláusula». La categoría «Otra» deja el
rosado (ahora reservado a las cláusulas) y pasa a gris. Se conservan los respaldos `.bak` junto al archivo.

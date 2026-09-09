# Vista 3D

La pestaña **Vista 3D** muestra la misma red como una nube de puntos en tres dimensiones. Sirve para
explorar la estructura general; la edición se hace en el mapa 2D y en las tablas.

## Uso

- **Orbitar**: arrastre con el botón izquierdo. **Zoom**: rueda del mouse. **Desplazar**: botón central.
- **Restablecer vista** vuelve a encuadrar toda la red.
- **Recalcular disposición** genera otra distribución de los puntos (la anterior se conserva hasta entonces y
  se guarda con el proyecto).
- **Mostrar todas las etiquetas**: por defecto solo se etiquetan las secciones con más relaciones.
- El color de cada punto es el de su sección. Las líneas van de un tono tenue en el origen a uno intenso en
  el destino para indicar la dirección. Cuando existen las dos flechas entre un mismo par de secciones, se
  dibujan ligeramente separadas, una a cada lado.
- El resaltado de impacto de la pestaña Análisis también se refleja aquí.

## Exportar

**Archivo → Exportar → Vista 3D como PNG / SVG** o *Copiar vista 3D al portapapeles*. El PNG conserva la
cámara actual al doble de resolución; el SVG es una proyección vectorial editable.

## Si la vista 3D no aparece

Requiere OpenGL. En equipos sin aceleración gráfica o por escritorio remoto puede mostrar un aviso. Cree
un archivo `.env` junto a `SpecRel.exe` con la línea `OPENGL_SOFTWARE=true` y reinicie. El resto de la
aplicación funciona igual sin 3D.

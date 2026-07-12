---
title: "Procesador de Datos iMHEA — Manual de Usuario"
subtitle: "Versión 1.0 · Julio 2026"
lang: es
---

# 1. Introducción

El Procesador de Datos iMHEA convierte registros crudos de sensores de
cuencas de cabecera — eventos de pluviómetros de balancín y archivos de
nivel de agua o caudal — en series de lluvia y caudal con control de
calidad a alta resolución, horaria y diaria, y calcula 59 índices
hidrológicos y 13 índices climáticos que describen rendimiento hídrico,
regulación, variabilidad, frecuencia, duración, estacionalidad e
intensidad de lluvia.

Los métodos implementan Ochoa-Tocachi et al. (2018), *High-resolution
hydrometeorological data from a network of headwater catchments in the
tropical Andes*, Scientific Data 5:180080. El software es una traducción
validada a Python de los scripts originales de iMHEA en MATLAB: los
caudales y flujos base reproducen exactamente el conjunto de datos
publicado, y todos los defectos conocidos del código original fueron
corregidos (un modo de compatibilidad puede reproducir el comportamiento
original; ver sección 11).

**Cómo citar.** Si utiliza resultados de este software en una
publicación, cite el artículo indicado arriba.

# 2. Preparación de sus datos

## 2.1 Formato de archivos crudos

El software lee el formato CSV crudo estándar de iMHEA. Un archivo por
sensor:

**Archivos de pluviómetro** (eventos de balancín):

```
Date,Event mm,Flag
24/05/2001 00:00:01,0,I
24/05/2001 00:41:23,0.2,
03/04/2004 00:00:01,,V
```

**Archivos de nivel de agua / caudal:**

```
Date,Level cm,Flow l/s,Flag
17/07/2012 14:00:00,8.1000,2.5582,"D,P"
```

Reglas:

- Fechas en `dd/mm/aaaa HH:MM:SS`, ordenadas ascendentemente.
- Punto decimal (`.`), columnas separadas por comas.
- Banderas: `I` = equipo instalado, `D` = datos descargados, `X` = pulso
  erróneo eliminado, `P` = intensidad anómala, `V` = vacío de datos. Una
  fila `V` con **valor vacío** marca el inicio de un vacío — así distingue
  el software entre datos faltantes y períodos secos/cero.
- Codificación UTF-8 (se tolera BOM); los fines de línea pueden ser de
  Windows, Unix o Mac clásico.
- Lluvia en milímetros por pulso; nivel en centímetros; caudal en litros
  por segundo.

Una versión técnica de esta especificación está incluida como
`docs/DATA_FORMAT.md`.

## 2.2 Lo que debe conocer de cada cuenca

| Parámetro | Significado | Valores típicos iMHEA |
|---|---|---|
| Área | área de la cuenca que drena al vertedero [km²] | 0.5 – 16 |
| Balde | resolución del pluviómetro [mm por pulso] | 0.1, 0.2 o 0.254 |
| Geometría del vertedero | altura de la V *a* [m], ancho rectangular *b* [m] | 0.30 / según sitio |

# 3. Primeros pasos

Al iniciar, la pantalla de inicio ofrece tres caminos:

- **Procesar mis datos** — crea un proyecto vacío al que usted agrega sus
  cuencas y archivos.
- **Explorar la red iMHEA** — solicita la carpeta que contiene
  `iMHEA_raw/` y carga la configuración completa de la red de 2018
  (28 estaciones, 12 pares) lista para ejecutar.
- **Abrir proyecto…** — reabre un archivo de proyecto `.imhea` guardado.

Un **proyecto** almacena las configuraciones de cuencas, ubicaciones de
archivos y opciones. Guárdelo desde la barra de herramientas (*Guardar
proyecto*); los resultados se recalculan a demanda y no se almacenan en
el archivo de proyecto.

La barra de herramientas contiene además **Ejecutar procesamiento**,
**Exportar** y el selector de idioma **EN/ES**.

# 4. Configuración de una cuenca

Seleccione una cuenca en el panel lateral y abra su pestaña
**Configuración**.

1. Ingrese el código (p. ej. `MIC_01`), el área y el tamaño del balde.
2. En **Caudal**, agregue el/los archivo(s) de nivel/caudal. Si el
   archivo tiene columna de caudal se usa directamente; elija *Nivel →
   curva de descarga…* para convertir nivel de agua (sección 4.1). Las
   estaciones solo de lluvia dejan el caudal vacío.
3. En **Pluviómetros**, agregue un archivo por pluviómetro. Varios
   pluviómetros se verifican y promedian automáticamente (sección 5).
4. Cada archivo muestra una línea de resumen — número de filas, paso de
   tiempo, columnas detectadas, período. Revísela antes de ejecutar.

## 4.1 Editor de curva de descarga

Para estaciones que registran solo nivel de agua, el caudal se calcula
con la ecuación de vertedero compuesto de pared delgada (escotadura en V
de 90° dentro de una sección rectangular):

- Dentro de la V (h ≤ a): Q = C1·h^e1
- Por encima: Q = C1·(h^e1 − (h−a)^e1) + C2·b·(h−a)^e2

El editor permite definir *a*, *b* y los cuatro coeficientes (por
defecto: C1 = 1.37, e1 = 2.5, C2 = 1.77, e2 = 1.5) y muestra la curva
resultante en vivo. Verifique *b* contra los planos de su vertedero — es
específico de cada sitio.

# 5. Ejecución del procesamiento

Presione **Ejecutar procesamiento** con una cuenca seleccionada. El
procesamiento corre en segundo plano; los mensajes aparecen en la pestaña
**Registro**. Lo que ocurre, en orden:

1. **Depuración** — se eliminan pulsos por rebote del equipo separados
   ≤ 1.1 s.
2. **Selección de la malla temporal** — la resolución de trabajo es el
   paso de tiempo mediano del registro de caudal (típicamente 5 min; las
   estaciones solo de lluvia usan 5 min).
3. **Desagregación de lluvia** — los eventos de pulsos se convierten en
   una serie continua de intensidad mediante interpolación con splines
   cúbicos de la curva acumulada (Sadler & Busscher 1989; Wang et al.
   2008), conservando el volumen total; las tormentas se separan a
   0.2 mm/h, las intensidades se limitan a 127 mm/h, los pulsos aislados
   se distribuyen a 3 mm/h.
4. **Relleno cruzado entre pluviómetros** — cada par de pluviómetros se
   compara por análisis de doble masa; los vacíos se rellenan
   proporcionalmente solo cuando la correlación R ≥ 0.99. La lluvia de la
   cuenca es el promedio de las series rellenadas.
5. **Promediado del caudal** a la malla; normalización por área.
6. **Agregación** a productos horarios y diarios; **separación de flujo
   base** (mínimos suavizados UKIH y filtro de dos parámetros de
   Chapman).
7. **Índices** — 59 hidrológicos + 13 climáticos (sección 8).

La barra de estado reporta el tiempo de ejecución (típicamente unos
segundos por cuenca).

# 6. Resultados

La pestaña **Resultados** muestra tarjetas de resumen (período,
coeficiente de escorrentía, índice de flujo base, porcentaje de vacíos) y
una de seis figuras, a resolución diaria, horaria o alta:

| Figura | Muestra |
|---|---|
| Hidrograma | barras de lluvia invertidas sobre la serie de caudal con flujo base sombreado |
| Curva de duración de caudales | porcentaje del tiempo en que cada caudal es excedido (escala log) |
| Curva intensidad-duración | intensidad máxima de lluvia vs duración, 5 min – 2 días |
| Régimen mensual | climatología de precipitación y escorrentía, mm/mes |
| Cobertura de datos | línea de tiempo de datos válidos y vacíos por variable |
| Curva de doble masa | lluvia acumulada vs escorrentía acumulada; los quiebres de pendiente revelan cambios de comportamiento o de instrumentación |

Las figuras son interactivas (zoom, desplazamiento) y pueden guardarse
como PNG/PDF/SVG desde la barra sobre el gráfico.

# 7. Informe de relleno de vacíos

El botón **Informe de relleno de vacíos** (pestaña Resultados) lista cada
comparación de doble masa de la última ejecución: par de pluviómetros, si
se aplicó relleno, la correlación R, la pendiente M y cuántos intervalos
se rellenaron en cada serie. Úselo para documentar el control de calidad
y detectar pluviómetros que divergen (R menor a 0.99 significa que no se
aplicó relleno — investigue la causa).

# 8. Los índices

La pestaña **Índices** lista todos los valores; *Copiar tabla* y
*Guardar CSV…* los exportan. Los índices siguen la nomenclatura de Olden
& Poff (2003) donde aplica. `Qxx` denota el caudal excedido el xx% del
tiempo; los percentiles usan posiciones de graficación de Gringorten.
Todos los índices de caudal se calculan del caudal medio diario en
l/s/km²; los de intensidad de lluvia, de la malla de 5 minutos.

## 8.1 Índices hidrológicos (59)

| # | Código | Descripción | Unidades |
|---|---|---|---|
| 1 | QDMIN | Caudal diario mínimo | l/s/km² |
| 2 | Q95 | Caudal excedido el 95% del tiempo (estiaje) | l/s/km² |
| 3 | DAYQ0 | Días con caudal cero por año | día |
| 4 | PQ0 | Proporción de días con caudal cero | – |
| 5 | QMDRY | Caudal medio diario del mes más seco | l/s/km² |
| 6 | QDMAX | Caudal diario máximo | l/s/km² |
| 7 | Q10 | Caudal excedido el 10% del tiempo (crecidas) | l/s/km² |
| 8 | QDMY | Caudal medio diario anual | l/s/km² |
| 9 | QDML | Caudal medio diario de largo plazo | l/s/km² |
| 10 | Q50 | Caudal mediano de la CDC | l/s/km² |
| 11 | BFI1 | Índice de flujo base, método UKIH de mínimos suavizados | – |
| 12 | K1 | Constante de recesión, método UKIH | – |
| 13 | BFI2 | Índice de flujo base, filtro de Chapman de 2 parámetros | – |
| 14 | K2 | Constante de recesión, filtro de Chapman | – |
| 15 | RANGE | Rango de caudales QDMAX/QDMIN | – |
| 16 | R2FDC | Pendiente de la CDC entre 33% y 66% de excedencia | – |
| 17 | IRH | Índice de regulación hidrológica | – |
| 18 | RBI1 | Índice de variabilidad de Richards-Baker (anual) | – |
| 19 | RBI2 | Índice de variabilidad de Richards-Baker (estacional) | – |
| 20 | DRYQMEAN | Caudal del mes más seco / caudal mensual medio | – |
| 21 | DRYQWET | Caudal del mes más seco / mes más húmedo | – |
| 22 | SINDQ | Índice de estacionalidad de caudales | – |
| 23 | QYEAR | Descarga anual promedio | mm |
| 24 | RRa | Coeficiente de escorrentía anual QYEAR/PYEAR | – |
| 25 | RRm | Coeficiente de escorrentía mensual | – |
| 26 | RRl | Coeficiente de escorrentía de largo plazo | – |
| 27 | MA5 | Asimetría de caudales diarios: media/mediana | – |
| 28 | MA41 | Escorrentía media anual | l/s/km² |
| 29 | MA3 | Coeficiente de variación de caudales diarios | – |
| 30 | MA11 | (Q25 − Q75) / mediana | – |
| 31 | ML17 | Caudal mínimo de 7 días / caudal medio anual | – |
| 32 | ML21 | CV de mínimos de 30 días | – |
| 33 | ML18 | CV de mínimos de 7 días | – |
| 34 | MH16 | Caudal alto: Q10 / mediana | – |
| 35 | MH14 | Máximo mediano de 30 días / mediana | – |
| 36 | MH22 | Volumen medio sobre 3× mediana / mediana | día |
| 37 | MH27 | Pico medio sobre Q25 / mediana | – |
| 38 | FL3 | Pulsos bajos bajo 5% del caudal medio diario | 1/año |
| 39 | FL2 | CV del conteo anual de pulsos bajos (FL1) | – |
| 40 | FL1 | Pulsos bajos bajo Q75 | 1/año |
| 41 | FH3 | Pulsos altos sobre 3× la mediana diaria | 1/año |
| 42 | FH6 | Eventos altos sobre 3× la mediana mensual | 1/año |
| 43 | FH7 | Eventos altos sobre 7× la mediana mensual | 1/año |
| 44 | FH2 | CV del conteo anual de pulsos altos (FH1) | – |
| 45 | FH1 | Pulsos altos sobre Q25 | 1/año |
| 46 | DL17 | CV de duraciones de pulsos bajos (DL16) | – |
| 47 | DL16 | Duración media de pulsos bajos bajo Q75 | día |
| 48 | DL13 | Mínimo medio de 30 días / mediana | – |
| 49 | DH13 | Máximo medio de 30 días / mediana | – |
| 50 | DH16 | CV de duraciones de pulsos altos (DH15) | – |
| 51 | DH20 | Duración media de pulsos sobre mediana/0.75 | día |
| 52 | DH15 | Duración media de pulsos altos sobre Q25 | día |
| 53 | TH3 | Período máximo sin crecidas (sobre Q10), fracción del año | – |
| 54 | TL2 | CV de TL1 | – |
| 55 | TL1 | Día juliano mediano del mínimo anual de 1 día | – |
| 56 | RA8 | Tasa de reversiones de caudal entre días | 1/día |
| 57 | RA5 | Fracción de días con caudal ascendente | – |
| 58 | RA6 | Tasa mediana de ascenso, espacio logarítmico | – |
| 59 | RA7 | Tasa mediana de descenso, espacio logarítmico | – |

## 8.2 Índices climáticos (13)

| # | Código | Descripción | Unidades |
|---|---|---|---|
| 1 | PYEAR | Precipitación anual promedio | mm |
| 2 | DAYP0 | Días sin precipitación por año | día |
| 3 | PP0 | Proporción de días sin precipitación | – |
| 4 | PMDRY | Precipitación del mes más seco | mm |
| 5 | SINDX | Índice de estacionalidad (0 nula – 1 extrema) | – |
| 6 | PVAR | Coeficiente de variación de la precipitación diaria | – |
| 7 | RMED1D | Mediana del máximo anual de 1 día | mm |
| 8 | RMED2D | Mediana del máximo anual de 2 días | mm |
| 9 | RMED1H | Mediana del máximo anual de 1 hora | mm |
| 10 | iMAX1D | Intensidad máxima de 1 día | mm/h |
| 11 | iMAX2D | Intensidad máxima de 2 días | mm/h |
| 12 | iMAX1H | Intensidad máxima de 1 hora | mm/h |
| 13 | iMAX15M | Intensidad máxima de 15 minutos | mm/h |

*(El conjunto de datos publicado lista dos filas adicionales, ETYEAR y
RPPE, derivadas de datos externos de evapotranspiración; este software no
las calcula.)*

# 9. Cuencas pareadas

El diseño iMHEA compara cuencas pareadas (p. ej. conservada vs
intervenida). Cree un par con **+ Agregar par** después de configurar
ambas cuencas. Al ejecutar un par:

- ambas se remuestrean a la resolución común más gruesa;
- la **lluvia** se rellena cruzadamente entre cuencas por análisis de
  doble masa (el caudal nunca se rellena);
- se producen tablas combinadas de alta resolución/horaria/diaria e
  índices lado a lado, con figuras comparativas (hidrogramas
  superpuestos, CDC, curvas intensidad-duración).

# 10. Exportación

**Exportar** escribe, en la carpeta que elija:

- `iMHEA_<CÓDIGO>_HRes_processed.csv` — alta resolución [Fecha, Lluvia,
  Caudal]
- `iMHEA_<CÓDIGO>_1hr_processed.csv` — horaria
- `iMHEA_<CÓDIGO>_1day_processed.csv` — diaria, incluyendo flujo base
- para pares, los archivos `_01`/`_02` correspondientes en el formato
  publicado de iMHEA (fechas `dd/mm/aaaa HH:MM:SS`, valores de ancho
  fijo, `NaN` para vacíos).

Los índices se exportan desde la pestaña Índices (CSV o portapapeles).

# 11. Modo compatible con MATLAB

Durante la traducción se encontraron nueve defectos en el código MATLAB
original (documentados en `docs/CODE_REVIEW.md` y cuantificados en
`docs/VALIDATION.md`). Por defecto este software calcula los valores
**corregidos**. Al marcar *Modo compatible con MATLAB* (pestaña
Configuración) se reproduce el comportamiento original donde es posible —
útil al comparar con el conjunto de datos publicado en 2018. Las
diferencias más relevantes:

- **BFI1/K1**: los valores publicados están inflados para registros con
  vacíos de datos (los bloques con vacíos entraban a la línea de flujo
  base como puntos de quiebre).
- **TL1/TL2**: los valores publicados de estacionalidad no son confiables
  después del primer año de cada registro (defecto de indexación del día
  del año).
- **FH7**: los valores publicados están doblemente normalizados
  (demasiado pequeños, aproximadamente por el número de años).

# 12. Referencia de línea de comandos

Para trabajo por lotes, el comando `imhea` (requiere el paquete de
Python):

```
imhea process --code MIC_01 --area 2.63 --bucket 0.2 \
    --flow caudal.csv --gauge pluv1.csv --gauge pluv2.csv --out ./procesado
imhea process --code LLUVIA_01 --bucket 0.1 --gauge pluv.csv --out ./salida
imhea pair --hres1 A_HRes.csv --hres2 B_HRes.csv --site XYZ --out ./salida
imhea network --data-root ./Scripts --out ./validacion
imhea --version
```

`--level-to-flow` (con `--weir A B` y `--coeff C1 E1 C2 E2`) convierte una
columna de nivel mediante la curva de descarga; `--matlab-compat` activa
el modo de compatibilidad.

# 13. Preguntas frecuentes

**¿Cuántos datos se necesitan para índices significativos?** Al menos un
año completo; el software calcula índices para cualquier longitud de
registro sin advertencia, así que interprete con cautela los resultados
de registros cortos (las estadísticas anuales tratan años parciales como
completos, igual que la metodología original).

**¿Por qué cambia ligeramente el total de lluvia tras el procesamiento?**
La depuración elimina pulsos dobles físicamente imposibles (≤ 1.1 s de
separación); el registro reporta el volumen eliminado. La desagregación
en sí conserva el volumen.

**Aparecen vacíos donde espero datos.** Los vacíos provienen de las filas
con bandera `V` en los archivos crudos. Revise la figura de Cobertura de
datos y la columna de banderas de los archivos.

**¿Puedo procesar datos de equipos que no son de iMHEA?** Sí — conviértalos
al formato CSV de la sección 2.1. Solo son obligatorios el formato de
fecha, la disposición de columnas y la convención de vacíos `V`.

**¿Dónde se guardan los resultados de mi proyecto?** Los resultados viven
en memoria y se recalculan a demanda; los CSV exportados y el archivo de
proyecto `.imhea` son los artefactos persistentes.

# 14. Referencias

- Ochoa-Tocachi, B.F., et al. (2018). High-resolution hydrometeorological
  data from a network of headwater catchments in the tropical Andes.
  *Scientific Data* 5, 180080.
- Gustard, A., Bullock, A., Dixon, J.M. (1992). *Low flow estimation in
  the United Kingdom.* Institute of Hydrology Report 108.
- Chapman, T. (1999). A comparison of algorithms for stream flow
  recession and baseflow separation. *Hydrological Processes* 13.
- Olden, J.D., Poff, N.L. (2003). Redundancy and the choice of hydrologic
  indices for characterizing streamflow regimes. *River Research and
  Applications* 19.
- Sadler, E.J., Busscher, W.J. (1989). High-intensity rainfall rate
  determination from tipping-bucket rain gauge data. *Agronomy Journal* 81.
- Wang, J., et al. (2008). A new treatment of depth-dependent errors in
  tipping-bucket rain gauge measurements. *J. Atmos. Oceanic Technol.* 25.

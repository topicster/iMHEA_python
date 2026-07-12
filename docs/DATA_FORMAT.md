# iMHEA raw data format specification / Especificación del formato de datos crudos iMHEA

*English below · Español primero*

## ES — Especificación

Un archivo CSV por sensor, nombrado
`iMHEA_<SITIO>_<CUENCA>_<SENSOR>_<NÚMERO>_raw.csv`
(p. ej. `iMHEA_CHA_01_PT_01_raw.csv`). Códigos de sensor: `PD`/`PT`/`PO` =
pluviómetro; `HI`/`HW`/`HS`/`HD`/`HO` = nivel/caudal.

### Pluviómetros (eventos de balancín)

| Columna | Contenido | Unidades |
|---|---|---|
| `Date` | `dd/mm/aaaa HH:MM:SS`, ascendente | – |
| `Event mm` | lluvia por pulso (vacío en filas de bandera `V`) | mm |
| `Flag` | ver tabla de banderas | – |

### Nivel de agua / caudal

| Columna | Contenido | Unidades |
|---|---|---|
| `Date` | `dd/mm/aaaa HH:MM:SS`, ascendente | – |
| `Level cm` | nivel de agua sobre el vértice del vertedero | cm |
| `Flow l/s` | caudal (puede omitirse si solo hay nivel) | l/s |
| `Flag` | ver tabla; varias banderas entre comillas: `"D,P"` | – |

Los archivos solo de caudal (`HW`) usan `Date,Flow l/s,Flag`.

### Banderas

| Bandera | Significado |
|---|---|
| `I` | equipo instalado / programado |
| `D` | datos descargados |
| `X` | pulso erróneo eliminado |
| `P` | intensidad anómala |
| `V` | **vacío de datos** — la fila lleva valor vacío; marca el inicio del período sin datos, que termina en la siguiente fila con valor |

### Reglas generales

- Codificación UTF-8; se tolera BOM. Fines de línea CR, LF o CRLF.
- Punto decimal (`.`); sin separador de miles.
- Fechas estrictamente ascendentes, sin duplicados.
- Sin filas vacías; la primera línea es el encabezado.
- La convención `V` es la **única** forma de marcar datos faltantes:
  un salto de tiempo sin fila `V` se interpreta como ausencia de lluvia
  (pluviómetros registran por evento) o como muestreo irregular (caudal).

---

## EN — Specification

One CSV file per sensor, named
`iMHEA_<SITE>_<CATCHMENT>_<SENSOR>_<NUMBER>_raw.csv`
(e.g. `iMHEA_CHA_01_PT_01_raw.csv`). Sensor codes: `PD`/`PT`/`PO` =
rain gauge; `HI`/`HW`/`HS`/`HD`/`HO` = level/discharge.

### Rain gauges (tipping-bucket events)

| Column | Content | Units |
|---|---|---|
| `Date` | `dd/mm/yyyy HH:MM:SS`, ascending | – |
| `Event mm` | rainfall per tip (empty on `V`-flag rows) | mm |
| `Flag` | see flag table | – |

### Water level / discharge

| Column | Content | Units |
|---|---|---|
| `Date` | `dd/mm/yyyy HH:MM:SS`, ascending | – |
| `Level cm` | water level above the weir vertex | cm |
| `Flow l/s` | discharge (may be absent if level-only) | l/s |
| `Flag` | see table; multiple flags quoted: `"D,P"` | – |

Flow-only files (`HW`) use `Date,Flow l/s,Flag`.

### Flags

| Flag | Meaning |
|---|---|
| `I` | logger installed / launched |
| `D` | data downloaded |
| `X` | erroneous tip removed |
| `P` | anomalous intensity |
| `V` | **data gap** — the row carries an empty value; it marks the start of the missing period, which ends at the next valued row |

### General rules

- UTF-8 encoding; BOM tolerated. CR, LF or CRLF line endings.
- Decimal point (`.`); no thousands separator.
- Strictly ascending timestamps, no duplicates.
- No blank rows; the first line is the header.
- The `V` convention is the **only** way to mark missing data: a time
  jump without a `V` row is interpreted as no rainfall (gauges are
  event-based) or irregular sampling (discharge).

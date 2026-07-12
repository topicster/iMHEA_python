"""Minimal EN/ES dictionary-based translation."""

from __future__ import annotations

LANG = "en"

_T = {
    "app_title": ("iMHEA Data Processor", "Procesador de Datos iMHEA"),
    "start_process": ("Process my data", "Procesar mis datos"),
    "start_explore": ("Explore the iMHEA network", "Explorar la red iMHEA"),
    "start_open": ("Open project…", "Abrir proyecto…"),
    "start_sub": ("Rainfall & streamflow processing for Andean catchments",
                  "Procesamiento de lluvia y caudal para cuencas andinas"),
    "catchments": ("Catchments", "Cuencas"),
    "pairs": ("Pairs", "Pares"),
    "rain_stations": ("Rain stations", "Estaciones de lluvia"),
    "add_catchment": ("Add catchment", "Agregar cuenca"),
    "add_rain": ("Add rain station", "Agregar estación de lluvia"),
    "add_pair": ("Add pair", "Agregar par"),
    "run": ("Run pipeline", "Ejecutar procesamiento"),
    "export": ("Export", "Exportar"),
    "setup": ("Setup", "Configuración"),
    "results": ("Results", "Resultados"),
    "indices": ("Indices", "Índices"),
    "log": ("Log", "Registro"),
    "code": ("Code", "Código"),
    "area": ("Area [km²]", "Área [km²]"),
    "bucket": ("Bucket [mm]", "Balde [mm]"),
    "discharge": ("Discharge", "Caudal"),
    "rain_gauges": ("Rain gauges", "Pluviómetros"),
    "add_files": ("Add gauge files", "Agregar archivos"),
    "select_flow": ("Select discharge file", "Seleccionar archivo de caudal"),
    "source": ("Source", "Fuente"),
    "flow_col": ("Flow column (l/s)", "Columna de caudal (l/s)"),
    "level_rating": ("Level → rating curve…", "Nivel → curva de descarga…"),
    "matlab_compat": ("MATLAB-compatible mode", "Modo compatible con MATLAB"),
    "compat_hint": ("reproduces legacy behaviour (see validation report)",
                    "reproduce el comportamiento original (ver informe)"),
    "validate": ("Validate setup", "Validar configuración"),
    "period": ("Period", "Período"),
    "runoff_ratio": ("Runoff ratio", "Coef. de escorrentía"),
    "gaps": ("Gaps", "Vacíos"),
    "resolution": ("Resolution", "Resolución"),
    "daily": ("Daily", "Diario"),
    "hourly": ("Hourly", "Horario"),
    "highres": ("High-res", "Alta resolución"),
    "figure": ("Figure", "Figura"),
    "hydrograph": ("Hydrograph", "Hidrograma"),
    "fdc": ("Flow duration curve", "Curva de duración de caudales"),
    "idc": ("Intensity-duration curve", "Curva intensidad-duración"),
    "regime": ("Monthly regime", "Régimen mensual"),
    "coverage": ("Data coverage", "Cobertura de datos"),
    "double_mass": ("Double-mass curve", "Curva de doble masa"),
    "index": ("Index", "Índice"),
    "value": ("Value", "Valor"),
    "description": ("Description", "Descripción"),
    "copy_table": ("Copy table", "Copiar tabla"),
    "save_csv": ("Save CSV…", "Guardar CSV…"),
    "running": ("Processing…", "Procesando…"),
    "done_in": ("Pipeline finished in", "Procesamiento terminado en"),
    "failed": ("Processing failed", "Error en el procesamiento"),
    "no_results": ("Run the pipeline to see results",
                   "Ejecute el procesamiento para ver resultados"),
    "rating_title": ("Rating curve editor", "Editor de curva de descarga"),
    "vnotch_h": ("V-notch height a [m]", "Altura del vertedero V a [m]"),
    "rect_w": ("Rectangular width b [m]", "Ancho rectangular b [m]"),
    "preview": ("Preview", "Vista previa"),
    "fills_title": ("Gap-filling report", "Informe de relleno de vacíos"),
    "fills_none": ("No cross-filling was attempted (single gauge).",
                   "No se intentó relleno cruzado (un solo pluviómetro)."),
    "new_project": ("New project", "Nuevo proyecto"),
    "save_project": ("Save project", "Guardar proyecto"),
    "data_root": ("Select the folder containing iMHEA_raw",
                  "Seleccione la carpeta que contiene iMHEA_raw"),
    "export_done": ("Files exported to", "Archivos exportados a"),
    "pair_of": ("Pair", "Par"),
    "remove": ("Remove", "Quitar"),
    "gauge_info": ("{n} rows · {span}", "{n} filas · {span}"),
}


def tr(key: str) -> str:
    pair = _T.get(key)
    if pair is None:
        return key
    return pair[1] if LANG == "es" else pair[0]


def set_lang(lang: str) -> None:
    global LANG
    LANG = "es" if lang == "es" else "en"

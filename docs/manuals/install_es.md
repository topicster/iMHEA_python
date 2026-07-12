---
title: "Procesador de Datos iMHEA — Manual de Instalación"
subtitle: "Versión 1.0 · Julio 2026"
lang: es
---

# Acerca de este software

El **Procesador de Datos iMHEA** procesa datos de lluvia y caudal de
cuencas de monitoreo hidrológico siguiendo la metodología de la Iniciativa
Regional de Monitoreo Hidrológico de Ecosistemas Andinos (iMHEA), publicada
en Ochoa-Tocachi et al. (2018), *Scientific Data* 5:180080.

Se distribuye en tres formas — instale la que mejor le convenga:

| Componente | Para | Requiere |
|---|---|---|
| **Aplicación de escritorio** | Equipos de campo y analistas; sin programación | Nada (autónoma) |
| **Herramienta de línea de comandos** (`imhea`) | Procesamiento por lotes, automatización | Python 3.10+ |
| **Biblioteca de Python** (`import imhea`) | Investigadores, análisis personalizados | Python 3.10+ |

# Opción A — Aplicación de escritorio (recomendada)

## A.1 Desde un paquete de distribución

Si recibió (o descargó de la página de *Releases* de GitHub del proyecto)
un archivo ZIP para su sistema operativo:

**Windows**

1. Descomprima `iMHEA-Data-Processor-windows.zip` en cualquier carpeta
   (p. ej. `Documentos`).
2. Abra la carpeta y haga doble clic en `iMHEA-Data-Processor.exe`.
3. Solo la primera vez: Windows SmartScreen puede advertir sobre una
   aplicación no reconocida. Haga clic en **Más información → Ejecutar de
   todas formas**. Esto ocurre porque el ejecutable no está firmado
   digitalmente; no indica ningún problema.

**macOS**

1. Descomprima y arrastre `iMHEA Data Processor.app` a `Aplicaciones`
   (opcional).
2. Solo la primera vez: **clic derecho sobre la app → Abrir → Abrir**.
   Gatekeeper de macOS bloquea el doble clic en aplicaciones no firmadas
   la primera vez. Si aún se niega, ejecute en Terminal:
   `xattr -dr com.apple.quarantine "/Applications/iMHEA Data Processor.app"`

**Linux**

1. Descomprima y ejecute `./iMHEA-Data-Processor/iMHEA-Data-Processor`.
2. Si reporta que falta un *Qt platform plugin*, instale las bibliotecas
   del sistema: `sudo apt install libegl1 libxkbcommon0`.

## A.2 Construir la aplicación usted mismo

Si no hay un paquete disponible para su plataforma, constrúyalo con un
doble clic. Primero necesita **Python 3.10 o superior**
(<https://www.python.org/downloads/> — en Windows, marque *"Add python.exe
to PATH"* durante la instalación).

1. Obtenga la carpeta `imhea-python` (del repositorio o de un colega).
2. Abra la subcarpeta `packaging`.
3. **macOS:** doble clic en `build_mac.command` (la primera vez: clic
   derecho → Abrir). **Windows:** doble clic en `build_windows.bat`.
4. Espere unos minutos. La aplicación terminada aparece en
   `imhea-python/dist/` y la carpeta se abre automáticamente. La app es
   autónoma — cópiela o comprímala para compartirla con colegas, quienes
   **no** necesitan Python.

## A.3 Construcción automática con GitHub Actions

Si el repositorio está alojado en GitHub, cada versión etiquetada (p. ej.
`v1.0.0`) construye y publica automáticamente paquetes para Windows, macOS
(Intel y Apple Silicon) y Linux. Los mantenedores también pueden iniciar
una construcción manualmente desde la pestaña **Actions** (flujo *Build
desktop apps*); los paquetes aparecen como artefactos descargables en la
página de la ejecución.

# Opción B — Paquete de Python (CLI + biblioteca)

Para usuarios con experiencia en terminal:

```
pip install imhea            # desde PyPI, cuando se publique
# o, desde una copia del repositorio:
pip install -e ".[gui]"      # biblioteca + CLI + aplicación de escritorio
```

Esto instala dos comandos:

- `imhea` — la interfaz de línea de comandos (ver Manual de Usuario,
  sección 9).
- `imhea-gui` — inicia la aplicación de escritorio.

Para ejecutar la interfaz gráfica desde el código fuente sin instalar:
`python gui/run_gui.py`.

# Requisitos del sistema

| | Mínimo |
|---|---|
| Sistema operativo | Windows 10+, macOS 12+ o Linux (glibc 2.31+) |
| Memoria | 4 GB (8 GB recomendado para registros multianuales de 5 min) |
| Disco | 500 MB para la aplicación; almacenamiento de datos según necesidad |
| Python (solo opciones B / A.2) | 3.10 o superior |

# Actualización

- **Aplicación de escritorio:** descargue o construya la nueva versión y
  reemplace la carpeta/app anterior. Los archivos de proyecto (`.imhea`)
  son compatibles hacia adelante.
- **Paquete de Python:** `pip install -U imhea`.

# Solución de problemas

**"Python not found" al construir.** Instale Python desde python.org y, en
Windows, vuelva a ejecutar el instalador eligiendo *Modify* si olvidó
marcar "Add python.exe to PATH".

**El script de construcción se cierra inmediatamente (Windows).** Abra un
Símbolo del sistema en la carpeta `packaging` y ejecute
`build_windows.bat` para ver el mensaje de error.

**macOS: "la app está dañada o incompleta".** La marca de cuarentena
sobrevive algunas transferencias. Ejecute:
`xattr -dr com.apple.quarantine "iMHEA Data Processor.app"`.

**La app inicia pero las figuras están en blanco (Linux).** Defina la
variable de entorno `QT_QPA_PLATFORM=xcb` (sistemas Wayland) o instale
`libegl1`.

**Carpetas sincronizadas en la nube.** Construir dentro de carpetas de
OneDrive/Dropbox/Drive funciona pero sincroniza cientos de megabytes;
prefiera construir en una carpeta local, o pause la sincronización.

# Obtener ayuda

Reporte problemas en la página de *Issues* de GitHub del proyecto,
adjuntando el mensaje mostrado en la pestaña **Registro** de la app o la
salida del terminal. Incluya su sistema operativo y la versión del
software (mostrada por `imhea --version` o en la barra de título).

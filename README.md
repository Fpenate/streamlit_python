# Streamlit Python Proyect

Aplicación web (Streamlit) para validar mediciones de sensores Flash/IR en Allegro a partir de archivos CSV. Procesa las mediciones, valida cada track, ejecuta pruebas estadísticas (Levene, ANOVA, Tukey HSD), calcula límites de control I-MR y genera un reporte imprimible con el resultado de la prueba.

## Inicio rápido

```bash
# 1. Crear el entorno virtual (solo la primera vez)
python3 -m venv venv

# 2. Activar el entorno
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
streamlit run app.py
```

Abrir la URL que muestra Streamlit (por defecto `http://localhost:8501`).

## Inicio rápido en Windows

```bat
rem 1. Crear el entorno virtual (solo la primera vez)
python -m venv venv

rem 2. Activar el entorno
venv\Scripts\activate

rem 3. Instalar dependencias
pip install -r requirements.txt

rem 4. Ejecutar la aplicación
streamlit run app.py
```

> **Importante en Windows:** `RUTA_ARCHIVOS_CSV` en `app.py` apunta a una ruta absoluta de Linux (`/home/user/...`). Al correr en Windows hay que cambiarla, por ejemplo a `r"C:\Users\TU_USUARIO\ALLEGRO_04_08_2026\data"`. Si usás PowerShell, la activación del entorno es `venv\Scripts\Activate.ps1` (o `venv\Scripts\activate.bat` en CMD).

## Cómo se usa

1. **Información de lote**: ingresar SHOP ORDER (10 caracteres), SPEC (8), BADGE (5 dígitos), turno, máquina y fecha. Al completar el SHOP ORDER la app busca el CSV automáticamente en `data/uploads/`.
2. **Defectos**: opcional, hasta 3 defectos (VOID, STREAK, TND, PINHOLE, OTROS).
3. **Reproceso**: marcar si la prueba es un reproceso de un lote anterior.
4. **Procesar datos**: ejecuta el análisis y abre las pestañas de resultados (Validaciones, Estadística, SPC, Global, Reporte).

## Comportamiento del sigma

| Tipo de prueba | Sigma efectivo |
|---|---|
| Normal (sin reproceso ni defectos) | `sigma_value` configurado |
| Reproceso o con defectos | `max(1.0, sigma_value - sigma_reproceso)` |

Los valores se configuran en **Configuración de Validación** (requiere código de acceso, ver abajo). El reporte impreso siempre muestra el sigma efectivo usado.

## Estructura del proyecto

| Archivo / carpeta | Propósito |
|---|---|
| `app.py` | Interfaz Streamlit, flujo de páginas, búsqueda de CSV, persistencia de configuración |
| `modules/csv_processor.py` | Lectura, limpieza, filtrado y validación de mediciones |
| `modules/stats_analyzer.py` | Levene, ANOVA, Tukey HSD, límites I-MR, detección de outliers MAD |
| `modules/db_operations.py` | Inserción directa en MySQL (tabla `test_limits`) |
| `config/connect_database.py` | Conexión MySQL (lee `config_db.json`) |
| `config/config_validacion.json` | Parámetros de validación persistidos (se reescribe desde la UI) |
| `data/uploads/` | Archivos CSV de medición (no se suben al repositorio) |

## Configuración

### Parámetros de validación

Acceso desde la UI: **⚙️ Configuración de Validación** → código `ADMIN123` (hardcodeado en `app.py`).

| Parámetro | Descripción |
|---|---|
| Mínimo de mediciones válidas por track | Mínimo requerido por track (default 100) |
| Valor de Sigma (σ) | Sigma para pruebas normales (rango 2.0–6.0) |
| Sigma a restar en reproceso/defectos | Se resta al sigma cuando es reproceso o lleva defectos (pasos de 0.1) |
| Alpha para FLASH / IR (Tukey) | Nivel de significancia para Tukey HSD |

### Base de datos (opcional)

La persistencia principal usa un endpoint HTTP (`guardar_en_bd_php`). La inserción directa a MySQL requiere un archivo `config_db.json` en la raíz del proyecto (NO está versionado):

```json
{
    "DB_HOST": "localhost",
    "DB_NAME": "tu_base",
    "DB_USER": "tu_usuario",
    "DB_PASSWORD": "tu_password"
}
```

## Notas importantes

- `RUTA_ARCHIVOS_CSV` en `app.py` es una **ruta absoluta hardcodeada** a `data/`; si movés el proyecto, actualizala.
- El proyecto **no tiene tests ni CI**; `requirements.txt` está pinneado, no actualizar dependencias sin necesidad.
- Los archivos de medición (`data/uploads/*.csv`) están en `.gitignore` — son datos de producción, no se suben a GitHub.

## Requisitos

- Python 3.12 (probado con 3.12.3)
- Dependencias en `requirements.txt` (pinned)

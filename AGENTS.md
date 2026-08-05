# AGENTS.md

Streamlit app for validating Allegro sensor measurement CSVs ("Automatización Límites Allegro"). The entire codebase is Spanish: identifiers, comments, UI strings, and emoji error prefixes (✅/❌/⚠️). Extend in Spanish; do not switch to English.

## Run

- `source venv/bin/activate && streamlit run app.py` (venv exists, Python 3.12.3)
- Fresh setup: `python3 -m venv venv && pip install -r requirements.txt` then run
- No tests, no CI, no git repo. `requirements.txt` is pinned; don't bump deps casually (statsmodels/scipy drive the stats analysis).

## Layout

- `app.py` — all Streamlit UI, page flow, CSV lookup, config persistence (~1600 lines)
- `modules/csv_processor.py` — `CSVProcessor`: read/clean/filter/pivot/validate measurement data
- `modules/stats_analyzer.py` — `StatsAnalyzer`: Levene tests, ANOVA, Tukey HSD (configurable alpha), IMR control limits, MAD outlier detection, plots
- `modules/db_operations.py` — direct MySQL insert into table `test_limits`
- `config/connect_database.py` — MySQL connection helper (reads `config_db.json`)
- `config/config_validacion.json` — persisted validation params (min measurements, sigma, sigma subtracted for reproceso/defects, alphas); the app rewrites this file at runtime from the config UI. `sigma_reproceso` defaults to 1.0 if the key is missing (old configs stay valid).
- `data/uploads/` — measurement CSVs (named by `AU...` shop order)

## Conventions

- Keep new UI code in `app.py`; put new analysis/processing logic in `modules/`.
- Sensor handling is dynamic, not hardcoded to IR1..IR4: code detects any IR column pair via `_uA`/`_nA` suffixes and the lowest-numbered `CreatorID` is the µA sensor.

## Gotchas

- `RUTA_ARCHIVOS_CSV` in `app.py` is a **hardcoded absolute path** to `data/` (CSVs actually live in `data/uploads/`; the recursive glob `**/*.csv` finds them). Moving the repo breaks lookup — update this constant.
- MySQL features require `config_db.json` (`DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`) which is **not committed**; DB operations fail until it is created. There is also an alternate HTTP persistence path (`guardar_en_bd_php`) posting to `https://development.avxels.com/sistemas/test_limits`.
- Config UI access code is hardcoded: `CODIGO_ACCESO_CONFIGURACION = "ADMIN123"` in `app.py`.
- CSV contract: files contain junk rows before the real header (header has `Index, Track, CreatorID, DataID, Value`); the processor auto-detects it. Values are scientific notation — first IR scaled to µA (1e6), others to nA (1e9). Only rows with `CreatorID` starting with `IR` and `DataID == 'IRMeasure'` are kept.
- Shop-order lookup requires exactly 10 chars; a leading `L` is stripped (scanner artifact). Duplicate files resolve to the most recently modified.
- `alpha_ir` in the JSON config can carry float noise (e.g. `0.055000000000000146`) from JSON round-tripping; normalizing to 2–3 decimals is safe.
- Sigma logic: on `PROCESAR DATOS`, if reproceso checkbox or any defect is selected, the effective sigma becomes `max(1.0, sigma_guardado - sigma_reproceso_guardado)` and is stored in `st.session_state.sigma_utilizado`; the printed report always shows the sigma actually used.

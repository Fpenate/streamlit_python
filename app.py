# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
from datetime import datetime, date
from PIL import Image
import matplotlib.pyplot as plt

import sys
from pathlib import Path
import os
import glob
import io
import time
                
import mysql.connector
from mysql.connector import Error
import json
import requests


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================
RUTA_ARCHIVOS_CSV = r"/home/user/Trabajo/ALLEGRO_04_08_2026/data"
#cambiar esta ruta a la carpeta donde se encuentran los archivos CSV


# ============================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================
CODIGO_ACCESO_CONFIGURACION = "ADMIN123"

# ============================================================
# FUNCIONES PARA GESTIONAR CONFIGURACIÓN PERSISTENTE
# ============================================================
ARCHIVO_CONFIG = os.path.join(os.path.dirname(__file__), 'config', 'config_validacion.json')


def guardar_en_bd_php(datos_payload):

    URL_ENDPOINT = "https://development.avxels.com/sistemas/test_limits" 
    
    try:
        response = requests.post(URL_ENDPOINT, json=datos_payload, timeout=10)
        if response.status_code == 200:
            return True, "✅ Datos guardados correctamente en la base de datos."
        else:
            return False, f"❌ Error del servidor: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"❌ Error de conexión: {str(e)}"
    

def guardar_configuracion_validacion(min_mediciones: int, sigma_val: float, alpha_flash: float, alpha_ir: float, sigma_reproceso: float = 1.0) -> tuple:
    
    try:
        # Normalizar decimales para evitar ruido de punto flotante (0.5000000000000001 -> 0.5)
        sigma_val = round(float(sigma_val), 1)
        sigma_reproceso = round(float(sigma_reproceso), 1)
        alpha_flash = round(float(alpha_flash), 4)
        alpha_ir = round(float(alpha_ir), 4)
        
        # Crear carpeta config si no existe
        carpeta_config = os.path.dirname(ARCHIVO_CONFIG)
        if not os.path.exists(carpeta_config):
            os.makedirs(carpeta_config)
        
        # Crear diccionario de configuración
        configuracion = {
            'min_mediciones_por_track': int(min_mediciones),
            'sigma_value': float(sigma_val),
            'sigma_reproceso': float(sigma_reproceso),
            'alpha_flash': float(alpha_flash),
            'alpha_ir': float(alpha_ir),
            'fecha_ultima_modificacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Guardar en JSON
        with open(ARCHIVO_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(configuracion, f, indent=4, ensure_ascii=False)
        
        return True, f"✅ Configuración guardada correctamente. Mínimo de mediciones: {min_mediciones} | Sigma: {sigma_val} | Sigma a restar (reproceso): {sigma_reproceso} | Alpha FLASH: {alpha_flash} | Alpha IR: {alpha_ir}"
        
    except Exception as e:
        return False, f"❌ Error al guardar configuración: {str(e)}"

def leer_configuracion_validacion() -> tuple:

    try:
        if os.path.exists(ARCHIVO_CONFIG):
            with open(ARCHIVO_CONFIG, 'r', encoding='utf-8') as f:
                configuracion = json.load(f)
            return (
                configuracion.get('min_mediciones_por_track', 100),
                round(float(configuracion.get('sigma_value', 3.0)), 1),
                round(float(configuracion.get('alpha_flash', 0.05)), 4),
                round(float(configuracion.get('alpha_ir', 0.05)), 4),
                round(float(configuracion.get('sigma_reproceso', 1.0)), 1)
            )
    except Exception as e:
        pass
    
    # Retornar valor por defecto si no existe o hay error
    return 100, 3.0, 0.05, 0.05, 1.0

# Agregar la carpeta modules al path
sys.path.append(str(Path(__file__).parent))

from modules.csv_processor import CSVProcessor
from modules.stats_analyzer import StatsAnalyzer
from config.connect_database import load_config, create_db_connection
from modules.db_operations import guardar_datos_lote

# ============================================================
# FUNCIÓN PARA BUSCAR ARCHIVO CSV POR SHOP_ORDER
# ============================================================
import os
import glob
from datetime import datetime

def buscar_archivo_csv(shop_order: str) -> tuple:
    try:
        if not shop_order or len(shop_order) != 10:
            return None, "❌ El SHOP ORDER debe tener exactamente 10 caracteres", False, None
        
        if not os.path.exists(RUTA_ARCHIVOS_CSV):
            return None, f"❌ La carpeta '{RUTA_ARCHIVOS_CSV}' no existe.", False, None
        
        # Lógica para corregir escáneres que insertan 'L' al inicio (Ej: LAU3860039 -> AU3860039*)
        shop_order_busqueda = shop_order
        if shop_order.upper().startswith('L'):
            shop_order_busqueda = shop_order[1:]
            
        patron_busqueda = os.path.join(RUTA_ARCHIVOS_CSV, "**", f"{shop_order_busqueda}*.csv")
        archivos_encontrados = glob.glob(patron_busqueda, recursive=True)
        
        if not archivos_encontrados:
            return None, f"❌ No se encontró archivo CSV para el SHOP ORDER '{shop_order}' (Buscando: {shop_order_busqueda}*)", False, None
        
        # 1. Detectar duplicados
        hubo_duplicados = len(archivos_encontrados) > 1
        
        # 2. Ordenar por fecha de modificación y tomar el primero
        archivos_encontrados.sort(key=os.path.getmtime, reverse=True)
        archivo_path = archivos_encontrados[0]
        
        # 3. Obtener y formatear la fecha del archivo seleccionado
        timestamp = os.path.getmtime(archivo_path)
        fecha_dt = datetime.fromtimestamp(timestamp)
        fecha_formateada = fecha_dt.strftime("%d/%m/%Y %H:%M:%S")
        
        return archivo_path, None, hubo_duplicados, fecha_formateada
        
    except Exception as e:
        return None, f"❌ Error al buscar archivo: {str(e)}", False, None


# Importar módulo de db_operations para guardar datos de lote
from modules.db_operations import guardar_datos_lote

# Configuración de la página
st.set_page_config(
    page_title="Automatización Límites Allegro",
    page_icon="🧪",
    layout="centered"
)
# 2. Inyección de CSS para limpiar la interfaz
st.markdown("""
    <style>
        /* Ocultar el botón de Deploy */
        .stDeployButton {
            display: none !important;
        }

        /* Ocultar el botón del Menú (las 3 rayas) */
        /* Nota: Esto oculta TODO el menú, incluyendo Settings y Wide Mode */
        #MainMenu {
            visibility: hidden !important;
        }

        /* O si prefieres mantener el menú pero ocultar solo opciones específicas, 
           es difícil por CSS, por lo que ocultar el header completo es más seguro */
        header {
            visibility: hidden !important;
        }

        /* Ajustar el espacio que deja el header oculto */
        .main .block-container {
            padding-top: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# Inicializar session_state para mantener datos entre interacciones
if 'datos_procesados' not in st.session_state:
    st.session_state.datos_procesados = None
if 'validaciones' not in st.session_state:
    st.session_state.validaciones = None
if 'procesamiento_exitoso' not in st.session_state:
    st.session_state.procesamiento_exitoso = False
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'min_mediciones_utilizado' not in st.session_state:
    st.session_state.min_mediciones_utilizado = None
if 'defectos_procesados' not in st.session_state:
    st.session_state.defectos_procesados = None
if 'reproceso_procesado' not in st.session_state:
    st.session_state.reproceso_procesado = None
if 'stats_analyzer' not in st.session_state:
    st.session_state.stats_analyzer = None
if 'resultados_levene' not in st.session_state:
    st.session_state.resultados_levene = {}
if 'sigma_utilizado' not in st.session_state:
    st.session_state.sigma_utilizado = None
if 'sigma_ajustado_por_reglas' not in st.session_state:
    st.session_state.sigma_ajustado_por_reglas = False
if 'csv_file' not in st.session_state:
    st.session_state.csv_file = None
if 'archivo_csv_path' not in st.session_state:
    st.session_state.archivo_csv_path = None
if 'codigo_acceso_valido' not in st.session_state:
    st.session_state.codigo_acceso_valido = False
if 'codigo_ingresado' not in st.session_state:
    st.session_state.codigo_ingresado = ""
if 'min_mediciones_guardado' not in st.session_state or 'sigma_guardado' not in st.session_state:
    min_m, sig_v, alpha_flash, alpha_ir, sigma_rep = leer_configuracion_validacion()
    if 'alpha_flash_guardado' not in st.session_state:
        st.session_state.alpha_flash_guardado = alpha_flash
    if 'alpha_ir_guardado' not in st.session_state:
        st.session_state.alpha_ir_guardado = alpha_ir
    if 'min_mediciones_guardado' not in st.session_state:
        st.session_state.min_mediciones_guardado = min_m
    if 'sigma_guardado' not in st.session_state:
        st.session_state.sigma_guardado = sig_v
    if 'sigma_reproceso_guardado' not in st.session_state:
        st.session_state.sigma_reproceso_guardado = sigma_rep
if 'limpiar_codigo' not in st.session_state:
    st.session_state.limpiar_codigo = False
if 'mensaje_db_exito' not in st.session_state:
    st.session_state.mensaje_db_exito = None
if 'mostrar_formulario_limites' not in st.session_state:
    st.session_state.mostrar_formulario_limites = False
if 'datos_limites_guardados' not in st.session_state:
    st.session_state.datos_limites_guardados = {
        "sup_flash": "", "inf_flash": "",
        "sup_ir": "", "inf_ir": ""
    }

def limpiar_formulario_callback():
    # Limpiar los inputs de texto
    for key in ["inp_shop_order", "inp_spec", "inp_badge", "def1_man", "def2_man", "def3_man"]:
        if key in st.session_state:
            st.session_state[key] = ""
    
    # Limpiar los selectores
    if "sel_turno" in st.session_state: st.session_state["sel_turno"] = 1
    if "sel_maquina" in st.session_state: st.session_state["sel_maquina"] = 1
    if "chk_reproceso" in st.session_state: st.session_state["chk_reproceso"] = False
    
    # Limpiar defectos
    if "def1" in st.session_state: st.session_state["def1"] = "-- Seleccionar --"
    if "def2" in st.session_state: st.session_state["def2"] = "-- Seleccionar --"
    if "def3" in st.session_state: st.session_state["def3"] = "-- Seleccionar --"
    
    # Resetear estado de los datos procesados para volver al inicio
    st.session_state.datos_procesados = None
    st.session_state.validaciones = None
    st.session_state.csv_file = None
    st.session_state.archivo_csv_path = None
    st.session_state.shop_order_real = None


# ============================================================
# VALIDACIÓN DE CAMPOS OBLIGATORIOS
# ============================================================
def validar_formulario():
    """Valida que todos los campos obligatorios estén completos"""
    errores = []
    
    if not shop_order or len(shop_order) != 10:
        errores.append("SHOP ORDER debe tener 10 caracteres")
    
    if not spec or len(spec) != 8:
        errores.append("SPEC debe tener 8 caracteres")
    
    if not badge or len(badge) != 5 or not badge.isdigit():
        errores.append("BADGE debe tener 5 dígitos")
    
    if not st.session_state.csv_file or not st.session_state.archivo_csv_path:
        errores.append("No se encontró el archivo CSV para el SHOP ORDER especificado")
    
    # Validar defectos tipo "OTROS"
    if defecto_1 == "OTROS" and not defecto_1_manual:
        errores.append("Debe especificar el Defecto 1 (OTROS)")
    if defecto_2 == "OTROS" and not defecto_2_manual:
        errores.append("Debe especificar el Defecto 2 (OTROS)")
    if defecto_3 == "OTROS" and not defecto_3_manual:
        errores.append("Debe especificar el Defecto 3 (OTROS)")
    
    return errores



# ============================================================
# SECCIÓN DE RESULTADOS
# ============================================================
# 1. Definir los nombres de las pestañas
if st.session_state.datos_procesados is not None:
#    nombres_tabs = ["📝 Datos y Formulario", "🔍 Validaciones", "📋 Datos Procesados", "📊 Estadística", "📉 SPC", "🔬 Global", "📄 Reporte"]
    nombres_tabs = ["📝 Datos y Formulario", "🔍 Validaciones", "📊 Estadística", "📉 SPC", "🔬 Global", "📄 Reporte"]
else:
    nombres_tabs = ["📝 Datos y Formulario"]

# 2. Crear las pestañas
tabs = st.tabs(nombres_tabs)

# 3. El primer tab SIEMPRE es el índice 0
tab_config = tabs[0]


with tab_config:
    # Título principal
    st.title("🧪 Automatización de límites para Flash/IR en Allegro")
    # ============================================================
    # SECCIÓN 1: INFORMACIÓN DE LOTE
    # ============================================================
    st.header("📋 Información de Lote de Prueba")

    col1, col2, col3 = st.columns(3)

    with col1:
        shop_order = st.text_input(
            "SHOP ORDER *",
            max_chars=10,
            help="Debe contener exactamente 10 caracteres",
            key="inp_shop_order"
        )
        
        if shop_order:
            st.session_state.csv_file = None
            st.session_state.archivo_csv_path = None
            
            if len(shop_order) == 10:
                # Capturamos los 4 valores: ruta, error, duplicados y fecha
                res = buscar_archivo_csv(shop_order)
                archivo_csv_path, error_msg, hay_duplicados, fecha_archivo = res

                if archivo_csv_path:
                    try:
                        # Mensaje si hay varios archivos
                        if hay_duplicados:
                            st.warning(f"⚠️ Se encontró más de un archivo. Usando el más reciente del: **{fecha_archivo}**")
                        else:
                            st.info(f"📄 Archivo encontrado con fecha: **{fecha_archivo}**")

                        with open(archivo_csv_path, 'rb') as archivo_fisico:
                            contenido_archivo = archivo_fisico.read()
                        
                        csv_file = io.BytesIO(contenido_archivo)
                        
                        st.session_state.csv_file = csv_file
                        st.session_state.archivo_csv_path = archivo_csv_path
                        st.session_state.shop_order_real = os.path.basename(archivo_csv_path).replace('.csv', '')[:10]
                        
                        st.success("✅ Shop Order, CSV OK!")                           
                    
                    except Exception as e:
                        st.error(f"❌ Error al leer el archivo: {str(e)}")
                else:
                    st.error(error_msg)
                    st.info(f"💡 Verifique en la ruta: {RUTA_ARCHIVOS_CSV}")
            else:
                st.warning("⚠️ El SHOP ORDER debe tener exactamente 10 caracteres")


    with col2:
        spec = st.text_input(
            "SPEC *",
            max_chars=8,
            help="Debe contener exactamente 8 caracteres",
            key="inp_spec"
        )
        if spec:
            if len(spec) != 8:
                st.error("❌ El SPEC debe tener exactamente 8 caracteres")
            else:
                st.success("✅ SPEC válido")
    with col3:
        badge = st.text_input(
            "BADGE *",
            max_chars=5,
            help="Debe contener exactamente 5 dígitos",
            key="inp_badge"
        )
        if badge:
            if len(badge) != 5 or not badge.isdigit():
                st.error("❌ El BADGE debe tener exactamente 5 dígitos numéricos")
            else:
                st.success("✅ BADGE válido")

    col4, col5, col6 = st.columns(3)


    with col4:
        turno = st.selectbox(
            "TURNO *",
            options=[1, 2, 3, 4],
            help="Seleccione el turno (1, 2, 3 o 4)",
            key="sel_turno"
        )

    with col5:
        maquina = st.selectbox(
            "MÁQUINA *",
            options=[1, 2, 3, 4],
            help="Seleccione la máquina (1, 2, 3 o 4)",
            key="sel_maquina"
        )

    with col6:
        fecha_prueba = st.date_input(
            "FECHA DE PRUEBA *",
#            value=date.today(),
            value=datetime.now(),
            help="Fecha se asigna automáticamente (puede modificarse)",
            key="inp_fecha"
        )

    col7_reproceso, col_limpiar = st.columns(2)
    with col7_reproceso:
        es_reproceso = st.checkbox(
            "🔄 Esta es una prueba de REPROCESO",
            help="Marque esta opción si esta prueba es un reproceso de un lote anterior",
            key="chk_reproceso"
        )

    with col_limpiar:
        st.button("🧹 Limpiar Formulario", use_container_width=True, on_click=limpiar_formulario_callback)

    st.markdown("---")
    # ============================================================
    # SECCIÓN 2: TIPO DE DEFECTOS
    # ============================================================
    st.header("🔍 Sección de Defectos")

    st.info("Puede especificar hasta 3 tipos de defectos. Si selecciona 'OTROS', deberá ingresar manualmente el defecto.")

    col7, col8, col9 = st.columns(3)

    opciones_defectos = ["-- Seleccionar --", "VOID", "STREAK", "TND", "PINHOLE", "OTROS"]

    with col7:
        defecto_1 = st.selectbox("TIPO DE DEFECTO 1", opciones_defectos, key="def1")
        if defecto_1 == "OTROS":
            defecto_1_manual = st.text_input("Especificar defecto 1:", max_chars=50, key="def1_man")
        else:
            defecto_1_manual = None

    with col8:
        defecto_2 = st.selectbox("TIPO DE DEFECTO 2", opciones_defectos, key="def2")
        if defecto_2 == "OTROS":
            defecto_2_manual = st.text_input("Especificar defecto 2:", max_chars=50, key="def2_man")
        else:
            defecto_2_manual = None

    with col9:
        defecto_3 = st.selectbox("TIPO DE DEFECTO 3", opciones_defectos, key="def3")
        if defecto_3 == "OTROS":
            defecto_3_manual = st.text_input("Especificar defecto 3:", max_chars=50, key="def3_man")
        else:
            defecto_3_manual = None
            
# ============================================================
# BOTÓN PROCESAR
# ============================================================
    st.markdown("---")
    st.header("🚀 Procesar Datos")

    if st.button("🔄 PROCESAR DATOS", type="primary", use_container_width=True):

        errores = validar_formulario()
        
        if errores:
            st.error("❌ **No se puede procesar. Corrija los siguientes errores:**")
            for error in errores:
                st.error(f"• {error}")
        else:
            # Limpiar límites manuales al procesar nuevos datos
            st.session_state.datos_limites_guardados = {
                "sup_flash": "", "inf_flash": "",
                "sup_ir": "", "inf_ir": ""
            }
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("🔄 Inicializando procesador...")
            progress_bar.progress(10)
            
            processor = CSVProcessor(min_mediciones_por_track=st.session_state.min_mediciones_guardado)
            st.session_state.processor = processor
            st.session_state.min_mediciones_utilizado = st.session_state.min_mediciones_guardado

            defectos_lista_procesada = []
            if defecto_1 != "-- Seleccionar --":
                defectos_lista_procesada.append(defecto_1_manual if defecto_1 == "OTROS" else defecto_1)
            if defecto_2 != "-- Seleccionar --":
                defectos_lista_procesada.append(defecto_2_manual if defecto_2 == "OTROS" else defecto_2)
            if defecto_3 != "-- Seleccionar --":
                defectos_lista_procesada.append(defecto_3_manual if defecto_3 == "OTROS" else defecto_3)
            
            st.session_state.defectos_procesados = defectos_lista_procesada if defectos_lista_procesada else None
            st.session_state.reproceso_procesado = es_reproceso
            
            # --- CÁLCULO DE SIGMA EFECTIVO ---
            sigma_efectivo = float(st.session_state.sigma_guardado)
            sigma_reproceso_resta = float(st.session_state.sigma_reproceso_guardado)
            st.session_state.sigma_ajustado_por_reglas = False
            
            if es_reproceso or len(defectos_lista_procesada) > 0:
                sigma_efectivo = max(1.0, sigma_efectivo - sigma_reproceso_resta)
                st.session_state.sigma_ajustado_por_reglas = True
                
            st.session_state.sigma_utilizado = sigma_efectivo

            status_text.text("📂 Leyendo y procesando archivo CSV...")
            progress_bar.progress(30)
            
            # Resetear el puntero del archivo
            st.session_state.csv_file.seek(0)
            
            exito, df_procesado, validaciones = processor.procesar_completo(st.session_state.csv_file)
            
            progress_bar.progress(80)
            
            tiene_errores_criticos = 'errores' in validaciones and validaciones['errores']
            
            if tiene_errores_criticos:
                progress_bar.progress(100)
                status_text.empty()
                
                st.error("❌ **ERROR CRÍTICO EN EL PROCESAMIENTO DE DATOS**")
                st.error("El archivo CSV no pudo ser procesado debido a los siguientes errores:")
                
                if 'errores' in validaciones:
                    for error in validaciones['errores']:
                        st.error(f"• {error}")
                
                st.warning("⚠️ **Por favor corrija los errores en el archivo CSV y vuelva a intentar.**")
                
            else:
                progress_bar.progress(100)
                status_text.text("✅ Procesamiento completado y Datos Guardados en Base de Datos")

                # Guardar estados básicos
                st.session_state.datos_procesados = df_procesado
                st.session_state.validaciones = validaciones
                st.session_state.procesamiento_exitoso = True
                
                # 1. Instanciar Analyzer
                analyzer_actual = StatsAnalyzer(df_procesado)
                st.session_state.stats_analyzer = analyzer_actual
                
                # 2. CALCULAR LEVENE INMEDIATAMENTE (Para evitar el desfase en BD)
                resultados_levene_frescos = {}
                cols_a_analizar = analyzer_actual.cols_ir

                for col in cols_a_analizar:
                    sensor_id = col.split('_')[0].lower()
                    llave = f"tracks_{sensor_id}"
                    # Guardamos el resultado en una variable local "fresca"
                    resultados_levene_frescos[llave] = analyzer_actual.test_levene_tracks(col)

                # Actualizar el session_state para el reporte visual
                st.session_state.resultados_levene = resultados_levene_frescos

                
                defectos_payload = []
                for d, m in [(defecto_1, defecto_1_manual), (defecto_2, defecto_2_manual), (defecto_3, defecto_3_manual)]:
                    if d != "-- Seleccionar --":
                        defectos_payload.append(m if d == "OTROS" and m else d)
                
                res_db = {} 

                if len(cols_a_analizar) >= 2:
                    for i, nombre_prueba in enumerate(["flash", "ir"]):
                        col = cols_a_analizar[i]
                        sensor_orig = col.split('_')[0].lower()
                        
                        # USAMOS resultados_levene_frescos en lugar de st.session_state
                        res_levene_local = resultados_levene_frescos.get(f"tracks_{sensor_orig}", {})
                        res_db[f"levene_{nombre_prueba}"] = "PASS" if res_levene_local.get('varianzas_iguales') else "FAIL"
                        
                        # ANOVA usando el analyzer recién creado
                        res_anova_local = analyzer_actual.anova_tracks(col)
                        p_val = res_anova_local.get('p_value')
                        res_db[f"anova_{nombre_prueba}"] = "PASS" if (p_val is not None and p_val > 0.05) else "FAIL"
                else:
                    res_db = {"levene_flash": "N/A", "anova_flash": "N/A", "levene_ir": "N/A", "anova_ir": "N/A"}

                # 3. Construir el Payload Final
                payload = {
                    "shop_order": st.session_state.get("shop_order_real") or shop_order,
                    "spec": spec,
                    "turno": turno,
                    "badge": badge,
                    "maquina": maquina,
                    "tipo_prueba": "REPROCESO" if es_reproceso else "ESTÁNDAR",
                    "defectos": ", ".join(defectos_payload) if defectos_payload else "NINGUNO",
                    "levene_flash": res_db["levene_flash"],
                    "anova_flash": res_db["anova_flash"],
                    "levene_ir": res_db["levene_ir"],
                    "anova_ir": res_db["anova_ir"]
                }


                exito_guardado, mensaje_guardado = guardar_en_bd_php(payload)
                
                if exito_guardado:
                    # Guardamos el mensaje en el estado para que sobreviva al rerun
                    st.session_state.mensaje_db_exito = mensaje_guardado
                    st.success(mensaje_guardado)
                else:
#                    st.error(f"❌ Error al guardar en BD: {mensaje_guardado}")

                    if validaciones.get('errores_criticos'):
                        for error in validaciones['errores_criticos']:
                            st.error(f"• {error}")
                    
                    if validaciones.get('advertencias'):
                        for advertencia in validaciones['advertencias']:
                            st.info(f"• {advertencia}")
                            
                time.sleep(3.0) 
                st.markdown("---")
                status_text.text("🚀 Finalizando y cargando análisis...")
                     
                st.rerun()
                
# ============================================================
# SECCIÓN 5: CONFIGURACIÓN DE VALIDACIÓN (PROTEGIDA)
# ============================================================
    st.header("⚙️ Configuración de Validación")

    with st.expander("🔐 **Menú de Configuración Avanzada** (Requiere código de acceso)", expanded=False):
        if st.session_state.limpiar_codigo:
            st.session_state.codigo_input = ""
            st.session_state.limpiar_codigo = False
        
        col_codigo1, col_codigo2 = st.columns([3, 1])
        
        with col_codigo1:
            codigo_ingresado = st.text_input(
                "Código de Acceso:",
                type="password",
                placeholder="Ingrese el código para acceder a la configuración",
                key="codigo_input"
            )
        
        with col_codigo2:
            st.write("")
            if st.button("🔓 Verificar", key="btn_verificar_codigo"):
                codigo = st.session_state.get("codigo_input", "").strip()
                if codigo == CODIGO_ACCESO_CONFIGURACION:
                    st.session_state.codigo_acceso_valido = True
                    st.success("✅ Código correcto. Acceso concedido.")
                    st.session_state.limpiar_codigo = True
                    st.experimental_rerun()
                else:
                    st.session_state.codigo_acceso_valido = False
                    st.error("❌ Código incorrecto. Intente de nuevo.")
        
        if st.session_state.codigo_acceso_valido:
            st.markdown("### 📊 Parámetros de Validación")
            
            col_config1, col_config2 = st.columns(2)
            
            with col_config1:
                min_mediciones_nuevo = st.number_input(
                    "Mínimo de mediciones válidas por track",
                    min_value=10,
                    max_value=1000,
                    value=st.session_state.min_mediciones_guardado,
                    step=10,
                )
                
            with col_config2:
                sigma_nuevo = st.number_input(
                    "Valor de Sigma (σ)",
                    min_value=2.0,
                    max_value=6.0,
                    value=float(st.session_state.sigma_guardado),
                    step=0.5,
                )
            col_alpha1, col_alpha2 = st.columns(2)
            with col_alpha1:
                alpha_flash_nuevo = st.number_input(
                    "Alpha para FLASH (Tukey)",
                    min_value=0.0001,
                    max_value=0.1000,
                    value=float(st.session_state.get('alpha_flash_guardado', 0.05)),
                    step=0.0001,
                    format="%.4f"
                )
            with col_alpha2:
                alpha_ir_nuevo = st.number_input(
                    "Alpha para IR (Tukey)",
                    min_value=0.0001,
                    max_value=0.1000,
                    value=float(st.session_state.get('alpha_ir_guardado', 0.05)),
                    step=0.0001,
                    format="%.4f"
                )
            col_rep1, col_rep2 = st.columns(2)
            with col_rep1:
                sigma_reproceso_nuevo = st.number_input(
                    "Sigma a restar en reproceso/defectos",
                    min_value=0.0,
                    max_value=6.0,
                    value=float(st.session_state.sigma_reproceso_guardado),
                    step=0.1,
                    format="%.1f",
                    help="Valor de sigma que se resta al Sigma configurado cuando la prueba es reproceso o lleva defectos"
                )
            
            col_btn = st.columns(1)
            with col_btn[0]:
                st.info(f"📊 Valores actuales: **{st.session_state.min_mediciones_guardado} mediciones**, **Sigma: {st.session_state.sigma_guardado}**, **Sigma a restar (reproceso): {st.session_state.sigma_reproceso_guardado}**")
                
                if st.button("💾 Guardar Configuración",  type="secondary", key="btn_guardar_config", use_container_width=True):
                    exito, mensaje = guardar_configuracion_validacion(min_mediciones_nuevo, sigma_nuevo, alpha_flash_nuevo, alpha_ir_nuevo, sigma_reproceso_nuevo)
                    if exito:
                        st.session_state.min_mediciones_guardado = min_mediciones_nuevo
                        st.session_state.sigma_guardado = sigma_nuevo
                        st.session_state.sigma_reproceso_guardado = sigma_reproceso_nuevo
                        st.session_state.alpha_flash_guardado = alpha_flash_nuevo
                        st.session_state.alpha_ir_guardado = alpha_ir_nuevo
                        st.success(mensaje)
                        st.info("🔄 Los nuevos valores se usarán en los próximos procesamientos")
                        
                        st.session_state.codigo_acceso_valido = False
                        st.info("🔒 Modo de edición cerrado. Ingrese el código nuevamente para modificar.")
                        st.session_state.limpiar_codigo = True
                        st.rerun()
                    else:
                        st.error(mensaje)
        else:
            min_mediciones_nuevo = st.session_state.min_mediciones_guardado
            sigma_nuevo = st.session_state.sigma_guardado
            sigma_reproceso_nuevo = st.session_state.sigma_reproceso_guardado
            st.info(f"ℹ️ Usando valores guardados: **{st.session_state.min_mediciones_guardado} mediciones**, **Sigma: {st.session_state.sigma_guardado}**, **Sigma a restar (reproceso): {st.session_state.sigma_reproceso_guardado}**")



if st.session_state.datos_procesados is not None and len(tabs) > 1:
    # Crea un iterador de la lista de pestañas (saltando la 0)
    it = iter(tabs[1:]) 
    
    # Asigna usando next() en el orden que aparecen en tu lista nombres_tabs
    tab_val = next(it)
    #tab_datos = next(it)
    tab_est = next(it)
    tab_spc = next(it)
    tab_global = next(it)
    tab_print = next(it)
    
    
    with tab_val:
        st.subheader("Validaciones Detalladas por Track")
        
        validaciones = st.session_state.validaciones
        # Obtenemos el valor mínimo usado en el procesamiento desde el session_state
        min_requerido = st.session_state.get('min_mediciones_utilizado', st.session_state.min_mediciones_guardado)
        
        for track in range(1, 9):
            if track in validaciones['tracks_validados']:
                track_info = validaciones['tracks_validados'][track]
                
                # 1. Definir el estado y el mensaje dinámico
                if track_info['aprobado']:
                    estado_icon = "✅"
                    mensaje_estado = "APROBADO"
                else:
                    estado_icon = "❌"
                    # Verificamos si el rechazo es específicamente por falta de mediciones
                    if track_info['total_mediciones'] < min_requerido:
                        mensaje_estado = f"RECHAZADO, NO CUMPLE CON EL VALOR MÍNIMO DE MEDICIONES (Mínimo: {min_requerido})"
                    else:
                        mensaje_estado = "RECHAZADO"

                titulo_expander = f"{estado_icon} Track {track} - {mensaje_estado}"
                
                with st.expander(titulo_expander):
                    # 2. Información General del Track
                    st.write(f"**Total mediciones válidas combinadas:** {track_info['total_mediciones']}")
                    
                    # Mostrar una alerta visual si no cumple las mediciones dentro del expander
                    if track_info['total_mediciones'] < min_requerido:
                        st.warning(f"⚠️ Este track solo tiene {track_info['total_mediciones']} de las {min_requerido} mediciones requeridas por cada Track.")
                    
                    st.markdown("---")
                    
                    # 3. Identificar dinámicamente qué sensores IR existen en este track
                    sensores_encontrados = [k.replace('mediciones_validas_', '') 
                                          for k in track_info.keys() if k.startswith('mediciones_validas_')]
                    
                    if sensores_encontrados:
                        cols_track = st.columns(len(sensores_encontrados))
                        
                        for i, nombre_ir in enumerate(sensores_encontrados):
                            with cols_track[i]:
                                st.markdown(f"**Análisis {nombre_ir.upper()}**")
                                
                                m_validas = track_info.get(f'mediciones_validas_{nombre_ir}', 0)
                                tiene_neg = track_info.get(f'tiene_negativos_{nombre_ir}', False)
                                tiene_ceros = track_info.get(f'tiene_ceros_repetitivos_{nombre_ir}', False)
                                
                                st.write(f"• Mediciones válidas: {m_validas}")
                                st.write(f"• Tiene negativos: {'❌ Sí' if tiene_neg else '✅ No'}")
                                st.write(f"• Ceros repetitivos: {'⚠️ Sí' if tiene_ceros else '✅ No'}")

#Tab oculto (tab_datos)     
#    with tab_datos:
        st.subheader("Vista de Datos Procesados")
        
        tracks_disponibles = sorted(st.session_state.datos_procesados['Track'].unique().tolist())
        tracks_seleccionados = st.multiselect(
            "🔍 Filtrar por Track",
            options=tracks_disponibles,
            default=tracks_disponibles,
            help="Selecciona los tracks que quieres visualizar. Por defecto muestra todos."
        )
        
        df_filtrado = st.session_state.datos_procesados[
            st.session_state.datos_procesados['Track'].isin(tracks_seleccionados)
        ].copy()

        if 'IR3_uA' in df_filtrado.columns:
            df_filtrado['IR3_uA'] = df_filtrado['IR3_uA'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else x)
        if 'IR4_nA' in df_filtrado.columns:
            df_filtrado['IR4_nA'] = df_filtrado['IR4_nA'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else x)
        
        st.info(f"📊 Mostrando {len(df_filtrado)} de {len(st.session_state.datos_procesados)} registros")
        
        st.dataframe(df_filtrado, use_container_width=True)

        csv_download = st.session_state.datos_procesados[
            st.session_state.datos_procesados['Track'].isin(tracks_seleccionados)
        ].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos procesados (CSV)",
            data=csv_download,
            file_name=f"datos_procesados_{shop_order}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with tab_est:
        st.subheader("📊 Análisis Estadístico - Test de Levene")
        
        if st.session_state.resultados_levene:
            st.markdown("---")

            # 1. Identificar sensores presentes dinámicamente
            # Buscamos llaves como 'tracks_ir1', 'tracks_ir3', etc.
            llaves_sensores = sorted([k for k in st.session_state.resultados_levene.keys() if k.startswith('tracks_')])
            
            if llaves_sensores:
                # Crear columnas dinámicas (ej: si hay 2 sensores, crea col1, espacio, col2)
                # Usamos un ratio [1, 0.04, 1] para mantener la estética original
                ratios = []
                for i in range(len(llaves_sensores)):
                    ratios.append(1)
                    if i < len(llaves_sensores) - 1:
                        ratios.append(0.04) # Espaciador
                
                cols_dinamicas = st.columns(ratios)

                for idx, llave in enumerate(llaves_sensores):
                    # Extraer el ID del sensor (ej: 'ir3')
                    sensor_id = llave.replace('tracks_', '')
                    # Calcular el índice real de la columna (saltando los espaciadores)
                    col_index = idx * 2
                    
                    with cols_dinamicas[col_index]:
                        st.markdown(f"#### 📈​ Test de Levene: {sensor_id.upper()} entre Tracks")
                        st.markdown(f"**Pregunta:** ¿Tienen todos los tracks varianzas iguales en {sensor_id.upper()}?")
                        
                        res_levene = st.session_state.resultados_levene[llave]
                        st.metric("Estadístico F", res_levene['estadistico'])
                        st.metric("P-value", res_levene['p_value'])

                        st.write("**Varianzas por Track:**")
                        for track, var in res_levene['varianzas_por_track'].items():
                            st.write(f"- {track}: {var}")

                        st.success(res_levene['conclusion'])

                        st.markdown("---")
                        st.markdown(f"**🔍 Identificación de Varianzas Problemáticas ({sensor_id.upper()})**")
                        st.info(f"Análisis MAD para {sensor_id.upper()} (Outliers de varianza).")

                        # Llamada dinámica a funciones de varianza
                        func_var_name = f"analizar_varianzas_diferentes_{sensor_id}"
                        analizar_var = getattr(st.session_state.stats_analyzer, func_var_name, None)
                        # Obtenemos la columna real de la lista detectada (ej. 'IR1_uA' o 'IR2_nA')
                        columna_real = st.session_state.stats_analyzer.cols_ir[idx]
                        
                        # Llamada directa a la nueva función maestra
                        res_var = st.session_state.stats_analyzer.analizar_varianzas_diferentes(columna_real)

                        if 'error' not in res_var:
                            resumen = res_var['resumen']
                            if resumen['tracks_problematicos']:
                                st.write(f"**❌ Tracks con varianzas problemáticas: {sensor_id.upper()}**")
                                for t_info in resumen['tracks_problematicos']:
                                    color = "🔴" if t_info['consenso'] else "🟡"
                                    # Mostramos la varianza si está disponible, o un texto genérico
                                    var_val = t_info.get('varianza', 'Atípica')
                                    st.write(f"{color} **{t_info['track']}**: var = {var_val} ({', '.join(t_info['metodos_detecta'])})")
                                    # Si var_val es un número, le damos formato; si no, lo dejamos como texto
                                    if isinstance(var_val, (int, float)):
                                        var_str = f"{var_val:.4f}"
                                    else:
                                        var_str = str(var_val)
                                    
                            else:
                                st.success(f"✅ Sin varianzas problemáticas en {sensor_id.upper()}")
                            
                            st.warning(resumen['recomendacion'])
                            
                            # Detalles MAD - Ahora sí se mostrará
                            with st.expander(f"📊 Detalles MAD para {sensor_id.upper()}"):
                                if 'analisis_completo' in res_var and 'mad' in res_var['analisis_completo']:
                                    mad_res = res_var['analisis_completo']['mad']
                                    st.metric("Mediana de Varianzas", mad_res['estadisticas'].get('mediana', 'N/A'))
                                    st.metric("Valor MAD", mad_res['estadisticas'].get('mad', 'N/A'))
                                    
                                    if mad_res.get('outliers'):
                                        nombres_outliers = [o['id'] if isinstance(o, dict) else str(o) for o in mad_res['outliers']]
                                        st.error(f"Outliers detectados: {', '.join(nombres_outliers)}")
                                    else:
                                        st.success("No se detectaron varianzas fuera de lo común.")
                        else:
                            st.warning(f"No se pudo analizar {sensor_id.upper()}: {res_var.get('error')}")


                        # --- ANOVA ---
                        st.markdown("---")
                        st.markdown(f"#### 📊 ANOVA: {sensor_id.upper()}")
                        
                        # Llamamos directamente a la función maestra anova_tracks
                        # usando el nombre de la columna real (ej: 'IR1_uA' o 'IR3_uA')
                        columna_real = f"{sensor_id.upper()}_uA" if idx == 0 else f"{sensor_id.upper()}_nA"
                        
                        # Intentar obtener el resultado
                        res_anova = st.session_state.stats_analyzer.anova_tracks(columna_real)
                        
                        if res_anova['estadistico_f'] is not None:
                            c1, c2 = st.columns(2)
                            c1.metric("Estadístico F", res_anova['estadistico_f'])
                            c1.metric("P-value", res_anova['p_value'])
                            df_b, df_w = res_anova['grados_libertad']
                            c2.metric("GL (Between)", df_b)
                            c2.metric("GL (Within)", df_w)
                            
                            st.write("**Medias por Track:**")
                            for track, media in res_anova['medias_por_track'].items():
                                st.write(f"- {track}: {media}")
                            st.success(res_anova['conclusion'])
                        else:
                            st.warning(res_anova['conclusion'])


                        # --- TUKEY ---
                                                # --- TUKEY ---
                        st.markdown("---")
                        st.markdown(f"#### 🔍 Tukey HSD: {sensor_id.upper()}")

                        # Usamos la columna real detectada (ej. 'IR1_uA' o 'IR3_uA')
                        columna_real = st.session_state.stats_analyzer.cols_ir[idx]
                        # Usar el alpha configurado según el sensor
                        if idx == 0:
                            alpha_usar = st.session_state.get('alpha_flash_guardado', 0.05)
                        else:
                            alpha_usar = st.session_state.get('alpha_ir_guardado', 0.05)
                        res_tukey = st.session_state.stats_analyzer.tukey_hsd(columna_real, alpha=alpha_usar)

                        if res_tukey['comparaciones']:
                            ct1, ct2 = st.columns(2)
                            with ct1:
                                st.markdown("**Resumen:**")
                                st.info(res_tukey['resumen'])
                            with ct2:
                                st.markdown("**Diferencias significativas:**")
                                comp_sig = [c for c in res_tukey['comparaciones'] if c['reject']]
                                if comp_sig:
                                    for cp in comp_sig:
                                        # Mostramos también el alpha actual para referencia
                                        st.error(f"❌ {cp['group1']} vs {cp['group2']}: p={cp['p_adj']} (α={alpha_usar})")
                                else:
                                    st.success(f"✅ Sin diferencias significativas (α={alpha_usar})")
                            
                            # Mostrar tabla completa de resultados
                            st.markdown("**📋 Detalle de comparaciones:**")
                            df_tukey = pd.DataFrame(res_tukey['comparaciones'])
                            st.dataframe(
                                df_tukey[['group1', 'group2', 'meandiff', 'p_adj', 'significativo2']], 
                                use_container_width=True
                            )
                        else:
                            st.warning(res_tukey['resumen'])

            else:
                st.info("No se detectaron datos de sensores IR para el análisis.")
        else:
            st.warning("⚠️ Los análisis estadísticos aún no se han ejecutado. Por favor procesa los datos primero.")


    with tab_spc:
        st.subheader("📉 Gráficas de Control I-MR (Statistical Process Control)")
        st.info("Las gráficas I-MR evalúan la estabilidad del proceso a lo largo del tiempo. El Rango Móvil (MR) mide la variabilidad entre una muestra y la siguiente.")
        st.warning("⚠️ **Nota importante:** Si los datos no están ordenados cronológicamente en el CSV, el MR mostrará saltos falsos al cambiar de Track. Se recomienda seleccionar un Track específico para un análisis preciso.")
        
        # Controles de selección dinámicos
        col_select1, col_select2 = st.columns(2)
        
        with col_select1:
            # Detectar qué tracks existen realmente en los datos
            tracks_existentes = sorted(st.session_state.datos_procesados['Track'].unique())
            opciones_tracks = ["Global (Todos los datos en orden)"] + [f"Track {int(t)}" for t in tracks_existentes]
            
            opcion_datos = st.selectbox(
                "Evaluar por:",
                options=opciones_tracks,
                index=0
            )
        
        with col_select2:
            # Detectar dinámicamente las columnas de sensores disponibles (IR1_uA, IR2_nA, etc.)
            columnas_disponibles = [c for c in st.session_state.datos_procesados.columns if c.endswith('_uA') or c.endswith('_nA')]
            
            columna_medida = st.selectbox(
                "Variable a analizar:",
                options=columnas_disponibles,
                format_func=lambda x: x.replace('_', ' (') + ')' # Formatea 'IR3_uA' a 'IR3 (uA)'
            )
        
        # Filtrar datos según selección
        df_para_imr = st.session_state.datos_procesados.copy()
        
        if "Track" in opcion_datos:
            # Extraer el número de track de la cadena "Track X"
            track_num = int(opcion_datos.split(" ")[1])
            df_para_imr = df_para_imr[df_para_imr['Track'] == track_num].reset_index(drop=True)
            st.markdown(f"**Filtrando datos exclusivamente del {opcion_datos}**")
        else:
            df_para_imr = df_para_imr.reset_index(drop=True)
            st.markdown("**Mostrando todos los datos en su orden secuencial actual en el archivo**")
        
        # Crear un analizador temporal para este subconjunto
        analyzer_imr = StatsAnalyzer(df_para_imr)
        
        # Calcular límites usando el método dinámico
        limites = analyzer_imr.calcular_limites_imr(columna_medida)
        
        if 'error' in limites:
            st.error(limites['error'])
        else:
            # Mostrar métricas de los límites calculados
            st.markdown("### Límites de Control Calculados")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            with col_m1:
                st.metric("Media (Línea Central)", limites['media_i'])
            with col_m2:
                st.metric("UCL (Límite Superior)", limites['ucl_i'])
            with col_m3:
                st.metric("LCL (Límite Inferior)", limites['lcl_i'])
            with col_m4:
                st.metric("N Observaciones", limites['n_observaciones'])

            
            # --- GENERAR GRÁFICOS CON MATPLOTLIB ---
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
            
            # Detectar unidad dinámicamente para las etiquetas de los ejes
            unidad = "μA" if "_uA" in columna_medida else "nA"
            sensor_id = columna_medida.split('_')[0]
            
            fig.suptitle(f'Gráficas I-MR: {sensor_id} ({opcion_datos})', fontsize=16, fontweight='bold')
            
            # Gráfica Superior: Individuos (I)
            datos_i = limites['datos_i']
            ax1.plot(datos_i, marker='o', linestyle='-', color='steelblue', markersize=4, label=f'Valor Individual ({unidad})')
            ax1.axhline(limites['media_i'], color='green', linestyle='--', linewidth=2, label=f"Media ({limites['media_i']})")
            ax1.axhline(limites['ucl_i'], color='red', linestyle='--', linewidth=2, label=f"UCL ({limites['ucl_i']})")
            ax1.axhline(limites['lcl_i'], color='red', linestyle='--', linewidth=2, label=f"LCL ({limites['lcl_i']})")
            
            # --- Agregar límites manuales si existen para esta columna ---
            _cols_ir_map = st.session_state.stats_analyzer.cols_ir
            if len(_cols_ir_map) >= 2:
                if columna_medida == _cols_ir_map[0]:
                    _s_key, _i_key, _lbl = "sup_flash", "inf_flash", "FLASH"
                elif columna_medida == _cols_ir_map[1]:
                    _s_key, _i_key, _lbl = "sup_ir", "inf_ir", "IR"
                else:
                    _s_key = _i_key = _lbl = None
                if _s_key:
                    _dl = st.session_state.datos_limites_guardados
                    try:
                        _sv = float(_dl[_s_key]) if _dl[_s_key] else None
                        _iv = float(_dl[_i_key]) if _dl[_i_key] else None
                        if _sv is not None:
                            ax1.axhline(_sv, color='purple', linestyle='-.', linewidth=2, label=f"UCL Manual ({_lbl}: {_sv} {unidad})")
                        if _iv is not None:
                            ax1.axhline(_iv, color='purple', linestyle='-.', linewidth=2, label=f"LCL Manual ({_lbl}: {_iv} {unidad})")
                    except ValueError:
                        pass
            
            # Resaltar out of control en I (usando los índices detectados por el analyzer)
            ooc_i = datos_i.iloc[limites.get('outliers_i', [])]
            if not ooc_i.empty:
                ax1.scatter(ooc_i.index, ooc_i, color='red', s=60, zorder=5, label='Fuera de Control', edgecolors='black')
            
            ax1.set_ylabel(f'Medición ({unidad})')
            ax1.legend(loc='upper right', fontsize='small')
            ax1.grid(True, alpha=0.3)
            ax1.set_title('Gráfica I (Individuos)')
            
            # Gráfica Inferior: Rango Móvil (MR)
            datos_mr = limites['datos_mr']
            ax2.plot(datos_mr.index, datos_mr, marker='s', linestyle='-', color='orange', markersize=4, label='Rango Móvil')
            ax2.axhline(limites['media_mr'], color='green', linestyle='--', linewidth=2, label=f"Media MR ({limites['media_mr']})")
            ax2.axhline(limites['ucl_mr'], color='red', linestyle='--', linewidth=2, label=f"UCL MR ({limites['ucl_mr']})")
            ax2.axhline(limites['lcl_mr'], color='red', linestyle='--', linewidth=2, label=f"LCL MR ({limites['lcl_mr']})")
            
            # Resaltar out of control en MR
            ooc_mr = datos_mr.iloc[limites.get('outliers_mr', [])]
            if not ooc_mr.empty:
                ax2.scatter(ooc_mr.index, ooc_mr, color='red', s=60, zorder=5, label='Fuera de Control', edgecolors='black')
            
            ax2.set_xlabel('Índice de Muestra Secuencial')
            ax2.set_ylabel(f'MR ({unidad})')
            ax2.legend(loc='upper right', fontsize='small')
            ax2.grid(True, alpha=0.3)
            ax2.set_title('Gráfica MR (Rango Móvil)')
            
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            st.pyplot(fig)
            
            # --- ANÁLISIS DE OUTLIERS ---
            n_ooc_i = len(ooc_i)
            n_ooc_mr = len(ooc_mr)
            
            st.markdown("---")
            if n_ooc_i > 0 or n_ooc_mr > 0:
                st.error(f"🚨 **Se detectaron puntos fuera de control:** {n_ooc_i} en la gráfica I, {n_ooc_mr} en la gráfica MR.")
                if n_ooc_i > 0:
                    st.warning(f"Índices fuera de control (I): {', '.join(map(str, ooc_i.index.tolist()))}")
                if n_ooc_mr > 0:
                    st.warning(f"Índices fuera de control (MR): {', '.join(map(str, ooc_mr.index.tolist()))}")
            else:
                st.success("✅ **El proceso se encuentra bajo control estadístico.**")

    # --- TAB 6: FUSIÓN GLOBAL DINÁMICA ---
    with tab_global:
        st.subheader("🔬 Gráficas I-MR Globales (Población Fusionada)")
        st.info("Tratamiento de los datos como una secuencia continua. Límites calculados basados en el Rango Móvil promedio global.")
        
        # Seleccionador de Sigma dinámico desde configuración
        sigma_val = st.session_state.sigma_utilizado
        if st.session_state.get('sigma_ajustado_por_reglas', False):
            sigma_resta_msg = st.session_state.get('sigma_reproceso_guardado', 1.0)
            st.warning(f"⚠️ **Ajuste automático:** Se restó {sigma_resta_msg} al Sigma configurado (ahora {sigma_val}) debido a que es un reproceso o tiene defectos.")
        
        # Detectar qué columnas IR existen en el objeto analyzer
        cols_ir = st.session_state.stats_analyzer.cols_ir
        
        # Crear columnas en la UI según cuántos sensores haya
        cols_ui = st.columns(len(cols_ir))
        
        for idx, col in enumerate(cols_ir):
            with cols_ui[idx]:
                res_global = st.session_state.stats_analyzer.calcular_limites_imr_global(col, sigma=sigma_val)
                
                if 'error' not in res_global:
                    # Extraer ID del sensor (ej: 'IR1') y su unidad para mostrar
                    sensor_id = res_global.get('sensor', col.split('_')[0])
                    unidad = res_global.get('unidad', '')
                    
                    st.markdown(f"### Análisis Global: {sensor_id} ({unidad})")
                    
                    # Calcular los conteos a partir de las listas de outliers
                    conteo_i = len(res_global.get('outliers_i', []))
                    conteo_mr = len(res_global.get('outliers_mr', []))
                    
                    # Mostrar métricas principales
                    col_met1, col_met2, col_met3 = st.columns(3)
                    with col_met1:
                        st.metric(f"Media", res_global['media_i'])
                    with col_met2:
                        st.metric(f"UCL ({sigma_val}σ)", res_global['ucl_i'])
                    with col_met3:
                        st.metric(f"Puntos Fuera Control", conteo_i)
                    
                    # Mensajes de estado dinámicos
                    if conteo_i > 0:
                        st.error(f"⚠️ {sensor_id}: Se detectaron {conteo_i} puntos fuera de los límites de control.")
                        with st.expander("Ver índices afectados"):
                            st.write(f"Índices: {res_global.get('outliers_i', [])}")
                    else:
                        st.success(f"✅ {sensor_id} se mantiene estable bajo los límites de {sigma_val} sigma.")
                        
                    if conteo_mr > 0:
                        st.warning(f"🔔 Nota: {conteo_mr} saltos de variabilidad (MR) detectados.")
                else:
                    st.error(f"Error en {col}: {res_global['error']}")
   
    # ============================================================
    # NUEVA PESTAÑA: I-MR GLOBAL FUSIONADO (SIGMA DINÁMICO) DEFAUL 3 SIGMA
    # ============================================================
    with tab_global:
        st.subheader("🔬 Gráficas I-MR Globales (Población Fusionada)")
        st.markdown("Tratamiento de los datos como una sola secuencia continua ignorando la segmentación por Tracks.")
        
        # --- SELECTOR DINÁMICO DE SIGMA ---
        sigma_seleccionado = st.session_state.sigma_utilizado
        if st.session_state.get('sigma_ajustado_por_reglas', False):
            sigma_resta_msg = st.session_state.get('sigma_reproceso_guardado', 1.0)
            st.warning(f"⚠️ **Ajuste automático:** Usando el valor de Sigma reducido: {sigma_seleccionado} (resta de {sigma_resta_msg} por reproceso o defectos).")
        else:
            st.info(f"Usando el valor de Sigma configurado globalmente: {sigma_seleccionado}")
        
        st.markdown("---")
        
        # 1. Detectar dinámicamente qué sensores hay en el analizador
        columnas_ir = st.session_state.stats_analyzer.cols_ir
        
        # 2. Iterar sobre cada sensor detectado
        for col in columnas_ir:
            # Obtener resultados globales para el sensor actual
            res_global = st.session_state.stats_analyzer.calcular_limites_imr_global(col, sigma=sigma_seleccionado)
            
            if 'error' not in res_global:
                # Extraer información dinámica
                sensor_id = res_global['sensor']
                unidad = res_global['unidad']
                conteo_ooc = len(res_global.get('outliers_i', []))
                
                st.markdown(f"#### {sensor_id} ({unidad}) - Secuencia Global ({sigma_seleccionado} Sigma)")
                
                # Mostrar métricas superiores
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Media", res_global['media_i'])
                c2.metric("UCL", res_global['ucl_i'])
                c3.metric("LCL", res_global['lcl_i'])
                c4.metric("Desv. Std (σ)", res_global['std_global'])
                c5.metric("Pts Fuera de Control", conteo_ooc)
                
                # --- GENERAR GRÁFICA CON MATPLOTLIB ---
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
                fig.suptitle(f'I-MR Global: {sensor_id} ({sigma_seleccionado} Sigma)', fontsize=14, fontweight='bold')
                
                # Gráfica I (Individuos)
                ax1.plot(res_global['datos_i'], color='steelblue', linewidth=1, label=f"Valor Individual")
                ax1.axhline(res_global['media_i'], color='green', linestyle='--', linewidth=1.5)
                ax1.axhline(res_global['ucl_i'], color='red', linestyle='--', linewidth=1.5)
                ax1.axhline(res_global['lcl_i'], color='red', linestyle='--', linewidth=1.5)

                # --- Agregar límites manuales si existen para esta columna ---
                _cols_ir_g = st.session_state.stats_analyzer.cols_ir
                if len(_cols_ir_g) >= 2:
                    if col == _cols_ir_g[0]:
                        _s_key, _i_key, _lbl = "sup_flash", "inf_flash", "FLASH"
                    elif col == _cols_ir_g[1]:
                        _s_key, _i_key, _lbl = "sup_ir", "inf_ir", "IR"
                    else:
                        _s_key = _i_key = _lbl = None
                    if _s_key:
                        _dl = st.session_state.datos_limites_guardados
                        try:
                            _sv = float(_dl[_s_key]) if _dl[_s_key] else None
                            _iv = float(_dl[_i_key]) if _dl[_i_key] else None
                            if _sv is not None:
                                ax1.axhline(_sv, color='purple', linestyle='-.', linewidth=2, label=f"UCL Manual ({_lbl}: {_sv})")
                            if _iv is not None:
                                ax1.axhline(_iv, color='purple', linestyle='-.', linewidth=2, label=f"LCL Manual ({_lbl}: {_iv})")
                        except ValueError:
                            pass
                
                # Resaltar puntos fuera de control usando los índices detectados
                idx_ooc_i = res_global.get('outliers_i', [])
                if idx_ooc_i:
                    ooc_data = res_global['datos_i'].iloc[idx_ooc_i]
                    ax1.scatter(ooc_data.index, ooc_data, color='red', s=25, zorder=5, label="Fuera de Control")
                
                ax1.set_ylabel(f'Valor {unidad}')
                ax1.grid(True, alpha=0.3)
                ax1.set_title("Gráfica I (Individuos)")
                
                # Gráfica MR (Rango Móvil)
                ax2.plot(res_global['datos_mr'].index, res_global['datos_mr'], color='orange', linewidth=1)
                ax2.axhline(res_global['media_mr'], color='green', linestyle='--', linewidth=1.5)
                ax2.axhline(res_global['ucl_mr'], color='red', linestyle='--', linewidth=1.5)
                
                # Resaltar puntos fuera de control en MR
                idx_ooc_mr = res_global.get('outliers_mr', [])
                if idx_ooc_mr:
                    ooc_mr_data = res_global['datos_mr'].iloc[idx_ooc_mr]
                    ax2.scatter(ooc_mr_data.index, ooc_mr_data, color='red', s=25, zorder=5)
                
                ax2.set_xlabel('Índice Secuencial Global')
                ax2.set_ylabel(f'Rango Móvil ({unidad})')
                ax2.grid(True, alpha=0.3)
                ax2.set_title("Gráfica MR (Rango Móvil)")
                
                plt.tight_layout()
                st.pyplot(fig)
                st.markdown("---")
            else:
                st.error(f"Error procesando {col}: {res_global['error']}")

    with tab_print:
        # =====================================================================
        # CONTROLES DE ENTRADA CON FORMULARIO AUTO-OCULTABLE
        # =====================================================================
        #st.markdown("### ?? Configuración de Límites Manuales")
        
        if not st.session_state.mostrar_formulario_limites:
            if st.button("Ingresar límites manuales", key="btn_abrir_limites"):
                st.session_state.mostrar_formulario_limites = True
                st.rerun()
        else:
            if st.button("Cancelar / Ocultar panel", key="btn_cerrar_limites"):
                st.session_state.mostrar_formulario_limites = False
                st.rerun()

        if st.session_state.mostrar_formulario_limites:
            with st.form("formulario_limites_manuales", clear_on_submit=False):
                st.markdown("✍️ **Modifique los límites y presione 'Guardar' para actualizar la tabla y ocultar este panel**")
                col_flash, col_ir = st.columns(2)
                
                with col_flash:
                    st.markdown("**Límites para FLASH**")
                    txt_sup_flash = st.text_input("Límite Superior (FLASH)", value=st.session_state.datos_limites_guardados["sup_flash"])
                    txt_inf_flash = st.text_input("Límite Inferior (FLASH)", value=st.session_state.datos_limites_guardados["inf_flash"])
                
                with col_ir:
                    st.markdown("**Límites para IR**")
                    txt_sup_ir = st.text_input("Límite Superior (IR)", value=st.session_state.datos_limites_guardados["sup_ir"])
                    txt_inf_ir = st.text_input("Límite Inferior (IR)", value=st.session_state.datos_limites_guardados["inf_ir"])
                
                boton_guardar = st.form_submit_button("Guardar Límites")
                
                if boton_guardar:
                    st.session_state.datos_limites_guardados["sup_flash"] = txt_sup_flash
                    st.session_state.datos_limites_guardados["inf_flash"] = txt_inf_flash
                    st.session_state.datos_limites_guardados["sup_ir"] = txt_sup_ir
                    st.session_state.datos_limites_guardados["inf_ir"] = txt_inf_ir
                    st.session_state.mostrar_formulario_limites = False
                    st.rerun()

        #st.markdown("---") 

        # --- CSS PARA IMPRIMIR EN UNA SOLA PÁGINA ---
        st.markdown("""
            <style>
                @media print {
                    .main .block-container {
                        padding-top: 0.1rem !important;
                        padding-bottom: 0.1rem !important;
                        margin-top: -50px !important;
                        max-width: 100% !important;
                    }
                    [data-testid="stHeader"],
                    [data-testid="stDecoration"],
                    [data-testid="stToolbar"] {
                        display: none !important;
                    }
                    h2, h3, h4, h5, h6 {
                        margin-top: 1px !important;
                        margin-bottom: 1px !important;
                        padding-top: 0 !important;
                        padding-bottom: 0 !important;
                    }
                    .stTabs [role="tablist"], .stButton, iframe {
                        display: none !important;
                    }
                    .main * {
                        font-size: 7.5pt !important;
                        line-height: 1.05 !important;
                    }
                    .main h3 { font-size: 11pt !important; }
                    .main h4 { font-size: 9.5pt !important; }
                    .stMetric { margin: 0 !important; padding: 0 !important; }
                    .row-widget { margin-bottom: 0 !important; padding-bottom: 0 !important; }
                    .stColumn > div { padding: 0 2px !important; }
                    table td, table th { padding: 1px 3px !important; font-size: 7pt !important; }
                    .element-container { margin-bottom: 0 !important; }
                    .stMarkdown { margin-bottom: 0 !important; padding-bottom: 0 !important; }
                    [data-testid="column"] { padding: 0 2px !important; }
                    .stVerticalBlock { gap: 2px !important; }
                    @page {
                        margin: 0.3cm;
                        size: A4 portrait;
                    }
                }
            </style>
        """, unsafe_allow_html=True)

        # --- TÍTULO COMPACTO ---
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px">
        <h3 style="margin:0;padding:0;font-size:14px">📊 Reporte Cálculo de Límites</h3>
        <span style="font-size:10px">{datetime.combine(fecha_prueba, datetime.now().time()).strftime('%d/%m/%Y - %H:%M:%S')}</span>
        </div>
        """, unsafe_allow_html=True)

        # --- INFORMACIÓN DEL LOTE (HTML COMPACTO) ---
        defectos_seleccionados = []
        for d, m in [(defecto_1, defecto_1_manual), (defecto_2, defecto_2_manual), (defecto_3, defecto_3_manual)]:
            if d != "-- Seleccionar --":
                defectos_seleccionados.append(m if d == "OTROS" and m else d)

        texto_sigma = str(st.session_state.sigma_utilizado)
        if st.session_state.get('sigma_ajustado_por_reglas', False):
            sigma_resta_msg = st.session_state.get('sigma_reproceso_guardado', 1.0)
            sigma_base_msg = st.session_state.get('sigma_guardado', '')
            texto_sigma = f"{st.session_state.sigma_utilizado} (Reducido: {sigma_base_msg} - {sigma_resta_msg})"

        lhs = [
            ("SHOP ORDER", st.session_state.get("shop_order_real") or shop_order),
            ("SPEC", spec), ("TURNO", turno), ("BADGE", badge),
            ("MÁQUINA", maquina),
            ("TIPO", "🔄 REPROCESO" if es_reproceso else "ESTÁNDAR"),
            ("DEFECTOS", ", ".join(defectos_seleccionados) if defectos_seleccionados else "NINGUNO"),
            ("SIGMA", texto_sigma)
        ]

        tiene_limites = any(st.session_state.datos_limites_guardados.values())
        if tiene_limites:
            lhs.append(("LÍM SUP FLASH", st.session_state.datos_limites_guardados["sup_flash"] or "N/A"))
            lhs.append(("LÍM INF FLASH", st.session_state.datos_limites_guardados["inf_flash"] or "N/A"))
            lhs.append(("LÍM SUP IR", st.session_state.datos_limites_guardados["sup_ir"] or "N/A"))
            lhs.append(("LÍM INF IR", st.session_state.datos_limites_guardados["inf_ir"] or "N/A"))

        html_rows = "<tr>"
        for i, (c, v) in enumerate(lhs):
            html_rows += f"<td style='padding:1px 5px;font-size:8pt'><b>{c}:</b> {v}</td>"
            if (i + 1) % 4 == 0 and i + 1 < len(lhs):
                html_rows += "</tr><tr>"
        html_rows += "</tr>"

        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;border:1px solid #ccc;margin-bottom:4px">
        {html_rows}
        </table>
        """, unsafe_allow_html=True)

        # --- GRÁFICAS + VALORES LADO A LADO ---
        st.markdown(f"<h4 style='margin:3px 0 1px 0;padding:0;font-size:10pt'>📈 Gráficas de Control</h4>", unsafe_allow_html=True)

        if st.session_state.stats_analyzer:
            cols_ir = st.session_state.stats_analyzer.cols_ir
            mapeo_nombres = {cols_ir[0]: "FLASH", cols_ir[1]: "IR"} if len(cols_ir) >= 2 else {}

            for col in cols_ir[:2]:
                tipo_prueba = mapeo_nombres.get(col, col.split('_')[0])
                res_g = st.session_state.stats_analyzer.calcular_limites_imr_global(col, sigma=st.session_state.sigma_utilizado)

                if 'error' not in res_g:
                    sensor_id = res_g['sensor']

                    col_vals, col_chart = st.columns([1.1, 2.8])

                    with col_vals:
                        _s_key = "sup_flash" if col == cols_ir[0] else ("sup_ir" if len(cols_ir) > 1 and col == cols_ir[1] else None)
                        _i_key = "inf_flash" if col == cols_ir[0] else ("inf_ir" if len(cols_ir) > 1 and col == cols_ir[1] else None)
                        _sv = None
                        _iv = None
                        if _s_key:
                            _dl = st.session_state.datos_limites_guardados
                            try:
                                _sv = float(_dl[_s_key]) if _dl[_s_key] else None
                                _iv = float(_dl[_i_key]) if _dl[_i_key] else None
                            except ValueError:
                                pass

                        _sv_str = f"{_sv} {res_g['unidad']}" if _sv is not None else "—"
                        _iv_str = f"{_iv} {res_g['unidad']}" if _iv is not None else "—"
                        tbl = f"""
                        <table style="width:100%;border-collapse:collapse;font-size:7.5pt">
                        <tr><th colspan="2" style="padding:1px 4px;text-align:center;background:#eee">{tipo_prueba} ({sensor_id})</th></tr>
                        <tr><td style="padding:1px 4px;border:1px solid #ccc">UCL</td><td style="padding:1px 4px;border:1px solid #ccc;font-weight:bold">{res_g['ucl_i']} {res_g['unidad']}</td></tr>
                        <tr><td style="padding:1px 4px;border:1px solid #ccc">LCL</td><td style="padding:1px 4px;border:1px solid #ccc;font-weight:bold">{res_g['lcl_i']} {res_g['unidad']}</td></tr>
                        <tr><td style="padding:1px 4px;border:1px solid #ccc;color:purple">UCL Manual</td><td style="padding:1px 4px;border:1px solid #ccc;color:purple">{_sv_str}</td></tr>
                        <tr><td style="padding:1px 4px;border:1px solid #ccc;color:purple">LCL Manual</td><td style="padding:1px 4px;border:1px solid #ccc;color:purple">{_iv_str}</td></tr>
                        </table>
                        """
                        st.markdown(tbl, unsafe_allow_html=True)

                    with col_chart:
                        fig, ax1 = plt.subplots(figsize=(4.8, 1.7))
                        fig.suptitle(f"{tipo_prueba} ({sensor_id})", fontsize=7.5, fontweight='bold', y=0.97)
                        ax1.plot(res_g['datos_i'], color='black', linewidth=0.5)
                        ax1.axhline(res_g['media_i'], color='blue', linestyle='-', alpha=0.35, linewidth=0.7)
                        ax1.axhline(res_g['ucl_i'], color='red', linestyle='--', linewidth=0.7)
                        ax1.axhline(res_g['lcl_i'], color='red', linestyle='--', linewidth=0.7)
                        ax1.text(0, res_g['ucl_i'], f"UCL:{res_g['ucl_i']}", color='red', fontsize=5.5, va='bottom', ha='left', fontweight='bold')
                        ax1.text(0, res_g['lcl_i'], f"LCL:{res_g['lcl_i']}", color='red', fontsize=5.5, va='top', ha='left', fontweight='bold')

                        _s_key = "sup_flash" if col == cols_ir[0] else ("sup_ir" if len(cols_ir) > 1 and col == cols_ir[1] else None)
                        _i_key = "inf_flash" if col == cols_ir[0] else ("inf_ir" if len(cols_ir) > 1 and col == cols_ir[1] else None)
                        if _s_key:
                            _dl = st.session_state.datos_limites_guardados
                            try:
                                _sv_c = float(_dl[_s_key]) if _dl[_s_key] else None
                                _iv_c = float(_dl[_i_key]) if _dl[_i_key] else None
                                if _sv_c is not None:
                                    ax1.axhline(_sv_c, color='purple', linestyle='-.', linewidth=0.7)
                                    ax1.text(0, _sv_c, f"UCL Man:{_sv_c}", color='purple', fontsize=5.5, va='bottom', ha='left', fontweight='bold')
                                if _iv_c is not None:
                                    ax1.axhline(_iv_c, color='purple', linestyle='-.', linewidth=0.7)
                                    ax1.text(0, _iv_c, f"LCL Man:{_iv_c}", color='purple', fontsize=5.5, va='top', ha='left', fontweight='bold')
                            except ValueError:
                                pass

                        idx_ooc = res_g.get('outliers_i', [])
                        if idx_ooc:
                            ax1.scatter(idx_ooc, res_g['datos_i'].iloc[idx_ooc], color='red', s=8, zorder=5)
                        ax1.tick_params(labelsize=5.5)
                        ax1.set_ylabel(res_g['unidad'], fontsize=6.5)
                        ax1.grid(True, alpha=0.12)
                        plt.subplots_adjust(right=0.88)
                        st.pyplot(fig, use_container_width=True)
                else:
                    st.error(f"Error en {col}: {res_g['error']}")

        # --- RESUMEN DE RESULTADOS ---
        st.markdown(f"<h4 style='margin:3px 0 1px 0;padding:0;font-size:10pt'>🔬 Resumen de Resultados</h4>", unsafe_allow_html=True)

        mostrar_boton_imprimir = False

        if st.session_state.stats_analyzer is not None:
            cols_ir = st.session_state.stats_analyzer.cols_ir
            if len(cols_ir) >= 2:
                mapeo_nombres = {cols_ir[0]: "FLASH", cols_ir[1]: "IR"}
                resultados_analisis = []

                for col in cols_ir[:2]:
                    tipo_prueba = mapeo_nombres[col]
                    sensor_original = col.split('_')[0]

                    sensor_key_levene = f"tracks_{sensor_original.lower()}"
                    res_levene = st.session_state.resultados_levene.get(sensor_key_levene, {})
                    status_var = " ✅ PASS" if res_levene.get('varianzas_iguales') else " ❌ FAIL"

                    res_anova = st.session_state.stats_analyzer.anova_tracks(col)
                    p_val_anova = res_anova.get('p_value')
                    status_media = " ✅ PASS" if (p_val_anova is not None and p_val_anova > 0.05) else " ❌ FAIL"

                    resultados_analisis.append({
                        "Grupo": tipo_prueba,
                        "Varianzas (Levene)": status_var,
                        "Medias (ANOVA)": status_media
                    })

                html_res = "<table style='width:100%;border-collapse:collapse;font-size:7.5pt;border:1px solid #ccc'>"
                html_res += "<tr style='background:#eee'><th style='padding:1px 6px;text-align:left'>Grupo</th><th style='padding:1px 6px;text-align:left'>Varianzas (Levene)</th><th style='padding:1px 6px;text-align:left'>Medias (ANOVA)</th></tr>"
                for r in resultados_analisis:
                    html_res += f"<tr><td style='padding:1px 6px'>{r['Grupo']}</td><td style='padding:1px 6px'>{r['Varianzas (Levene)']}</td><td style='padding:1px 6px'>{r['Medias (ANOVA)']}</td></tr>"
                html_res += "</table>"
                st.markdown(html_res, unsafe_allow_html=True)

                # Evaluar condición PASS para el botón de imprimir
                # FLASH: las 2 pruebas deben estar PASS (Levene Y ANOVA)
                # IR: alcanza con que 1 de las 2 esté PASS (Levene O ANOVA)
                if len(resultados_analisis) >= 2:
                    flash = resultados_analisis[0]
                    ir = resultados_analisis[1]

                    flash_ok = (flash["Varianzas (Levene)"] == " ✅ PASS" and
                                flash["Medias (ANOVA)"] == " ✅ PASS")
                    ir_ok = (ir["Varianzas (Levene)"] == " ✅ PASS" or
                             ir["Medias (ANOVA)"] == " ✅ PASS")

                    mostrar_boton_imprimir = flash_ok and ir_ok

            else:
                st.warning("⚠️ Revisar el archivo, posiblemente no se detectaron suficientes columnas de prueba.")
        else:
            st.info("ℹ️ Los resultados del análisis estadístico aparecerán aquí una vez que se procese el SHOP ORDER.")

        # --- SECCIÓN DEL BOTÓN DE IMPRESIÓN ---
        if mostrar_boton_imprimir:
                 
            # Inicializamos el disparador en el estado de la sesión si no existe
            if "disparar_impresion" not in st.session_state:
                st.session_state.disparar_impresion = False

            # Al hacer clic, activamos el disparador
            if st.button("🖨️ Imprimir Reporte", key="btn_imprimir_reporte_final", use_container_width=True):
                st.session_state.disparar_impresion = True
                st.rerun()

            # Si el disparador está activo, inyectamos el HTML de forma dinámica
            if st.session_state.disparar_impresion:
                st.session_state.disparar_impresion = False # Lo reiniciamos para el próximo clic
                
                import time
                timestamp_unico = int(time.time())
                
                # 1. Creamos el contenedor vacío
                contenedor_print = st.empty()
                
                # 2. Forzamos el renderizado del componente HTML nativo dentro del contenedor
                with contenedor_print:
                    st.components.v1.html(f"""
                        <script>
                            // ID único para forzar re-ejecución en el navegador: {timestamp_unico}
                            window.parent.print();
                        </script>
                    """, height=0, width=0)
                
st.markdown("---")
st.caption("Sistema de Automatización de Límites Allegro - Versión 1.0 | IT-Development AVXELS © 2026")

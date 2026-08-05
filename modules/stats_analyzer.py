"""
Módulo de análisis estadístico
Implementa pruebas estadísticas para análisis de datos de mediciones
"""

import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from typing import Tuple, Dict, List
import matplotlib.pyplot as plt

class StatsAnalyzer:
    """Clase para realizar análisis estadísticos dinámicos en datos de mediciones"""
    
    def __init__(self, df: pd.DataFrame):
        """
        Inicializa el analizador estadístico
        
        Args:
            df: DataFrame con datos procesados (detecta columnas _uA y _nA automáticamente)
        """
        self.df = df
        self.resultados = {}
        # Identificar dinámicamente qué columnas de datos tenemos
        self.cols_ir = [c for c in df.columns if c.endswith('_uA') or c.endswith('_nA')]
        
    def test_levene_global(self) -> Dict:
        """
        Realiza el test de Levene entre los sensores detectados (ej: IR1 vs IR2)
        
        Returns:
            Dict: Resultado del test comparando el primer sensor contra el segundo.
        """
        try:
            if len(self.cols_ir) < 2:
                return {'conclusion': 'Se necesitan al menos 2 sensores para comparar varianzas'}

            # Obtener nombres de las columnas
            col1, col2 = self.cols_ir[0], self.cols_ir[1]
            
            # Obtener datos limpios
            datos1 = self.df[col1].dropna().values
            datos2 = self.df[col2].dropna().values
            
            if len(datos1) < 2 or len(datos2) < 2:
                return {'conclusion': 'Datos insuficientes para realizar el test'}
            
            # Realizar test de Levene
            estadistico, p_value = stats.levene(datos1, datos2)
            
            # Calcular varianzas y desviaciones
            var1, var2 = np.var(datos1, ddof=1), np.var(datos2, ddof=1)
            std1, std2 = np.std(datos1, ddof=1), np.std(datos2, ddof=1)
            
            # Interpretación
            varianzas_iguales = p_value > 0.05
            conclusion = (f"✅ Varianzas IGUALES (p={p_value:.4f} > 0.05)" if varianzas_iguales 
                         else f"❌ Varianzas DIFERENTES (p={p_value:.4f} <= 0.05)")
            
            # Crear resultado con llaves dinámicas basadas en los nombres reales
            resultado = {
                'estadistico': round(estadistico, 4),
                'p_value': round(p_value, 4),
                'conclusion': conclusion,
                'varianzas_iguales': varianzas_iguales,
                f'{col1}_varianza': round(var1, 4),
                f'{col2}_varianza': round(var2, 4),
                f'{col1}_desv_std': round(std1, 4),
                f'{col2}_desv_std': round(std2, 4),
                'sensores_comparados': [col1, col2]
            }
            
            self.resultados['levene_global'] = resultado
            return resultado
            
        except Exception as e:
            return {'conclusion': f'Error al realizar test: {str(e)}'}

        """
        Realiza el test de Levene para IR3 comparando varianzas entre todos los tracks (1-8)
        
        El test de Levene verifica si todos los tracks tienen varianzas iguales en IR3.
        
        Returns:
            Dict: {
                'estadistico': valor del estadístico,
                'p_value': valor p,
                'conclusion': Interpretación,
                'varianzas_iguales': bool,
                'varianzas_por_track': dict con varianza de cada track
            }
        """
        try:
            # Obtener datos de IR3 por track
            tracks_ir3 = []
            varianzas_track = {}
            
            for track in range(1, 9):
                datos_track = self.df[self.df['Track'] == track]['IR3_uA'].dropna().values
                if len(datos_track) >= 2:
                    tracks_ir3.append(datos_track)
                    varianzas_track[f'Track_{track}'] = round(np.var(datos_track, ddof=1), 4)
            
            # Verificar que hay datos en al menos 2 tracks
            if len(tracks_ir3) < 2:
                return {
                    'estadistico': None,
                    'p_value': None,
                    'conclusion': 'Datos insuficientes en los tracks',
                    'varianzas_iguales': None,
                    'varianzas_por_track': varianzas_track
                }
            
            # Realizar test de Levene
            estadistico, p_value = stats.levene(*tracks_ir3)
            
            # Interpretación
            varianzas_iguales = p_value > 0.05
            if varianzas_iguales:
                conclusion = f"✅ Varianzas IGUALES entre tracks (p={p_value:.4f} > 0.05)"
            else:
                conclusion = f"❌ Varianzas DIFERENTES entre tracks (p={p_value:.4f} <= 0.05)"
            
            resultado = {
                'estadistico': round(estadistico, 4),
                'p_value': round(p_value, 4),
                'conclusion': conclusion,
                'varianzas_iguales': varianzas_iguales,
                'varianzas_por_track': varianzas_track
            }
            
            self.resultados['levene_tracks_ir3'] = resultado
            return resultado
            
        except Exception as e:
            return {
                'estadistico': None,
                'p_value': None,
                'conclusion': f'Error al realizar test: {str(e)}',
                'varianzas_iguales': None,
                'varianzas_por_track': {}
            }
    def test_levene_tracks(self, nombre_columna: str) -> Dict:
        """
        Realiza el test de Levene para una columna específica comparando varianzas entre tracks.
        """
        try:
            # 1. Validar que la columna existe
            if nombre_columna not in self.df.columns:
                return {'estadistico': None, 'p_value': None, 'conclusion': f'Error: {nombre_columna} no existe'}

            datos_por_track = []
            varianzas_track = {}
            
            # 2. Agrupar datos por track dinámicamente
            for track in sorted(self.df['Track'].unique()):
                datos_track = self.df[self.df['Track'] == track][nombre_columna].dropna().values
                if len(datos_track) >= 2:
                    datos_por_track.append(datos_track)
                    varianzas_track[f'Track {track}'] = round(np.var(datos_track, ddof=1), 4)
            
            # 3. Ejecutar Test si hay suficientes datos
            if len(datos_por_track) < 2:
                return {'estadistico': None, 'p_value': None, 'conclusion': 'Datos insuficientes', 'varianzas_por_track': varianzas_track}
            
            estadistico, p_value = stats.levene(*datos_por_track)
            varianzas_iguales = p_value > 0.05
            
            conclusion = f"✅ Varianzas IGUALES (p={p_value:.4f})" if varianzas_iguales else f"❌ Varianzas DIFERENTES (p={p_value:.4f})"
            
            return {
                'estadistico': round(estadistico, 4),
                'p_value': round(p_value, 4),
                'conclusion': conclusion,
                'varianzas_iguales': varianzas_iguales,
                'varianzas_por_track': varianzas_track
            }
        except Exception as e:
            return {'estadistico': None, 'p_value': None, 'conclusion': f'Error: {str(e)}', 'varianzas_por_track': {}}

    
    def _detectar_outliers_mad(self, varianzas_dict: Dict[str, float], umbral: float = 2.5) -> Dict:
        """
        Detecta varianzas outliers usando MAD (Median Absolute Deviation)
        
        Método robusto menos sensible a outliers extremos que Z-score
        - MAD = mediana(|x - mediana(x)|)
        - Modified Z-score = 0.6745 * (x - mediana) / MAD
        - |Modified Z-score| > umbral indica outlier
        
        Args:
            varianzas_dict: Diccionario con varianzas por track
            umbral: Umbral para considerar como outlier (default: 2.5)
            
        Returns:
            Dict: Similar al método Z-score
        """
        varianzas_valores = list(varianzas_dict.values())
        
        if len(varianzas_valores) < 2:
            return {
                'outliers': [],
                'detalles_outliers': [],
                'estadisticas': {},
                'metodo': f'MAD (umbral={umbral}) - datos insuficientes'
            }
        
        # Calcular mediana
        mediana = np.median(varianzas_valores)
        
        # Calcular MAD
        desv_abs = np.abs(varianzas_valores - mediana)
        mad = np.median(desv_abs)
        
        # Evitar división por cero
        if mad == 0:
            return {
                'outliers': [],
                'detalles_outliers': [],
                'estadisticas': {'mediana': round(mediana, 4), 'mad': 0},
                'metodo': f'MAD (umbral={umbral}) - MAD = 0'
            }
        
        # Calcular Modified Z-scores
        outliers = []
        detalles_outliers = []
        
        for track_name, varianza in varianzas_dict.items():
            mod_z_score = 0.6745 * (varianza - mediana) / mad
            
            if abs(mod_z_score) > umbral:
                outliers.append(track_name)
                detalles_outliers.append({
                    'track': track_name,
                    'varianza': round(varianza, 4),
                    'mod_z_score': round(mod_z_score, 4),
                    'tipo': 'Muy Alta' if mod_z_score > 0 else 'Muy Baja'
                })
        
        return {
            'outliers': outliers,
            'detalles_outliers': detalles_outliers,
            'estadisticas': {
                'mediana': round(mediana, 4),
                'mad': round(mad, 4),
                'min': round(min(varianzas_valores), 4),
                'max': round(max(varianzas_valores), 4)
            },
            'metodo': f'MAD (Median Absolute Deviation) - umbral={umbral}',
            'umbral': umbral
        }
    
    def analizar_varianzas_diferentes(self, nombre_columna: str) -> Dict:
        """
        Analiza si hay tracks con varianzas atípicas (Outliers) usando MAD.
        """
        try:
            varianzas = {}
            # Obtener varianza de cada track
            for track in sorted(self.df['Track'].unique()):
                datos = self.df[self.df['Track'] == track][nombre_columna].dropna().values
                if len(datos) >= 2:
                    varianzas[track] = np.var(datos, ddof=1)

            if not varianzas:
                return {'error': 'No hay datos suficientes'}

            # Cálculo de MAD (Median Absolute Deviation) sobre las varianzas
            lista_varianzas = list(varianzas.values())
            mediana_v = np.median(lista_varianzas)
            mad = np.median([abs(v - mediana_v) for v in lista_varianzas])
            
            # Evitar división por cero
            umbral = 3.0
            outliers = []
            if mad > 0:
                for track, var in varianzas.items():
                    # Puntuación Z robusta
                    score = 0.6745 * (var - mediana_v) / mad
                    if abs(score) > umbral:
                        outliers.append({
                        'id': f"Track {track}",
                        'valor': round(var, 6)
                        })

            # Estructura que espera tu interfaz
            return {
                'resumen': {
                    'tracks_problematicos': [{'track': o['id'], 'varianza': o['valor'],'consenso': True, 'metodos_detecta': ['MAD']} for o in outliers],
                    'recomendacion': "Revisar tracks marcados para obtener estabilidad." if outliers else "Varianzas estables."
                },
                'analisis_completo': {
                    'mad': {
                        'estadisticas': {'mediana': round(mediana_v, 6), 'mad': round(mad, 6)},
                        'outliers': outliers
                    }
                }
            }
        except Exception as e:
            return {'error': str(e)}


    def _generar_recomendacion(self, tracks_problematicos: List[Dict], 
                               resultado_iqr: Dict = None, resultado_zscore: Dict = None, 
                               resultado_mad: Dict = None, medida: str = '') -> str:
        """
        Genera una recomendación basada en el análisis de varianzas
        
        Args:
            tracks_problematicos: Lista de tracks problemáticos encontrados
            resultado_iqr: Resultado del análisis IQR
            resultado_zscore: Resultado del análisis Z-score
            resultado_mad: Resultado del análisis MAD
            medida: 'IR3' o 'IR4'
            
        Returns:
            str: Recomendación con instrucciones de acción
        """
        if not tracks_problematicos:
            return f"✅ No se detectaron varianzas outliers en {medida}."
        
        tracks_consenso = [t for t in tracks_problematicos if t['consenso']]
        
        if len(tracks_consenso) > 0:
            tracks_str = ', '.join([t['track'] for t in tracks_consenso])
            return (
                f"⚠️ VARIANZAS PROBLEMÁTICAS en {medida}:\n"
                f"Tracks identificados: {tracks_str}\n"
                f"Estos tracks muestran variabilidad significativamente diferente al resto.\n"
                f"🔍 RECOMENDACIÓN:\n"
                f"1. Revisar los datos de medición de estos tracks\n"
                f"2. Verificar si hay problemas en la configuración o calibración\n"
                f"3. Considerar eliminar o recolectar más datos de estos tracks\n"
                f"4. Investigar si hay anomalías en los equipos/procesos asociados"
            )
        else:
            return (
                f"⚠️ Se detectaron varianzas diferentes en {medida}."
            )
    
    #ANOVA DINAMICO PARA CUALQUIER COLUMNA
    def anova_tracks(self, nombre_columna: str) -> Dict:
        """
        Realiza el ANOVA para una columna específica entre tracks.
        """
        try:
            datos_por_track = []
            medias_por_track = {}
            
            for track in sorted(self.df['Track'].unique()):
                datos_track = self.df[self.df['Track'] == track][nombre_columna].dropna().values
                if len(datos_track) >= 2:
                    datos_por_track.append(datos_track)
                    medias_por_track[f'Track {track}'] = round(np.mean(datos_track), 4)
            
            if len(datos_por_track) < 2:
                return {'estadistico_f': None, 'conclusion': 'Datos insuficientes para ANOVA'}
            
            f_stat, p_val = stats.f_oneway(*datos_por_track)
            
            # Grados de libertad
            df_between = len(datos_por_track) - 1
            df_within = sum(len(d) for d in datos_por_track) - len(datos_por_track)
            
            conclusion = f"✅ No hay diferencias significativas (p={p_val:.4f})" if p_val > 0.05 \
                         else f"❌ Hay diferencias significativas entre medias (p={p_val:.4f})"
            
            return {
                'estadistico_f': round(f_stat, 4),
                'p_value': round(p_val, 4),
                'grados_libertad': (df_between, df_within),
                'medias_por_track': medias_por_track,
                'conclusion': conclusion
            }
        except Exception as e:
            return {'estadistico_f': None, 'conclusion': f'Error: {str(e)}'}
        
        
######################################################################################################################################
#    def tukey_hsd(self, nombre_columna: str) -> Dict:
#        """
#        Realiza la prueba de Tukey HSD de forma compatible con nuevas versiones de statsmodels.
#        """
#        try:
#            # Filtrar datos válidos
#            df_clean = self.df[['Track', nombre_columna]].dropna()
            
#            if df_clean['Track'].nunique() < 2:
#                return {'comparaciones': [], 'resumen': 'Datos insuficientes para comparaciones pareadas.'}

            # Ejecutar Tukey
#            tukey = pairwise_tukeyhsd(endog=df_clean[nombre_columna], groups=df_clean['Track'], alpha=0.05)  #para pruebas cambia valor a 0001
            
            # Extraer resultados de forma segura convirtiéndolos a un DataFrame de Pandas
            # statsmodels permite convertir el resumen a un dataframe directamente
#            df_resumen = pd.DataFrame(data=tukey.summary().data[1:], columns=tukey.summary().data[0])
            
#            comparaciones = []
#            for _, row in df_resumen.iterrows():
#                comparaciones.append({
#                    'group1': f"Track {row['group1']}",
#                   'group2': f"Track {row['group2']}",
#                    'meandiff': round(float(row['meandiff']), 4),
#                    'p_adj': round(float(row['p-adj']), 4),
#                    'reject': bool(row['reject']),
#                    'significativo2': "SÍ" if row['reject'] else "NO"
#                })

#            tiene_diferencias = any(c['reject'] for c in comparaciones)
#            resumen = "Se detectaron diferencias significativas entre algunos tracks." if tiene_diferencias \
#                      else "No hay diferencias significativas entre ningún par de tracks."

#            return {
#                'comparaciones': comparaciones,
#                'resumen': resumen
#            }
#        except Exception as e:
            # En caso de error, devolvemos una lista vacía y el mensaje
#            return {'comparaciones': [], 'resumen': f'Error en Tukey: {str(e)}'}

######################################################################################################################################

#Funcion Tukey con alpha personalizable para pruebas de significancia más estrictas (ej: 0.001)
    def tukey_hsd(self, nombre_columna: str, alpha: float = 0.05) -> Dict:
        """
        Realiza la prueba de Tukey HSD con un nivel de significancia (alpha) personalizable.
        """
        try:
            # Filtrar datos válidos
            df_clean = self.df[['Track', nombre_columna]].dropna()
            
            if df_clean['Track'].nunique() < 2:
                return {'comparaciones': [], 'resumen': 'Datos insuficientes para comparaciones pareadas.'}

            # Ejecutar Tukey usando el alpha recibido
            tukey = pairwise_tukeyhsd(endog=df_clean[nombre_columna], groups=df_clean['Track'], alpha=alpha)
            
            # ... (el resto del código de la función se mantiene igual)
            df_resumen = pd.DataFrame(data=tukey.summary().data[1:], columns=tukey.summary().data[0])
            
            comparaciones = []
            for _, row in df_resumen.iterrows():
                comparaciones.append({
                    'group1': f"Track {row['group1']}",
                    'group2': f"Track {row['group2']}",
                    'meandiff': round(float(row['meandiff']), 4),
                    'p_adj': round(float(row['p-adj']), 4),
                    'reject': bool(row['reject']),
                    'significativo2': "SÍ" if row['reject'] else "NO"
                })

            tiene_diferencias = any(c['reject'] for c in comparaciones)
            resumen = "Se detectaron diferencias significativas entre algunos tracks." if tiene_diferencias \
                      else "No hay diferencias significativas entre ningún par de tracks."

            return {'comparaciones': comparaciones, 'resumen': resumen}
        except Exception as e:
            return {'comparaciones': [], 'resumen': f'Error en Tukey: {str(e)}'}







    def calcular_limites_imr(self, columna: str) -> Dict:
        """
        Calcula los límites de control para una gráfica I-MR dinámicamente.
        Compatible con cualquier sensor IR detectado.
        """
        try:
            # 1. Validar existencia de la columna
            if columna not in self.df.columns:
                return {'error': f'La columna {columna} no existe en el dataset'}

            # 2. Extraer datos limpios
            datos = self.df[columna].dropna().reset_index(drop=True)
            
            if len(datos) < 2:
                return {'error': f'Datos insuficientes en {columna} para calcular I-MR'}
            
            # --- Cálculos para Individuos (I) ---
            media_i = datos.mean()
            
            # --- Cálculos para Rango Móvil (MR) ---
            mr = datos.diff().abs().dropna() 
            media_mr = mr.mean()
            
            # Constantes SPC (n=2)
            D3, D4, d2 = 0.0, 3.267, 1.128
            
            # Límites para MR (Rango Móvil)
            ucl_mr = D4 * media_mr
            lcl_mr = D3 * media_mr # Normalmente 0
            
            # Límites para I (Individuos)
            # 3 / d2 ≈ 2.66
            lcl_i = media_i - (3 / d2) * media_mr
            ucl_i = media_i + (3 / d2) * media_mr
            
            # 3. Detectar puntos fuera de control (Violaciones de límites)
            outliers_i = datos[(datos > ucl_i) | (datos < lcl_i)].index.tolist()
            outliers_mr = mr[mr > ucl_mr].index.tolist()
            
            resultado = {
                'sensor': columna.split('_')[0], # Extrae 'IR1', 'IR3', etc.
                'datos_i': datos,
                'datos_mr': mr,
                'media_i': round(media_i, 4),
                'lcl_i': round(lcl_i, 4),
                'ucl_i': round(ucl_i, 4),
                'media_mr': round(media_mr, 4),
                'lcl_mr': round(lcl_mr, 4),
                'ucl_mr': round(ucl_mr, 4),
                'outliers_i': outliers_i,
                'outliers_mr': outliers_mr,
                'n_observaciones': len(datos)
            }
            
            # Guardar con un nombre estandarizado (ej: limites_imr_ir3)
            id_sensor = columna.split('_')[0].lower()
            self.resultados[f'limites_imr_{id_sensor}'] = resultado
            
            return resultado
            
        except Exception as e:
            return {'error': f'Error al calcular límites I-MR en {columna}: {str(e)}'}

    def graficar_imr(self, columna: str, titulo_proceso: str = ""):
        """
        Genera gráficas I-MR dinámicas para cualquier sensor detectado.
        """
        # 1. Calcular los límites (usando la función dinámica previa)
        res = self.calcular_limites_imr(columna)
        
        if 'error' in res:
            return None # Retornamos None para que Streamlit sepa que no hay gráfico
            
        # Determinar el nombre del sensor y la unidad dinámicamente
        sensor_name = columna.split('_')[0] # 'IR1', 'IR2', etc.
        unidad = "μA" if "_uA" in columna else "nA"
        
        # 2. Configurar la figura
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
        fig.suptitle(f'Gráficas de Control I-MR: {sensor_name} {titulo_proceso}', 
                     fontsize=16, fontweight='bold')
        
        # --- GRÁFICA SUPERIOR: Individuos (I) ---
        ax1.plot(res['datos_i'], marker='o', linestyle='-', color='steelblue', 
                 markersize=4, label=f'Medición ({unidad})')
        ax1.axhline(res['media_i'], color='green', linestyle='--', linewidth=2, 
                    label=f"Media ({res['media_i']})")
        ax1.axhline(res['ucl_i'], color='red', linestyle='--', linewidth=2, 
                    label=f"UCL ({res['ucl_i']})")
        ax1.axhline(res['lcl_i'], color='red', linestyle='--', linewidth=2, 
                    label=f"LCL ({res['lcl_i']})")
        
        # Resaltar puntos fuera de control usando los índices calculados
        out_of_control_i = res['datos_i'].iloc[res['outliers_i']]
        if not out_of_control_i.empty:
            ax1.scatter(out_of_control_i.index, out_of_control_i, 
                        color='red', s=50, zorder=5, label='Fuera de Control')
        
        ax1.set_ylabel(f'Valor ({unidad})')
        ax1.legend(loc='upper right', fontsize='small')
        ax1.grid(True, alpha=0.3)
        ax1.set_title(f'Gráfica I (Individuos) - {sensor_name}')
        
        # --- GRÁFICA INFERIOR: Rango Móvil (MR) ---
        ax2.plot(res['datos_mr'].index, res['datos_mr'], marker='s', linestyle='-', 
                 color='orange', markersize=4, label='Rango Móvil')
        ax2.axhline(res['media_mr'], color='green', linestyle='--', linewidth=2, 
                    label=f"Media MR ({res['media_mr']})")
        ax2.axhline(res['ucl_mr'], color='red', linestyle='--', linewidth=2, 
                    label=f"UCL MR ({res['ucl_mr']})")
        ax2.axhline(res['lcl_mr'], color='red', linestyle='--', linewidth=2, 
                    label=f"LCL MR ({res['lcl_mr']})")
        
        # Resaltar puntos fuera de control en MR
        out_of_control_mr = res['datos_mr'].iloc[res['outliers_mr']]
        if not out_of_control_mr.empty:
            ax2.scatter(out_of_control_mr.index, out_of_control_mr, 
                        color='red', s=50, zorder=5, label='Fuera de Control')
        
        ax2.set_xlabel('Muestra Secuencial')
        ax2.set_ylabel(f'Δ Rango ({unidad})')
        ax2.legend(loc='upper right', fontsize='small')
        ax2.grid(True, alpha=0.3)
        ax2.set_title(f'Gráfica MR (Rango Móvil) - {sensor_name}')
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Retornamos la figura para Streamlit y el conteo de alertas
        alertas = {
            'sensor': sensor_name,
            'ooc_i': len(out_of_control_i),
            'ooc_mr': len(out_of_control_mr)
        }
        
        return fig, alertas

    def calcular_limites_imr_global(self, columna: str, sigma: float = 3.0) -> Dict:
        """
        Calcula límites I-MR globales fusionando datos. 
        Detecta dinámicamente el sensor y ajusta la escala según el sigma solicitado.
        """
        try:
            # 1. Validar columna y extraer datos
            if columna not in self.df.columns:
                return {'error': f'Columna {columna} no encontrada'}

            datos = self.df[columna].dropna().reset_index(drop=True)
            
            if len(datos) < 2:
                return {'error': 'Datos insuficientes para análisis global'}
            
            # 2. Cálculos Estadísticos Base
            media_i = np.mean(datos)
            mr = datos.diff().abs().dropna()
            media_mr = np.mean(mr)
            
            # Constantes SPC (n=2)
            d2 = 1.128
            D4_base = 3.267 # Corresponde a 3 sigmas
            
            # 3. Límites Dinámicos (Individuos)
            # Escalamos el ancho de banda según el valor de 'sigma'
            ucl_i = media_i + (sigma / d2) * media_mr
            lcl_i = media_i - (sigma / d2) * media_mr
            
            # 4. Límites Dinámicos (Rango Móvil)
            # Escalamos el D4 proporcionalmente al sigma solicitado
            ucl_mr = D4_base * (sigma / 3.0) * media_mr
            lcl_mr = 0
            
            # 5. Detección de puntos fuera de control (Outliers)
            ooc_i_indices = datos[(datos > ucl_i) | (datos < lcl_i)].index.tolist()
            ooc_mr_indices = mr[mr > ucl_mr].index.tolist()
            
            # Identificar Sensor y Unidad para la UI
            sensor_id = columna.split('_')
            unidad = "μA" if "_uA" in columna else "nA"
            
            return {
                'sensor': sensor_id,
                'unidad': unidad,
                'datos_i': datos,
                'datos_mr': mr,
                'media_i': round(media_i, 4),
                'ucl_i': round(ucl_i, 4),
                'lcl_i': round(lcl_i, 4),
                'media_mr': round(media_mr, 4),
                'ucl_mr': round(ucl_mr, 4),
                'lcl_mr': round(lcl_mr, 4),
                'outliers_i': ooc_i_indices,
                'outliers_mr': ooc_mr_indices,
                'std_global': round(np.std(datos, ddof=1), 4),
                'total_datos': len(datos),
                'sigma_usado': sigma
            }
            
        except Exception as e:
            return {'error': f'Error en cálculo global: {str(e)}'}


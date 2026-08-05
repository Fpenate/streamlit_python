"""
Módulo de procesamiento de archivos CSV
Transforma, limpia y valida datos de mediciones
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, List
import io

class CSVProcessor:
    """Clase para procesar archivos CSV de mediciones"""
    
    def __init__(self, min_mediciones_por_track: int = 100):
        """
        Inicializa el procesador
        
        Args:
            min_mediciones_por_track: Cantidad mínima de mediciones válidas por track
        """
        self.min_mediciones = min_mediciones_por_track
        self.df_original = None
        self.df_procesado = None
        self.errores = []
        self.advertencias = []
    
    def leer_csv(self, archivo) -> bool:
        """
        Lee el archivo CSV eliminando filas basura al principio
        
        Args:
            archivo: Archivo CSV cargado desde Streamlit
            
        Returns:
            bool: True si se leyó correctamente, False en caso contrario
        """
        try:
            # 1. Volver al inicio del archivo (importante en Streamlit si se leyó antes)
            archivo.seek(0)
            
            # 2. Leer líneas para encontrar dónde están los encabezados reales
            lineas = archivo.readlines()
            linea_header = 0
            columnas_requeridas = ['Index', 'Track', 'CreatorID', 'DataID', 'Value']
            
            encontrado = False
            for i, linea in enumerate(lineas):
                # Decodificar si es necesario y limpiar espacios
                contenido = linea.decode('utf-8').strip() if isinstance(linea, bytes) else linea.strip()
                # Comprobar si la línea contiene todos los encabezados requeridos
                if all(col in contenido for col in columnas_requeridas):
                    linea_header = i
                    encontrado = True
                    break
            
            if not encontrado:
                self.errores.append("No se encontró la fila de encabezados requerida.")
                return False

            # 3. Volver a leer con pandas saltando las líneas basura
            archivo.seek(0)
            self.df_original = pd.read_csv(archivo, skiprows=linea_header)
            
            # 4. Validar columnas finales
            columnas_faltantes = [col for col in columnas_requeridas if col not in self.df_original.columns]
            if columnas_faltantes:
                self.errores.append(f"Columnas faltantes tras limpieza: {', '.join(columnas_faltantes)}")
                return False
                
            return True
            
        except Exception as e:
            self.errores.append(f"Error al leer el archivo CSV: {str(e)}")
            return False
    
    def filtrar_datos(self) -> bool:
        """
        Filtra solo los datos necesarios:
        - CreatorID: IR3, IR4
        - DataID: IRMeasure
        
        Returns:
            bool: True si hay datos después del filtrado
        """
        try:
            # Filtrar solo IR3 e IR4
            df_filtrado = self.df_original[
                (self.df_original['CreatorID'].str.startswith('IR', na=False)) &
                (self.df_original['DataID'] == 'IRMeasure')
            ].copy()
            
            if df_filtrado.empty:
                self.errores.append("No se encontraron datos de IR3 o IR4 con IRMeasure en el CSV")
                return False
            
            self.df_procesado = df_filtrado
            return True
            
        except Exception as e:
            self.errores.append(f"Error al filtrar datos: {str(e)}")
            return False
    
    def convertir_notacion_cientifica(self) -> bool:
        try:
            # Detectamos qué IRs existen (ej: IR1, IR2) y los ordenamos
            irs_presentes = sorted(self.df_procesado['CreatorID'].unique())
            if not irs_presentes: return False
            
            # El primero de la lista (menor número) será uA
            ir_menor = irs_presentes[0]

            def aplicar_escala(row):
                try:
                    valor = float(row['Value'])
                    # Si es el sensor menor (IR1 o IR3), escala micro (1e6)
                    # Si es cualquier otro (IR2 o IR4), escala nano (1e9)
                    factor = 1e6 if row['CreatorID'] == ir_menor else 1e9
                    return round(valor * factor, 2)
                except:
                    return np.nan
            
            self.df_procesado['Value_Converted'] = self.df_procesado.apply(aplicar_escala, axis=1)
            return True
        except Exception as e:
            self.errores.append(f"Error en conversión: {str(e)}")
            return False


    
    def pivotar_datos(self) -> bool:
        try:
            irs_ordenados = sorted(self.df_procesado['CreatorID'].unique())
            
            df_pivot = self.df_procesado.pivot_table(
                index=['Index', 'Track'],
                columns='CreatorID',
                values='Value_Converted',
                aggfunc='first'
            ).reset_index()
            
            df_pivot.columns.name = None
            
            # Renombrado dinámico: el primero uA, el segundo nA
            mapeo = {}
            for i, nombre_ir in enumerate(irs_ordenados):
                sufijo = "_uA" if i == 0 else "_nA"
                mapeo[nombre_ir] = f"{nombre_ir}{sufijo}"
            
            df_pivot.rename(columns=mapeo, inplace=True)
            self.df_procesado = df_pivot
            return True
        except Exception as e:
            self.errores.append(f"Error al pivotar: {str(e)}")
            return False

    
    def eliminar_valores_nulos(self) -> bool:
        try:
            registros_antes = len(self.df_procesado)
            
            # Identificar dinámicamente las columnas de datos
            cols_datos = [c for c in self.df_procesado.columns if '_uA' in c or '_nA' in c]
            
            # Eliminar si falta cualquiera de las dos mediciones
            self.df_procesado = self.df_procesado.dropna(subset=cols_datos)
            
            registros_eliminados = registros_antes - len(self.df_procesado)
            if registros_eliminados > 0:
                self.advertencias.append(f"Se eliminaron {registros_eliminados} filas incompletas")
            return True
        except Exception as e:
            self.errores.append(f"Error al limpiar nulos: {str(e)}")
            return False


    def ajustar_decimales(self, ndigits: int = 2) -> bool:
        """
        Asegura que las columnas de mediciones (uA y nA) estén en formato numérico
        y redondea los valores dinámicamente.

        Returns:
            bool: True si la operación fue exitosa
        """
        try:
            if self.df_procesado is None:
                return True

            # Identificar dinámicamente las columnas que contienen los datos
            # Esto encontrará IR1_uA, IR2_nA, IR3_uA, etc.
            cols_a_ajustar = [c for c in self.df_procesado.columns if c.endswith('_uA') or c.endswith('_nA')]

            for col in cols_a_ajustar:
                # Forzar tipo numérico (por si hay basura) y redondear
                self.df_procesado[col] = pd.to_numeric(
                    self.df_procesado[col], 
                    errors='coerce'
                ).round(ndigits)

            return True

        except Exception as e:
            self.errores.append(f"Error al ajustar decimales: {str(e)}")
            return False

    
    def validar_datos(self) -> Tuple[bool, Dict]:
        """
        Valida los datos procesados dinámicamente para cualquier sensor IR.
        """
        validaciones = {
            'tracks_validados': {},
            'errores_criticos': [],
            'advertencias': []
        }
        
        # 1. Identificar qué columnas de datos tenemos (ej. ['IR1_uA', 'IR2_nA'])
        cols_ir = [c for c in self.df_procesado.columns if c.endswith('_uA') or c.endswith('_nA')]
        
        for track in range(1, 9):
            track_data = self.df_procesado[self.df_procesado['Track'] == track]
            
            # Inicializar estructura de resultados para este track
            track_stats = {
                'total_mediciones': 0,
                'aprobado': False
            }
            
            # Inicializar dinámicamente contadores para cada IR encontrado
            for col in cols_ir:
                track_stats[f'mediciones_validas_{col}'] = 0
                track_stats[f'tiene_negativos_{col}'] = False
                track_stats[f'tiene_ceros_repetitivos_{col}'] = False

            validaciones['tracks_validados'][track] = track_stats
            
            if len(track_data) == 0:
                validaciones['errores_criticos'].append(f"❌ Track {track}: No se encontraron datos")
                continue
            
            mediciones_validas_total = 0
            tiene_error_negativo = False

            # 2. Validar cada columna IR dinámicamente
            for col in cols_ir:
                serie_datos = track_data[col].dropna()
                
                # Contar válidos (positivos no cero)
                validos_filtrados = serie_datos[(serie_datos > 0)]
                num_validos = len(validos_filtrados)
                track_stats[f'mediciones_validas_{col}'] = num_validos
                mediciones_validas_total += num_validos
                
                # Verificar negativos
                if (serie_datos < 0).any():
                    track_stats[f'tiene_negativos_{col}'] = True
                    tiene_error_negativo = True
                    validaciones['errores_criticos'].append(
                        f"❌ Track {track}: Se encontraron valores negativos en {col}"
                    )
                
                # Verificar ceros repetitivos (más del 10% < 0.01)
                ceros_cercanos = (serie_datos.abs() < 0.01).sum()
                if len(serie_datos) > 0 and ceros_cercanos > len(serie_datos) * 0.1:
                    track_stats[f'tiene_ceros_repetitivos_{col}'] = True
                    validaciones['advertencias'].append(
                        f"⚠️ Track {track}: Más del 10% de valores de {col} están cercanos a cero"
                    )

            # 3. Validaciones finales del Track
            track_stats['total_mediciones'] = mediciones_validas_total
            
            if mediciones_validas_total < self.min_mediciones:
                validaciones['errores_criticos'].append(
                    f"❌ Track {track}: Solo tiene {mediciones_validas_total} mediciones válidas "
                    f"(mínimo requerido: {self.min_mediciones})"
                )
            elif not tiene_error_negativo:
                track_stats['aprobado'] = True
        
        validacion_exitosa = len(validaciones['errores_criticos']) == 0
        return validacion_exitosa, validaciones

    
    def procesar_completo(self, archivo) -> Tuple[bool, pd.DataFrame, Dict]:
        """
        Ejecuta el flujo completo de procesamiento dinámico para sensores IR.
        
        Args:
            archivo: Archivo CSV cargado
            
        Returns:
            Tuple[bool, pd.DataFrame, Dict]: (éxito, dataframe_procesado, validaciones)
        """
        # Limpiar errores y advertencias previas
        self.errores = []
        self.advertencias = []
        
        # Paso 1: Leer CSV (detecta encabezados automáticamente)
        if not self.leer_csv(archivo):
            return False, None, {'errores': self.errores}
        
        # Paso 2: Filtrar datos (detecta cualquier CreatorID que empiece con 'IR')
        if not self.filtrar_datos():
            return False, None, {'errores': self.errores}
        
        # Paso 3: Convertir notación científica (asigna uA y nA según jerarquía de IR)
        if not self.convertir_notacion_cientifica():
            return False, None, {'errores': self.errores}
        
        # Paso 4: Pivotar datos (formato largo → ancho dinámico)
        if not self.pivotar_datos():
            return False, None, {'errores': self.errores}
        
        # Paso 5: Eliminar valores nulos (detecta dinámicamente columnas _uA y _nA)
        if not self.eliminar_valores_nulos():
            return False, None, {'errores': self.errores}

        # Paso 5b: Ajustar decimales (redondea cualquier columna de datos encontrada)
        if not self.ajustar_decimales(ndigits=2):
            return False, None, {'errores': self.errores}

        # Paso 6: Validar datos (evalúa tracks y calidad de señal)
        validacion_exitosa, validaciones = self.validar_datos()
        
        # Agregar advertencias acumuladas durante el proceso
        if self.advertencias:
            if 'advertencias' not in validaciones:
                validaciones['advertencias'] = []
            validaciones['advertencias'].extend(self.advertencias)
        
        return validacion_exitosa, self.df_procesado, validaciones

    
    def obtener_estadisticas_basicas(self) -> Dict:
        """
        Obtiene estadísticas básicas de los datos procesados dinámicamente.
        Funciona para cualquier par de sensores detectados (IR1, IR2, IR3, etc.)
        
        Returns:
            Dict: Diccionario con estadísticas
        """
        if self.df_procesado is None or self.df_procesado.empty:
            return {}
        
        estadisticas = {
            'total_registros': len(self.df_procesado),
            'tracks_unicos': int(self.df_procesado['Track'].nunique()),
            'rango_tracks': f"{self.df_procesado['Track'].min()} - {self.df_procesado['Track'].max()}",
        }
        
        # Identificar dinámicamente las columnas de sensores (uA y nA)
        cols_ir = [c for c in self.df_procesado.columns if c.endswith('_uA') or c.endswith('_nA')]
        
        for col in cols_ir:
            # Limpiar nombre para la llave del diccionario (ej: de 'IR3_uA' a 'ir3')
            nombre_llave = col.split('_')[0].lower()
            
            estadisticas[nombre_llave] = {
                'media': round(self.df_procesado[col].mean(), 2),
                'min': round(self.df_procesado[col].min(), 2),
                'max': round(self.df_procesado[col].max(), 2),
                'std': round(self.df_procesado[col].std(), 2)
            }
        
        return estadisticas

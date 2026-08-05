import json
import mysql.connector
from mysql.connector import Error

# Importar módulo de conexión a base de datos
from config.connect_database import load_config, create_db_connection

def load_config():
    """
    Cargar la configuración de la base de datos desde el archivo config_db.json
    """
    with open('config_db.json') as f:
        return json.load(f)

def create_db_connection():
    """
    Crear y retornar una conexión a la base de datos
    """
    try:
        config = load_config()
        connection = mysql.connector.connect(
            host=config['DB_HOST'],
            database=config['DB_NAME'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD']
        )
        return connection, None
    except Error as err:
        return None, {
            'error': err,
            'errno': err.errno if hasattr(err, 'errno') else None,
            'sqlstate': err.sqlstate if hasattr(err, 'sqlstate') else None,
            'msg': str(err)
        }

def guardar_datos_lote(shop_order, spec, turno, badge, maquina):  
    """
    Guardar los datos en la base de datos
    Si no se proporciona fecha_prueba, se usará la fecha del servidor
    """
    fecha_prueba = None  # Puedes modificar esto para aceptar una fecha específica si lo deseas
    connection, error = create_db_connection()
    
    if error:
        return False, f"Error de conexión: {error['msg']}"
    
    try:
        cursor = connection.cursor()
        
        # Si no se proporciona fecha, se usará el valor por defecto del servidor
        if fecha_prueba is None:
            query = """
            INSERT INTO test_limits (
                shop_order, 
                spec, 
                turno, 
                badge, 
                maquina
            ) VALUES (%s, %s, %s, %s, %s)
            """
            valores = (shop_order, spec, turno, badge, maquina)
        else:
            # Si se proporciona una fecha específica
            query = """
            INSERT INTO test_limits (
                shop_order, 
                spec, 
                turno, 
                badge, 
                maquina
            ) VALUES (%s, %s, %s, %s, %s)
            """
            valores = (shop_order, spec, turno, badge, maquina)
        
        # Ejecutar la consulta
        cursor.execute(query, valores)
        
        # Confirmar la transacción
        connection.commit()
        
        return True, "Datos guardados exitosamente"
    
    except Error as e:
        return False, f"Error al guardar los datos: {str(e)}"
    
    finally:
        # Cerrar cursor y conexión
        if connection.is_connected():
            cursor.close()
            connection.close()


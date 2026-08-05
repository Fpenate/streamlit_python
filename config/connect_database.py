import json
import mysql.connector
from mysql.connector import Error

# Cargar configuración de la base de datos
def load_config():
    with open('config_db.json') as f:
        return json.load(f)

# Crear conexión a la base de datos
def create_db_connection(config):
    try:
        connection = mysql.connector.connect(
            host=config['DB_HOST'],
            database=config['DB_NAME'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD']
        )
        return connection, None
    except Error as err:
        # Devolver tanto el error como su mensaje detallado
        return None, {
            'error': err,
            'errno': err.errno if hasattr(err, 'errno') else None,
            'sqlstate': err.sqlstate if hasattr(err, 'sqlstate') else None,
            'msg': str(err)
        }
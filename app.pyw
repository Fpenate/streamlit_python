import subprocess
import os
import socket
import webbrowser
import time

#script para iniciar la app de Streamlit en segundo plano y abrir el navegador

def is_port_in_use(port):
    """Verifica si el puerto ya está en uso"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Cambiar al directorio del script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Verificar si Streamlit ya está corriendo
if is_port_in_use(8501):
    # Si ya está corriendo, solo abrir el navegador
    webbrowser.open('http://localhost:8501')
else:
    # Si no está corriendo, iniciar Streamlit
    subprocess.Popen([
        r"venv\Scripts\python.exe",
        "-m", "streamlit", "run", "app.py",
        "--browser.gatherUsageStats", "false"
    ], creationflags=subprocess.CREATE_NO_WINDOW)
    
    # Esperar un poco y abrir el navegador
    time.sleep(3)
    webbrowser.open('http://localhost:8501')
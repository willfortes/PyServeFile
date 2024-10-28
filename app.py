import os
import sys
import threading
import logging
from flask import Flask, send_from_directory, render_template_string, abort, url_for, Response
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import pyperclip
import webbrowser
from plyer import notification

app = Flask(__name__)

BASE_DIR = os.path.expanduser("~")
PORT = 5000
HOST = "http://127.0.0.1"
LOG_FILE = "file_server.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Função para detectar drives no Windows
def get_drives():
    from string import ascii_uppercase
    return [f"{drive}:/" for drive in ascii_uppercase if os.path.exists(f"{drive}:/")]

@app.route('/')
@app.route('/<path:subpath>')
def file_list(subpath=""):
    if subpath == "":
        drives = get_drives()
        drive_links = [f"<li><a href='{url_for('file_list', subpath=drive)}'>{drive}</a></li>" for drive in drives]
        html_content = f"""
        <html>
        <head><title>Servidor de Arquivos</title></head>
        <body>
        <h2>Unidades disponíveis:</h2>
        <ul>{''.join(drive_links)}</ul>
        </body>
        </html>
        """
        return render_template_string(html_content)

    current_path = os.path.join(BASE_DIR, subpath)
    if not os.path.exists(current_path):
        abort(404)

    items = os.listdir(current_path)
    files = []
    directories = []

    for item in items:
        item_path = os.path.join(current_path, item)
        if os.path.isdir(item_path):
            directories.append(item)
        else:
            files.append(item)

    logger.info(f"Acessou o caminho: {current_path}")
    html_content = f"""
    <html>
    <head><title>Servidor de Arquivos</title></head>
    <body>
    <h2>Navegando em: {current_path}</h2>
    <a href='{url_for('file_list', subpath='/'.join(subpath.split('/')[:-1]))}'>Voltar</a><br><br>
    <h3>Pastas:</h3>
    <ul>
        {''.join([f"<li><a href='{url_for('file_list', subpath=os.path.join(subpath, directory))}'>{directory}</a></li>" for directory in directories])}
    </ul>
    <h3>Arquivos:</h3>
    <ul>
        {''.join([f"<li><a href='{url_for('download_file', filepath=os.path.join(subpath, file))}'>{file}</a></li>" for file in files])}
    </ul>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/download/<path:filepath>')
def download_file(filepath):
    directory, filename = os.path.split(filepath)
    logger.info(f"Download solicitado: {filepath}")
    return send_from_directory(os.path.join(BASE_DIR, directory), filename, as_attachment=True)

@app.route('/logs')
def view_logs():
    """Exibe os logs em tempo real."""
    def generate():
        with open(LOG_FILE, "r") as f:
            while True:
                line = f.readline()
                if line:
                    yield line + "<br>"
                else:
                    break
    return Response(generate(), mimetype='text/html')

def run_flask():
    """Função para rodar o servidor Flask em uma thread."""
    app.run(host='0.0.0.0', port=PORT)

def create_icon(color):
    """Cria um ícone colorido para a bandeja (verde para on, vermelho para off)."""
    image = Image.new("RGB", (64, 64), color=color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, 48, 48), fill=color)
    return image

def show_notification(title, message):
    """Exibe uma notificação na área de trabalho do Windows."""
    notification.notify(
        title=title,
        message=message,
        app_name="Flask File Server",
        timeout=5  # Tempo em segundos que a notificação ficará visível
    )

def start_server(icon, item):
    """Inicia o servidor Flask."""
    global server_thread
    if not server_thread or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_flask, daemon=True)
        server_thread.start()
    icon.icon = create_icon("green")  # Ícone verde quando "on"
    icon.visible = True
    logger.info("Servidor iniciado.")
    show_notification("Servidor Iniciado", f"O servidor está rodando em {HOST}:{PORT}")

def stop_server(icon, item):
    """Para o servidor Flask."""
    global server_thread
    if server_thread and server_thread.is_alive():
        icon.icon = create_icon("red")  # Ícone vermelho quando "off"
        icon.visible = True
        logger.info("Servidor parado.")
        show_notification("Servidor Parado", "O servidor foi interrompido.")

def copy_to_clipboard(icon, item):
    """Copia o host e a porta atuais para a área de transferência."""
    pyperclip.copy(f"{HOST}:{PORT}")
    logger.info("Host copiado para a área de transferência.")

def open_logs(icon, item):
    """Abre a página de visualização dos logs no navegador."""
    webbrowser.open(f"{HOST}:{PORT}/logs")
    logger.info("Visualização de logs acessada.")

def exit_app(icon, item):
    """Fecha o aplicativo e para o servidor."""
    stop_server(icon, item)
    icon.stop()
    logger.info("Aplicativo encerrado.")
    sys.exit()

def setup_tray_icon():
    """Configura o ícone da bandeja do sistema com opções para controlar o servidor."""
    icon = pystray.Icon(
        "FlaskFileServer",
        icon=create_icon("red"),  # Inicia com ícone vermelho (servidor desligado)
        menu=pystray.Menu(
            item(f"Host: {HOST}:{PORT}", lambda: None, enabled=False),  # Informação do host e porta
            item('Copy Host to Clipboard', copy_to_clipboard),
            item('Open Logs', open_logs),  # Abre logs no navegador
            item('Start', start_server),
            item('Stop', stop_server),
            item('Exit', exit_app)
        )
    )
    icon.run()

if __name__ == "__main__":
    server_thread = None  # Inicializa a variável da thread do servidor
    
    # Inicia o ícone da bandeja em uma thread separada
    tray_thread = threading.Thread(target=setup_tray_icon)
    tray_thread.start()

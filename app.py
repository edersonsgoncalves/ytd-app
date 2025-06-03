import subprocess
from flask import Flask, render_template, request, send_file, jsonify
import os
import io # Para capturar a saída do subprocesso
import threading # Para rodar o download em thread separada
import queue # Para comunicação entre threads

app = Flask(__name__)

# Define o diretório onde os vídeos serão baixados
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', '/app/downloads_default') 

# Cria a pasta de download se ela não existir
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Fila para armazenar os logs de download para exibição na web
# Usamos uma fila para que a thread de download possa enviar logs
# e a thread da web possa lê-los.
download_log_queue = queue.Queue()
current_download_filename = None # Para saber qual arquivo está sendo baixado atualmente

@app.route('/', methods=['GET', 'POST'])
def index():
    global current_download_filename
    if request.method == 'POST':
        video_url = request.form['video_url']
        if video_url:
            # Limpa a fila de logs para um novo download
            with download_log_queue.mutex:
                download_log_queue.queue.clear()
            
            # Reset o nome do arquivo atual
            current_download_filename = None

            # Inicia o download em uma thread separada para não travar a UI
            download_thread = threading.Thread(target=perform_download, args=(video_url,))
            download_thread.start()

            # Retorna uma mensagem indicando que o download foi iniciado.
            # O frontend vaiPolling o endpoint /logs
            return render_template('index.html', message="Download iniciado. Verifique o log abaixo para o progresso.", status="info", download_in_progress=True)
        else:
            return render_template('index.html', message="Por favor, forneça um link de vídeo.", status="error")
    
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    # Retorna todos os logs acumulados na fila até o momento
    logs = []
    while not download_log_queue.empty():
        logs.append(download_log_queue.get())
    return jsonify({"logs": logs, "download_finished": current_download_filename is not None})

@app.route('/download_file')
def download_file_route():
    global current_download_filename
    if current_download_filename and os.path.exists(current_download_filename):
        # Limpa o nome do arquivo atual após o envio para evitar re-downloads acidentais
        # ou indica que o download foi "consumido" pelo navegador.
        file_to_send = current_download_filename
        current_download_filename = None 
        return send_file(file_to_send, as_attachment=True)
    else:
        return jsonify({"error": "Arquivo não encontrado ou download não concluído."}), 404

def perform_download(video_url):
    global current_download_filename
    try:
        download_log_queue.put("Iniciando download de: " + video_url + "\n")

        # Primeiro, obtemos o nome do arquivo para saber o que procurar depois
        info_command = ['yt-dlp', '--get-filename', '-o', '%(title)s.%(ext)s', video_url]
        try:
            filename_template = subprocess.check_output(info_command, text=True, stderr=subprocess.PIPE).strip()
            download_log_queue.put(f"Nome de arquivo esperado: {filename_template}\n")
            # yt-dlp pode retornar um caminho completo, queremos apenas o basename para comparação
            expected_base_filename_prefix = os.path.basename(filename_template).split('.')[0]
        except subprocess.CalledProcessError as e:
            download_log_queue.put(f"Erro ao obter nome do arquivo: {e.stderr}\n")
            raise

        # Comando para baixar o vídeo com saída para stdout (pipe)
        # --progress: Exibe o progresso de download
        # --newline: Força uma nova linha após cada atualização de progresso
        download_command = [
            'yt-dlp', 
            '-o', os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'), 
            '--restrict-filenames', 
            '--progress', # Adiciona progresso
            '--newline',  # Força nova linha para melhor parsing
            video_url
        ]
        
        # Abre o subprocesso para ler sua saída em tempo real
        process = subprocess.Popen(download_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in iter(process.stdout.readline, ''):
            download_log_queue.put(line) # Adiciona cada linha do log do yt-dlp
        
        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            download_log_queue.put(f"yt-dlp retornou um erro com código: {return_code}\n")
            # Se o erro for de yt-dlp, ele já foi capturado no `for line in ...`
            raise subprocess.CalledProcessError(return_code, download_command)
        
        download_log_queue.put("Download concluído. Tentando localizar o arquivo...\n")

        # Agora, aprimoramos a lógica para encontrar o arquivo baixado
        # É crucial porque --restrict-filenames e yt-dlp podem alterar o nome final.
        found_file = None
        # Lista arquivos no diretório de download
        for f in os.listdir(DOWNLOAD_FOLDER):
            # Verifica se o arquivo começa com o prefixo esperado e se é um arquivo (não um diretório)
            if f.startswith(expected_base_filename_prefix) and os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f)):
                found_file = os.path.join(DOWNLOAD_FOLDER, f)
                break
        
        if found_file and os.path.exists(found_file):
            current_download_filename = found_file
            download_log_queue.put(f"Arquivo localizado: {os.path.basename(found_file)}\n")
            download_log_queue.put("Download pronto para ser enviado ao navegador.\n")
            download_log_queue.put("__DOWNLOAD_COMPLETE__\n") # Sinal para o frontend
        else:
            download_log_queue.put(f"Erro: Não foi possível encontrar o arquivo baixado com prefixo '{expected_base_filename_prefix}'.\n")
            current_download_filename = None # Garantir que não tenta enviar arquivo inexistente
            download_log_queue.put("__DOWNLOAD_FAILED__\n")

    except subprocess.CalledProcessError as e:
        download_log_queue.put(f"Erro no processo de download: {e}\n")
        download_log_queue.put("__DOWNLOAD_FAILED__\n")
    except Exception as e:
        download_log_queue.put(f"Ocorreu um erro inesperado: {e}\n")
        download_log_queue.put("__DOWNLOAD_FAILED__\n")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
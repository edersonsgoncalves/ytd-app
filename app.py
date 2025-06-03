import subprocess
from flask import Flask, render_template, request, send_file, jsonify
import os
import threading # Para rodar o download em thread separada
import queue # Para comunicação entre threads

app = Flask(__name__)

# Define o diretório onde os vídeos serão baixados
# Ele tenta pegar da variável de ambiente DOWNLOAD_FOLDER, senão usa um padrão
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', '/var/www/html/ytd/downloads') 

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
            # O frontend vai "pollear" o endpoint /logs para o progresso.
            return render_template('index.html', message="Download iniciado. Verifique o log abaixo para o progresso.", status="info", download_in_progress=True)
        else:
            return render_template('index.html', message="Por favor, forneça um link de vídeo.", status="error")
    
    # Para requisições GET, renderiza o formulário inicial
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    # Retorna todos os logs acumulados na fila até o momento
    logs = []
    while not download_log_queue.empty():
        logs.append(download_log_queue.get())
    
    # Verifica se o download foi concluído (se current_download_filename não é None)
    # ou se um dos sinalizadores de fim foi colocado na fila
    download_finished_signal = False
    if "__DOWNLOAD_COMPLETE__\n" in logs:
        download_finished_signal = True
    elif "__DOWNLOAD_FAILED__\n" in logs:
        download_finished_signal = True

    return jsonify({"logs": logs, "download_finished": download_finished_signal})

@app.route('/download_file')
def download_file_route():
    global current_download_filename
    if current_download_filename and os.path.exists(current_download_filename):
        # Armazena o caminho do arquivo para enviar antes de limpar a variável global
        file_to_send = current_download_filename
        
        # Limpa o nome do arquivo atual após o envio para evitar re-downloads acidentais
        # ou indica que o download foi "consumido" pelo navegador.
        current_download_filename = None 
        
        # Envia o arquivo como anexo, forçando o download no navegador
        return send_file(file_to_send, as_attachment=True)
    else:
        # Se o arquivo não for encontrado ou o download não tiver sido concluído
        return jsonify({"error": "Arquivo não encontrado ou download não concluído."}), 404

def perform_download(video_url):
    global current_download_filename
    try:
        download_log_queue.put("Iniciando download de: " + video_url + "\n")

        # Primeiro, usamos yt-dlp para obter o nome de arquivo esperado.
        # Isso é crucial para depois localizar o arquivo baixado, especialmente com --restrict-filenames.
        info_command = ['yt-dlp', '--get-filename', '-o', '%(title)s.%(ext)s', video_url]
        try:
            filename_template = subprocess.check_output(info_command, text=True, stderr=subprocess.PIPE).strip()
            download_log_queue.put(f"Nome de arquivo esperado: {filename_template}\n")
            # Extrai o prefixo do nome do arquivo (antes da extensão) para comparação futura
            expected_base_filename_prefix = os.path.basename(filename_template).split('.')[0]
        except subprocess.CalledProcessError as e:
            download_log_queue.put(f"Erro ao obter nome do arquivo: {e.stderr}\n")
            raise # Re-lança a exceção para ser capturada pelo bloco try/except externo

        # Comando para baixar o vídeo
        # -f: Define a preferência de formato
        #   'bv[ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best' significa:
        #   1. Melhor vídeo MP4 + Melhor áudio M4A (e mescla)
        #   2. OU Melhor formato que já seja MP4 completo
        #   3. OU O melhor formato disponível (qualquer um)
        # -o: Define o nome do arquivo de saída no DOWNLOAD_FOLDER
        # --restrict-filenames: Remove caracteres especiais do nome do arquivo
        # --progress: Exibe o progresso de download no stdout
        # --newline: Força uma nova linha após cada atualização de progresso para facilitar o parsing
        download_command = [
            'yt-dlp', 
            '-f', 'bv[ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best', 
            '-o', os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'), 
            '--restrict-filenames', 
            '--progress', 
            '--newline',  
            video_url
        ]
        
        # Abre o subprocesso para ler sua saída em tempo real
        # stdout=subprocess.PIPE: Captura a saída padrão
        # stderr=subprocess.STDOUT: Redireciona a saída de erro para a saída padrão,
        #                           assim tudo vai para o mesmo pipe.
        # text=True: Decodifica a saída como texto
        # bufsize=1: Buffer de linha para leitura em tempo real
        process = subprocess.Popen(download_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        # Lê a saída do subprocesso linha por linha e a adiciona à fila de logs
        for line in iter(process.stdout.readline, ''):
            download_log_queue.put(line) 
        
        process.stdout.close() # Fecha o pipe de saída
        return_code = process.wait() # Espera o processo terminar e obtém o código de retorno

        if return_code != 0:
            download_log_queue.put(f"yt-dlp retornou um erro com código: {return_code}\n")
            # Se o yt-dlp retornar um código de erro, levanta uma exceção
            raise subprocess.CalledProcessError(return_code, download_command)
        
        download_log_queue.put("Download concluído. Tentando localizar o arquivo...\n")

        # Lógica aprimorada para encontrar o arquivo baixado
        # É crucial porque --restrict-filenames e yt-dlp podem alterar o nome final,
        # e a mesclagem pode resultar em uma extensão diferente (e.g., .mkv).
        found_file = None
        
        # 1. Tenta encontrar o arquivo mesclado (geralmente .mkv para vídeo+áudio)
        # Substitui a extensão no template pelo .mkv
        merged_filename_mkv = os.path.join(DOWNLOAD_FOLDER, os.path.basename(filename_template).replace('.%(ext)s', '.mkv'))
        if os.path.exists(merged_filename_mkv):
            found_file = merged_filename_mkv
        else:
            # 2. Se o .mkv não foi encontrado, procura por qualquer arquivo
            #    que comece com o prefixo do nome esperado no diretório de downloads.
            for f in os.listdir(DOWNLOAD_FOLDER):
                # Verifica se o arquivo começa com o prefixo esperado E se é um arquivo (não um diretório)
                if f.startswith(expected_base_filename_prefix) and os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f)):
                    found_file = os.path.join(DOWNLOAD_FOLDER, f)
                    break # Encontrou o primeiro que corresponde, sai do loop
        
        if found_file and os.path.exists(found_file):
            current_download_filename = found_file # Armazena o caminho completo do arquivo encontrado
            download_log_queue.put(f"Arquivo localizado: {os.path.basename(found_file)}\n")
            download_log_queue.put("Download pronto para ser enviado ao navegador.\n")
            download_log_queue.put("__DOWNLOAD_COMPLETE__\n") # Sinal para o frontend que o download foi um sucesso
        else:
            download_log_queue.put(f"Erro: Não foi possível encontrar o arquivo baixado com prefixo '{expected_base_filename_prefix}'.\n")
            current_download_filename = None # Garante que não tenta enviar um arquivo inexistente
            download_log_queue.put("__DOWNLOAD_FAILED__\n") # Sinal para o frontend que o download falhou

    except subprocess.CalledProcessError as e:
        # Captura erros específicos do subprocesso (yt-dlp)
        download_log_queue.put(f"Erro no processo de download (código {e.returncode}): {e}\n")
        download_log_queue.put("__DOWNLOAD_FAILED__\n")
    except Exception as e:
        # Captura quaisquer outros erros inesperados
        download_log_queue.put(f"Ocorreu um erro inesperado: {e}\n")
        download_log_queue.put("__DOWNLOAD_FAILED__\n")

if __name__ == '__main__':
    # Execute a aplicação em 0.0.0.0 para que ela seja acessível de outras máquinas na rede
    # A porta 5000 é a porta interna do container. O mapeamento externo é feito no 'docker run'.
    # debug=True é bom para desenvolvimento (reinicia o servidor em mudanças, exibe erros),
    # mas deve ser desligado em produção por questões de segurança e performance.
    app.run(host='0.0.0.0', port=9500, debug=True)

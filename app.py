import subprocess
from flask import Flask, render_template, request, send_file, jsonify
import os
import threading # Para rodar o download em thread separada
import queue # Para comunicação entre threads
import re # Importar para usar expressões regulares

app = Flask(__name__)

# Define o diretório onde os vídeos serão baixados
# Ele tenta pegar da variável de ambiente DOWNLOAD_FOLDER, senão usa um padrão
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
    
    # Variáveis para passar para o template
    message = None
    status = "info"
    download_in_progress = False

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

            # Define as variáveis para o template após iniciar o download
            message = "Download iniciado. Verifique o log abaixo para o progresso."
            status = "info"
            download_in_progress = True
        else:
            # Define as variáveis para o template em caso de URL vazia
            message = "Por favor, forneça um link de vídeo."
            status = "error"
            download_in_progress = False # Não há download em progresso

    # Para requisições GET ou após um POST, renderiza o formulário inicial
    # passando as variáveis de estado.
    return render_template('index.html', message=message, status=status, download_in_progress=download_in_progress)

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
    final_downloaded_path = None # Variável para armazenar o caminho exato do arquivo final

    try:
        download_log_queue.put("Iniciando download de: " + video_url + "\n")

        # Comando para baixar o vídeo
        # -f: Define a preferência de formato (MP4 prioritário)
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
        process = subprocess.Popen(download_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        # Coleta todas as linhas de saída para análise posterior e envia para a fila de logs
        all_output_lines = []
        for line in iter(process.stdout.readline, ''):
            all_output_lines.append(line)
            download_log_queue.put(line) 
        
        process.stdout.close() # Fecha o pipe de saída
        return_code = process.wait() # Espera o processo terminar e obtém o código de retorno

        if return_code != 0:
            download_log_queue.put(f"yt-dlp retornou um erro com código: {return_code}\n")
            # Se o yt-dlp retornar um código de erro, levanta uma exceção
            raise subprocess.CalledProcessError(return_code, download_command)
        
        download_log_queue.put("Download concluído. Tentando localizar o arquivo...\n")

        # --- Lógica para encontrar o nome do arquivo final a partir dos logs do yt-dlp ---
        merger_regex = re.compile(r'\[Merger\] Merging formats into "(.*)"')
        destination_regex = re.compile(r'\[download\] Destination: (.*)')

        # 1. Procura pela linha de mesclagem (mais confiável para vídeos com áudio separado)
        # Percorre as linhas de trás para frente, pois a linha de mesclagem costuma ser uma das últimas
        for line in reversed(all_output_lines):
            match = merger_regex.search(line)
            if match:
                final_downloaded_path = match.group(1).strip()
                break
        
        # 2. Se não encontrou uma linha de mesclagem, procura pela última linha de destino de download
        # Isso ocorre para downloads de arquivos únicos que não precisam de mesclagem.
        if not final_downloaded_path:
            for line in reversed(all_output_lines):
                match = destination_regex.search(line)
                if match:
                    final_downloaded_path = match.group(1).strip()
                    # Adiciona uma verificação extra para evitar pegar arquivos temporários de formato (e.g., .f137.mp4)
                    # Se o nome do arquivo não contém '.f' seguido de números e ponto, é mais provável que seja o final.
                    # Isso é uma heurística, o regex do Merger é mais robusto.
                    if not re.search(r'\.f\d+\.', final_downloaded_path):
                        break 
                    else: # Se for um arquivo intermediário, continua procurando
                        final_downloaded_path = None # Reseta para continuar a busca
        
        # 3. Verifica se o caminho final encontrado existe e é um arquivo válido
        if final_downloaded_path and os.path.exists(final_downloaded_path) and os.path.isfile(final_downloaded_path):
            current_download_filename = final_downloaded_path # Armazena o caminho completo do arquivo encontrado
            download_log_queue.put(f"Arquivo localizado: {os.path.basename(final_downloaded_path)}\n")
            download_log_queue.put("Download pronto para ser enviado ao navegador.\n")
            download_log_queue.put("__DOWNLOAD_COMPLETE__\n") # Sinal para o frontend que o download foi um sucesso
        else:
            # Fallback se a análise do log falhar ou o arquivo não for encontrado no caminho analisado
            download_log_queue.put(f"Erro: Não foi possível localizar o arquivo baixado através da análise do log. Verifique o diretório de downloads manualmente.\n")
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
    # A porta 9500 é a porta interna do container, conforme sua instrução.
    # debug=True é bom para desenvolvimento (reinicia o servidor em mudanças, exibe erros),
    # mas deve ser desligado em produção por questões de segurança e performance.
    app.run(host='0.0.0.0', port=9500, debug=True)

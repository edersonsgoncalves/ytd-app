import subprocess
from flask import Flask, render_template, request, send_file
import os

app = Flask(__name__)

# Define o diretório onde os vídeos serão baixados
DOWNLOAD_FOLDER = '/var/www/html/ytd/downloads' # Mude para o caminho desejado

# Cria a pasta de download se ela não existir
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form['video_url']
        if video_url:
            try:
                # Usa yt-dlp para obter informações do vídeo (título e extensão)
                # Isso nos ajuda a dar um nome de arquivo razoável
                info_command = ['yt-dlp', '--get-filename', '-o', '%(title)s.%(ext)s', video_url]
                filename = subprocess.check_output(info_command, text=True).strip()
                
                # O yt-dlp pode retornar um caminho completo se já existir, 
                # então pegamos apenas o nome base
                base_filename = os.path.basename(filename)
                
                output_path = os.path.join(DOWNLOAD_FOLDER, base_filename)

                # Comando para baixar o vídeo
                # -o: define o nome do arquivo de saída
                # --restrict-filenames: remove caracteres especiais do nome do arquivo
                download_command = [
                    'yt-dlp', 
                    '-o', os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'), 
                    '--restrict-filenames', 
                    video_url
                ]
                
                subprocess.run(download_command, check=True)
                
                # Tenta encontrar o arquivo exato baixado (pode variar com --restrict-filenames)
                # Pega o primeiro arquivo que começa com o título aproximado
                downloaded_file = None
                for f in os.listdir(DOWNLOAD_FOLDER):
                    if f.startswith(base_filename.split('.')[0]): # Compara pelo título antes da extensão
                        downloaded_file = os.path.join(DOWNLOAD_FOLDER, f)
                        break
                
                if downloaded_file and os.path.exists(downloaded_file):
                    return send_file(downloaded_file, as_attachment=True)
                else:
                    return render_template('index.html', message="Erro ao encontrar o arquivo baixado. Verifique os logs do servidor.", status="error")

            except subprocess.CalledProcessError as e:
                return render_template('index.html', message=f"Erro ao baixar o vídeo: {e}", status="error")
            except Exception as e:
                return render_template('index.html', message=f"Ocorreu um erro inesperado: {e}", status="error")
        else:
            return render_template('index.html', message="Por favor, forneça um link de vídeo.", status="error")
    
    return render_template('index.html')

if __name__ == '__main__':
    # Execute a aplicação em 0.0.0.0 para que ela seja acessível de outras máquinas na rede
    # O porto 5000 é o padrão do Flask, mas você pode mudar para 9500 se preferir
    app.run(host='0.0.0.0', port=5000, debug=True) # debug=True é bom para desenvolvimento, mas desligue em produção

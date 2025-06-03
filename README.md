# YouTube Downloader - Web Interface
Uma interface web simples e leve para baixar vídeos e áudios do YouTube e de outras plataformas suportadas pelo `yt-dlp` diretamente para o seu servidor, com download imediato para o seu navegador.

### Descrição
Este projeto oferece uma solução prática para quem precisa baixar conteúdo de vídeo/áudio de diversas fontes (como YouTube) para um servidor remoto e, em seguida, transferir esse arquivo diretamente para o navegador local. Desenvolvido com Flask e containerizado com Docker, ele elimina a necessidade de acesso SSH para iniciar downloads ou de servidores HTTP temporários para acessar os arquivos.

### Funcionalidades
* *Download Simplificado*: Cole a URL do vídeo e clique em um botão para iniciar o download.
* *Priorização de MP4*: Tenta baixar o conteúdo no formato MP4 (vídeo + áudio) por padrão. Se o MP4 não estiver disponível, faz fallback para o melhor formato disponível.
* *Logs em Tempo Real*: Acompanhe o progresso do download e quaisquer mensagens do `yt-dlp` diretamente na interface web.
* *Download Direto para o Navegador*: Após a conclusão do download no servidor, um botão é disponibilizado para baixar o arquivo diretamente para o seu dispositivo local.
* *Containerizado com Docker*: Fácil de configurar e implantar em qualquer ambiente que suporte Docker, garantindo isolamento e portabilidade.

### Tecnologias Utilizadas
**Python 3**: Linguagem de programação principal.
**Flask**: Micro-framework web para o backend.
**yt-dlp**: Ferramenta de linha de comando para download de vídeos.
**FFmpeg**: Ferramenta essencial para processamento e mesclagem de áudio/vídeo, utilizada pelo yt-dlp.
**Docker**: Para containerização da aplicação.
**HTML, CSS, JavaScript**: Para a interface do usuário no frontend.
**Gemini**: Compilador do código (código gerado por IA - Supervisionado)

<a href="https://flask.palletsprojects.com/en/stable/" target="_blank" rel="noreferrer"><img src="https://flask.palletsprojects.com/en/stable/_images/flask-horizontal.png" alt="flask" height="40"/></a>  <a href="https://www.python.org" target="_blank" rel="noreferrer"><img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" alt="python" height="40"/></a>  <a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noreferrer"><img src="https://avatars.githubusercontent.com/u/79589310?s=48&v=4" alt="yt-dlp" height="40"/></a>  <a href="https://ffmpeg.org/" target="_blank" rel="noreferrer"><img src="https://trac.ffmpeg.org/ffmpeg-logo.png" alt="ffmpeg" height="40"/></a> <a href="https://www.docker.com/" target="_blank" rel="noreferrer"><img src="https://banner2.cleanpng.com/20180802/ipp/c26b0dc2951a5195ae50c46f6be2544e.webp" alt="docker" height="40"/></a> <a href="https://www.docker.com/" target="_blank" rel="noreferrer"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/344px-Google_Gemini_logo.svg.png" alt="gemini" height="40"/></a>  <a href="https://www.w3schools.com/css/" target="_blank" rel="noreferrer"><img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/css3/css3-original-wordmark.svg" alt="css3" width="40" height="40"/></a>  <a href="https://git-scm.com/" target="_blank" rel="noreferrer"><img src="https://www.vectorlogo.zone/logos/git-scm/git-scm-icon.svg" alt="git" width="40" height="40"/></a> <a href="https://www.w3.org/html/" target="_blank" rel="noreferrer"><img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/html5/html5-original-wordmark.svg" alt="html5" width="40" height="40"/></a> <a href="https://developer.mozilla.org/en-US/docs/Web/JavaScript" target="_blank" rel="noreferrer"><img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/javascript/javascript-original.svg" alt="javascript" width="40" height="40"/></a>  

### Estrutura do Projeto
├── app.py                  # Lógica do backend Flask
├── requirements.txt        # Dependências Python (Flask, yt-dlp)
├── Dockerfile              # Instruções para construir a imagem Docker
├── deploy.sh               # Script para automatizar o deploy Docker
└── templates/
    └── index.html          # Interface web (frontend)

### Pré-requisitos
* Docker instalado e configurado no seu servidor.
* Configuração e Execução
* Siga estes passos para colocar o aplicativo em funcionamento:
	* Clone o Repositório (ou crie os arquivos):
	* Crie a estrutura de diretórios e os arquivos (app.py, requirements.txt, Dockerfile, deploy.sh, e a pasta templates com index.html) no seu servidor. Por exemplo, em /var/www/html/ytd/.
	* Ajuste o Caminho de Download (Opcional, mas recomendado):
		No arquivo deploy.sh, a variável HOST_DOWNLOAD_PATH está definida como /var/www/html/ytd/downloads. Certifique-se de que este caminho exista no seu servidor e que o usuário Docker tenha permissões de escrita nele. Você pode alterá-lo para um diretório de sua preferência.
	* Dê Permissões de Execução ao Script de Deploy:
		* Navegue até o diretório raiz do seu projeto no terminal do servidor e execute:
			`chmod +x deploy.sh`
		* Execute o Script de Deploy:
			Este script irá parar qualquer container existente com o mesmo nome, removê-lo, construir uma nova imagem Docker com as últimas alterações e iniciar um novo container.
			`./deploy.sh`
			Você verá a saída do processo de construção e inicialização.

### Como Usar o Aplicativo
**Acesse a Interface Web:**
Abra seu navegador e digite o endereço IP do seu servidor seguido da porta 9500. Por exemplo: `http://<IP_DO_SEU_SERVIDOR>:9500` (substitua <IP_DO_SEU_SERVIDOR> pelo IP real do seu servidor).  

**Cole a URL:**
No campo de texto, cole a URL do vídeo ou áudio que você deseja baixar.

**Inicie o Download:**
Clique no botão "Baixar Vídeo". O log de progresso aparecerá abaixo do formulário.

**Baixe o Arquivo:**
Após a mensagem "Download concluído com sucesso no servidor!", um link "Baixar Arquivo" aparecerá. Clique nele para fazer o download do arquivo para o seu dispositivo local.

### Logs e Depuração
Se você encontrar problemas ou quiser monitorar o que está acontecendo no container, você pode ver os logs do Docker em tempo real:
`docker logs -f ytd`

### Considerações para Produção
Para um ambiente de produção, algumas práticas são recomendadas:
- *Desligue o Modo Debug*: No `app.py`, altere `debug=True` para `debug=False`.
- *Servidor WSGI*: Use um servidor WSGI como Gunicorn ou uWSGI para servir a aplicação Flask de forma mais robusta e performática.
- *Proxy Reverso*: Considere usar um proxy reverso como Nginx ou Apache para lidar com o tráfego web, SSL/TLS e balanceamento de carga.
- *Segurança de Rede*: Configure firewalls (como ufw no Linux ou as regras de segurança do seu provedor de nuvem) para permitir apenas o tráfego necessário na porta da aplicação.
- *Gerenciamento de Volumes*: Garanta que o volume de downloads seja persistente e tenha backups adequados.

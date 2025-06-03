# Usa uma imagem base oficial do Python.
# A tag "3.10-slim-buster" é boa porque é leve e baseada em Debian.
FROM python:3.10-slim-buster

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo requirements.txt para o container
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala yt-dlp e ffmpeg (essencial para muitos downloads e conversões)
# yt-dlp pode ser instalado via pip, mas ffmpeg é uma dependência do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    # yt-dlp pode ser instalado via pip, mas ter certeza que está disponível
    # ou podemos confiar no pip install yt-dlp acima.
    # Para ter certeza que yt-dlp está disponível globalmente no container:
    # pip install yt-dlp (já feito no requirements.txt)
    # Alguns usuários preferem instalar yt-dlp via pacote do sistema (se disponível)
    # ou baixá-lo diretamente, mas pip é o mais comum para esta setup.
    # Se yt-dlp for um binário global no sistema, você precisaria adicioná-lo aqui.
    # No caso do pip install, ele estará no PATH do ambiente Python.
    && rm -rf /var/lib/apt/lists/*

# Copia todo o restante do seu código da aplicação para o diretório de trabalho
COPY . .

# Cria o diretório de downloads dentro do container e define permissões
# Este diretório será mapeado para um volume no host
RUN mkdir -p /downloads && chmod a+rwx /downloads

# Expõe a porta que a aplicação Flask vai usar
EXPOSE 9500

# Define a variável de ambiente para a pasta de downloads
# Certifique-se que o Flask use esta variável ou o caminho absoluto '/downloads'
ENV DOWNLOAD_FOLDER=/downloads

# Comando para rodar a aplicação quando o container iniciar
# Usando gunicorn para produção é melhor, mas para teste, o Flask embutido serve
# CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
# Para a sua app.py, que usa app.run(), basta:
CMD ["python", "app.py"]

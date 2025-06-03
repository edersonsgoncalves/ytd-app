#!/bin/bash

# --- Configurações da Aplicação ---
# Nome da imagem Docker que será construída
IMAGE_NAME="ytd-app"
# Nome do container Docker que será criado
CONTAINER_NAME="ytd"
# Porta no host que será mapeada para a porta do container
HOST_PORT="9500"
# Porta interna do container onde a aplicação Flask está rodando
CONTAINER_PORT="9500" # Conforme sua última instrução
# Caminho no host para a pasta de downloads que será mapeada para o container
HOST_DOWNLOAD_PATH="/var/www/html/ytd/downloads"
# Caminho dentro do container onde os downloads serão salvos
CONTAINER_DOWNLOAD_PATH="/downloads"

# --- Navegar para o diretório do script (garante que o build aconteça no local correto) ---
# Obtém o diretório onde o script está localizado
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "--- Iniciando o processo de deploy para $CONTAINER_NAME ---"

# --- 1. Parar o container existente (se estiver rodando) ---
echo "Verificando se o container '$CONTAINER_NAME' está rodando..."
if sudo docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
    echo "Parando o container '$CONTAINER_NAME'..."
    sudo docker stop "$CONTAINER_NAME"
else
    echo "Container '$CONTAINER_NAME' não está rodando."
fi

# --- 2. Remover o container existente (se existir) ---
echo "Verificando se o container '$CONTAINER_NAME' existe..."
if sudo docker ps -aq --filter "name=$CONTAINER_NAME" | grep -q .; then
    echo "Removendo o container '$CONTAINER_NAME'..."
    sudo docker rm "$CONTAINER_NAME"
else
    echo "Container '$CONTAINER_NAME' não existe."
fi

# --- 3. Construir a nova imagem Docker ---
echo "Construindo a imagem Docker '$IMAGE_NAME'..."
# O '.' no final indica que o Dockerfile está no diretório atual
sudo docker build -t "$IMAGE_NAME" .

# Verifica se a construção da imagem foi bem-sucedida
if [ $? -ne 0 ]; then
    echo "Erro: Falha ao construir a imagem Docker. Verifique as mensagens acima."
    exit 1
fi
echo "Imagem Docker construída com sucesso!"

# --- 4. Rodar o novo container ---
echo "Iniciando o novo container '$CONTAINER_NAME'..."
sudo docker run -d \
  -p "$HOST_PORT":"$CONTAINER_PORT" \
  -v "$HOST_DOWNLOAD_PATH":"$CONTAINER_DOWNLOAD_PATH" \
  --name "$CONTAINER_NAME" \
  "$IMAGE_NAME"

# Verifica se o container foi iniciado com sucesso
if [ $? -ne 0 ]; then
    echo "Erro: Falha ao iniciar o container Docker. Verifique as mensagens acima."
    exit 1
fi

echo "Container '$CONTAINER_NAME' iniciado com sucesso!"
echo "Você pode acessar a aplicação em: http://<IP_DO_SEU_SERVIDOR>:$HOST_PORT"
echo "Para ver os logs do container: sudo docker logs -f $CONTAINER_NAME"

echo "--- Processo de deploy concluído ---"

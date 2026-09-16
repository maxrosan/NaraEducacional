#!/usr/bin/env bash
# Teste da API do gravador NARA usando apenas `curl` — sem instalar nada.
#
# USO:
#   ./testar_gravador.sh parear   http://localhost:8001 RHFF89 AA:BB:CC:11:22:33
#   ./testar_gravador.sh enviar   http://localhost:8001 gravacao.wav
#   ./testar_gravador.sh feedback http://localhost:8001 <upload_id>
#   ./testar_gravador.sh status   http://localhost:8001
#
# O token é gravado em token.txt ao lado do script.
#
# No Windows: use o Git Bash, o WSL, ou copie os comandos `curl` avulsos —
# o curl já vem no Windows 10+ (no PowerShell, use `curl.exe`).

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARQUIVO_TOKEN="$DIR/token.txt"
COMANDO="${1:-}"
URL="${2:-http://localhost:8001}"

uuid() {
  # UUID v4 sem depender de uuidgen (usa /proc no Linux, senão python3)
  if [ -r /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid
  else
    python3 -c "import uuid; print(uuid.uuid4())"
  fi
}

case "$COMANDO" in

  parear)
    CODIGO="${3:?informe o código de pareamento}"
    DEVICE_ID="${4:?informe o device_id}"
    echo "--- PAREAMENTO ---"
    RESPOSTA=$(curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL/api/dispositivos/parear/" \
      -H "Content-Type: application/json" \
      -d "{\"codigo\":\"$CODIGO\",\"device_id\":\"$DEVICE_ID\",\"nome\":\"Gravador de testes\"}")
    echo "$RESPOSTA"
    # extrai o token sem jq (corta o campo "token":"...")
    TOKEN=$(printf '%s' "$RESPOSTA" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
    if [ -n "$TOKEN" ]; then
      printf '%s' "$TOKEN" > "$ARQUIVO_TOKEN"
      echo "Token salvo em $ARQUIVO_TOKEN"
    else
      echo "Não veio token — confira o código (expira em 10 min e é de uso único)."
      exit 1
    fi
    ;;

  enviar)
    ARQUIVO="${3:?informe o caminho do .wav}"
    TOKEN=$(cat "$ARQUIVO_TOKEN")
    UPLOAD_ID=$(uuid)
    # sha256 é opcional; se o sha256sum não existir, o campo é simplesmente omitido
    SHA=$(sha256sum "$ARQUIVO" 2>/dev/null | cut -d' ' -f1 || true)

    echo "--- ENVIO (upload_id=$UPLOAD_ID) ---"
    curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL/api/dispositivos/audio/" \
      -H "Authorization: Bearer $TOKEN" \
      -F "arquivo=@$ARQUIVO;type=audio/wav" \
      -F "upload_id=$UPLOAD_ID" \
      ${SHA:+-F "sha256=$SHA"}

    echo
    echo "--- RETRY com o MESMO upload_id (deve responder duplicado=true) ---"
    curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL/api/dispositivos/audio/" \
      -H "Authorization: Bearer $TOKEN" \
      -F "arquivo=@$ARQUIVO;type=audio/wav" \
      -F "upload_id=$UPLOAD_ID"

    echo
    echo "--- FEEDBACK (turma reconhecida? criança registrada?) ---"
    echo "O 'recebido' acima só confirma que o arquivo chegou. A turma e a"
    echo "criança só existem depois da transcrição, então consultamos até o"
    echo "sinal sair de 'aguardando'."
    for _ in $(seq 1 20); do
      sleep 3
      RESP=$(curl -s "$URL/api/dispositivos/audio/$UPLOAD_ID/" -H "Authorization: Bearer $TOKEN")
      SINAL=$(printf '%s' "$RESP" | sed -n 's/.*"sinal":"\([^"]*\)".*/\1/p')
      echo "  sinal=$SINAL"
      [ "$SINAL" != "aguardando" ] && break
    done
    echo "$RESP"
    ;;

  feedback)
    UPLOAD_ID="${3:?informe o upload_id}"
    TOKEN=$(cat "$ARQUIVO_TOKEN")
    curl -s -w "\nHTTP %{http_code}\n" "$URL/api/dispositivos/audio/$UPLOAD_ID/" \
      -H "Authorization: Bearer $TOKEN"
    ;;

  status)
    TOKEN=$(cat "$ARQUIVO_TOKEN")
    echo "--- STATUS ---"
    curl -s -w "\nHTTP %{http_code}\n" "$URL/api/dispositivos/status/" \
      -H "Authorization: Bearer $TOKEN"
    ;;

  *)
    echo "Comandos: parear | enviar | feedback | status"
    echo "Ex.: $0 parear http://localhost:8001 RHFF89 AA:BB:CC:11:22:33"
    exit 1
    ;;
esac

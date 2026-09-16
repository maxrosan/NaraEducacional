#!/usr/bin/env python3
"""
Teste ponta a ponta da API do gravador NARA — SEM dependências externas.

Usa apenas a biblioteca padrão do Python 3 (urllib, wave, uuid, hashlib), de
propósito: o objetivo é mostrar exatamente quais bytes vão na requisição, para
servir de referência ao firmware (que montará o mesmo multipart em C).

USO
---
1) Peça um código de pareamento na plataforma
   (admin → Cadastros → Dispositivos → "Gerar código de pareamento").

2) Pareie o dispositivo (só na primeira vez ou ao trocar de professora):

   python testar_gravador.py parear --url http://localhost:8001 \
       --codigo RHFF89 --device-id AA:BB:CC:11:22:33 --nome "Gravador de testes"

   O token devolvido é gravado em `token.txt` ao lado deste script.

3) Envie um áudio de teste (gera um WAV de 3s se você não passar um arquivo).
   Depois do envio o script CONSULTA O DESFECHO até o servidor terminar — é o
   retorno que o aparelho dá à professora por LED/bipe:

   python testar_gravador.py enviar --url http://localhost:8001
   python testar_gravador.py enviar --url http://localhost:8001 --arquivo gravacao.wav

3b) Consultar o desfecho de uma gravação antiga:

   python testar_gravador.py feedback --url http://localhost:8001 --upload-id <uuid>

4) Confira o vínculo atual do dispositivo:

   python testar_gravador.py status --url http://localhost:8001

5) Rode a bateria completa (pareia, envia, testa retry e erros):

   python testar_gravador.py tudo --url http://localhost:8001 --codigo RHFF89
"""

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave

ARQUIVO_TOKEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")


# ---------------------------------------------------------------------------
# HTTP (só stdlib)
# ---------------------------------------------------------------------------

def _requisicao(url, metodo="GET", corpo=None, headers=None):
    """Faz a requisição e devolve (status, dict_json). Nunca levanta em erro HTTP."""
    req = urllib.request.Request(url, data=corpo, method=metodo)
    for chave, valor in (headers or {}).items():
        req.add_header(chave, valor)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(texto or "{}")
        except json.JSONDecodeError:
            return e.code, {"error": texto[:300]}
    except urllib.error.URLError as e:
        print(f"ERRO de rede: {e.reason}")
        sys.exit(1)


def post_json(url, dados):
    corpo = json.dumps(dados).encode("utf-8")
    return _requisicao(url, "POST", corpo, {"Content-Type": "application/json"})


def post_multipart(url, token, campos, arquivo_nome, arquivo_bytes):
    """Monta um multipart/form-data na mão — é o mesmo formato que o firmware
    precisa produzir. Cada parte é:

        --BOUNDARY CRLF
        Content-Disposition: form-data; name="campo" CRLF
        CRLF
        valor CRLF

    e a parte do arquivo leva também o Content-Type. O corpo termina com
    --BOUNDARY-- CRLF.
    """
    boundary = "----NaraGravadorBoundary" + uuid.uuid4().hex[:12]
    crlf = b"\r\n"
    partes = []

    for nome, valor in campos.items():
        if valor is None:
            continue
        partes.append(f"--{boundary}".encode())
        partes.append(f'Content-Disposition: form-data; name="{nome}"'.encode())
        partes.append(b"")
        partes.append(str(valor).encode())

    partes.append(f"--{boundary}".encode())
    partes.append(
        f'Content-Disposition: form-data; name="arquivo"; filename="{arquivo_nome}"'.encode()
    )
    partes.append(b"Content-Type: audio/wav")
    partes.append(b"")
    corpo = crlf.join(partes) + crlf + arquivo_bytes + crlf
    corpo += f"--{boundary}--".encode() + crlf

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(corpo)),
    }
    return _requisicao(url, "POST", corpo, headers)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def gerar_wav_teste(caminho, segundos=3, sample_rate=16000):
    """Gera um WAV PCM 16 bits mono 16 kHz com um bipe — o formato recomendado."""
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        quadros = bytearray()
        for i in range(sample_rate * segundos):
            amostra = int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            quadros += struct.pack("<h", amostra)
        w.writeframes(bytes(quadros))
    return caminho


def salvar_token(token):
    with open(ARQUIVO_TOKEN, "w", encoding="utf-8") as f:
        f.write(token)
    print(f"Token salvo em {ARQUIVO_TOKEN}")


def ler_token():
    if not os.path.exists(ARQUIVO_TOKEN):
        print("Token não encontrado. Rode o comando 'parear' primeiro.")
        sys.exit(1)
    with open(ARQUIVO_TOKEN, encoding="utf-8") as f:
        return f.read().strip()


def mostrar(titulo, status, dados):
    print(f"\n--- {titulo} ---")
    print(f"HTTP {status}")
    print(json.dumps(dados, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_parear(args):
    status, dados = post_json(
        f"{args.url}/api/dispositivos/parear/",
        {"codigo": args.codigo, "device_id": args.device_id, "nome": args.nome},
    )
    mostrar("PAREAMENTO", status, dados)
    if status == 201 and dados.get("token"):
        salvar_token(dados["token"])
        return dados["token"]
    print("\nFalhou. Códigos comuns: codigo_invalido (expirado/já usado), device_id_ausente.")
    sys.exit(1)


def cmd_status(args):
    token = args.token or ler_token()
    status, dados = _requisicao(
        f"{args.url}/api/dispositivos/status/",
        headers={"Authorization": f"Bearer {token}"},
    )
    mostrar("STATUS DO DISPOSITIVO", status, dados)


def cmd_feedback(args):
    """Consulta o desfecho de UMA gravação até sair de 'aguardando'.

    É esta chamada que diz à professora, via LED/bipe, se a turma foi
    reconhecida e se a criança entrou no relato — o aparelho não tem tela e
    turma/criança só são conhecidas depois da transcrição, que é assíncrona.
    """
    token = args.token or ler_token()
    upload_id = args.upload_id

    for tentativa in range(1, args.tentativas + 1):
        status, dados = _requisicao(
            f"{args.url}/api/dispositivos/audio/{upload_id}/",
            headers={"Authorization": f"Bearer {token}"},
        )
        sinal = (dados.get("feedback") or {}).get("sinal")
        if status != 200 or sinal != "aguardando":
            mostrar("FEEDBACK DA GRAVAÇÃO", status, dados)
            _explicar_sinal(dados)
            return dados
        print(f"  ... ainda processando (tentativa {tentativa}/{args.tentativas})")
        time.sleep(args.espera)

    print("\nO servidor ainda não terminou. Consulte de novo mais tarde:")
    print(f"  python {os.path.basename(__file__)} feedback --upload-id {upload_id}")
    return None


def _explicar_sinal(dados):
    """Traduz o feedback para o que o firmware deve fazer."""
    feedback = dados.get("feedback") or {}
    acoes = {
        "ok": "LED VERDE  — gravação registrada.",
        "atencao": "LED AMARELO — entrou, mas incompleto (ver mensagem).",
        "erro": "LED VERMELHO — nada foi registrado.",
        "aguardando": "Ainda processando; consultar de novo.",
    }
    print(f"\n>> {acoes.get(feedback.get('sinal'), 'sinal desconhecido')}")
    print(f">> Mensagem: {feedback.get('mensagem', '')}")


def cmd_enviar(args):
    token = args.token or ler_token()

    caminho = args.arquivo
    if not caminho:
        caminho = os.path.join(os.path.dirname(ARQUIVO_TOKEN), "teste.wav")
        gerar_wav_teste(caminho)
        print(f"WAV de teste gerado: {caminho}")

    with open(caminho, "rb") as f:
        conteudo = f.read()

    upload_id = args.upload_id or str(uuid.uuid4())
    sha256 = hashlib.sha256(conteudo).hexdigest()

    print(f"\nEnviando {len(conteudo)} bytes | upload_id={upload_id}")
    status, dados = post_multipart(
        f"{args.url}/api/dispositivos/audio/",
        token,
        {"upload_id": upload_id, "sha256": sha256, "duracao_seg": args.duracao},
        os.path.basename(caminho),
        conteudo,
    )
    mostrar("ENVIO DE ÁUDIO", status, dados)

    if status in (200, 201) and not args.sem_feedback:
        print("\nAguardando o processamento para dar retorno à professora...")
        args.token, args.upload_id = token, upload_id
        cmd_feedback(args)

    return upload_id, conteudo


def cmd_tudo(args):
    print("=" * 60)
    print("BATERIA COMPLETA DE TESTES")
    print("=" * 60)

    token = cmd_parear(args)
    args.token = token

    cmd_status(args)

    # 1. envio normal
    upload_id, conteudo = cmd_enviar(args)

    # 2. retry com o MESMO upload_id → deve responder 200 e duplicado=true
    print("\n>>> Repetindo o envio com o mesmo upload_id (simula retry por timeout)")
    args.upload_id = upload_id
    status, dados = post_multipart(
        f"{args.url}/api/dispositivos/audio/",
        token,
        {"upload_id": upload_id, "sha256": hashlib.sha256(conteudo).hexdigest()},
        "teste.wav",
        conteudo,
    )
    mostrar("RETRY (idempotência)", status, dados)
    if dados.get("duplicado") is True:
        print("OK: o servidor reconheceu o retry e NÃO duplicou o registro.")
    else:
        print("ATENÇÃO: esperava duplicado=true nesta chamada.")

    # 3. erros previstos
    print("\n>>> Testes de erro (respostas esperadas)")
    status, dados = post_multipart(
        f"{args.url}/api/dispositivos/audio/", token,
        {"upload_id": str(uuid.uuid4())}, "x.wav", b"isto nao e um wav valido" * 3,
    )
    mostrar("WAV inválido (espera 400 wav_invalido)", status, dados)

    status, dados = post_multipart(
        f"{args.url}/api/dispositivos/audio/", "token-invalido.abc",
        {"upload_id": str(uuid.uuid4())}, "x.wav", conteudo,
    )
    mostrar("Token inválido (espera 401 token_invalido)", status, dados)

    status, dados = post_multipart(
        f"{args.url}/api/dispositivos/audio/", token,
        {"upload_id": "nao-e-uuid"}, "x.wav", conteudo,
    )
    mostrar("upload_id inválido (espera 400 upload_id_invalido)", status, dados)

    print("\n" + "=" * 60)
    print("FIM DA BATERIA")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Testes da API do gravador NARA")
    parser.add_argument("--url", default="http://localhost:8001", help="Base da API")
    parser.add_argument("--token", help="Token do dispositivo (default: token.txt)")

    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("parear", help="Troca o código de pareamento por um token")
    p.add_argument("--codigo", required=True)
    p.add_argument("--device-id", required=True)
    p.add_argument("--nome", default="Gravador de testes")
    p.set_defaults(func=cmd_parear)

    p = sub.add_parser("enviar", help="Envia um WAV e aguarda o feedback")
    p.add_argument("--arquivo", help="WAV a enviar (default: gera um de teste)")
    p.add_argument("--upload-id", help="UUID (default: gera um novo)")
    p.add_argument("--duracao", type=int, help="Duração em segundos (opcional)")
    p.add_argument("--sem-feedback", action="store_true",
                   help="Não consulta o desfecho depois de enviar")
    p.add_argument("--tentativas", type=int, default=20)
    p.add_argument("--espera", type=int, default=3, help="Segundos entre consultas")
    p.set_defaults(func=cmd_enviar)

    p = sub.add_parser("feedback", help="Consulta o desfecho de uma gravação")
    p.add_argument("--upload-id", required=True)
    p.add_argument("--tentativas", type=int, default=20)
    p.add_argument("--espera", type=int, default=3)
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("status", help="Consulta o vínculo do dispositivo")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("tudo", help="Pareia, envia, testa retry e erros")
    p.add_argument("--codigo", required=True)
    p.add_argument("--device-id", default="AA:BB:CC:11:22:33")
    p.add_argument("--nome", default="Gravador de testes")
    p.add_argument("--arquivo")
    p.add_argument("--upload-id")
    p.add_argument("--duracao", type=int)
    p.add_argument("--sem-feedback", action="store_true")
    p.add_argument("--tentativas", type=int, default=20)
    p.add_argument("--espera", type=int, default=3)
    p.set_defaults(func=cmd_tudo)

    args = parser.parse_args()
    args.url = args.url.rstrip("/")
    args.func(args)


if __name__ == "__main__":
    main()

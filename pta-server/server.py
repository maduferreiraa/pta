#!/usr/bin/env python3
"""
Servidor do Protocolo de Transferência de Arquivos (PTA).

Uso:
    python3 server.py [porta]

- Porta padrão: 11550 (TCP).
- Usuários válidos: lidos de users.txt (um por linha), no mesmo diretório deste script.
- Arquivos servidos: diretório files/, no mesmo diretório deste script.

Formato das mensagens (campos separados por um único espaço, sem terminador):
    pedido:   SEQ_NUM COMMAND [ARGS]
    resposta: SEQ_NUM REPLY [ARGS]

Máquina de estados (por conexão):
    ESPERANDO --CUMP <nome> válido--> PRONTO
    ESPERANDO --qualquer outro caso--> NOK + fecha conexão
    PRONTO    --LIST-->  ARQS <num> a1,a2,...  (ou NOK)
    PRONTO    --PEGA <nome>--> ARQ <tam> <bytes>  (ou NOK se não existir)
    PRONTO    --TERM-->  OK + fecha conexão
    PRONTO    --qualquer outro caso--> NOK (conexão permanece aberta)
"""

import os
import socket
import sys
import threading

HOST = "0.0.0.0"
DEFAULT_PORT = 11550
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
FILES_DIR = os.path.join(BASE_DIR, "files")
RECV_SIZE = 4096

ESPERANDO = "ESPERANDO"
PRONTO = "PRONTO"


def load_users():
    """Lê a lista de usuários válidos (sensível a maiúsculas/minúsculas)."""
    users = set()
    try:
        with open(USERS_FILE, "r", encoding="ascii", errors="ignore") as f:
            for line in f:
                name = line.strip()
                if name:
                    users.add(name)
    except OSError as e:
        print("Aviso: não foi possível ler %s: %s" % (USERS_FILE, e), file=sys.stderr)
    return users


def list_files():
    """Nomes dos arquivos regulares em files/, ou None em caso de erro."""
    try:
        names = [
            n for n in os.listdir(FILES_DIR)
            if os.path.isfile(os.path.join(FILES_DIR, n))
        ]
    except OSError:
        return None
    return sorted(names)


def read_file(name):
    """Conteúdo (bytes) do arquivo pedido, ou None se não existir/inválido."""
    # Impede path traversal: só nomes simples dentro de files/.
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        return None
    path = os.path.join(FILES_DIR, name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def parse(raw):
    """
    Interpreta uma mensagem de pedido.
    Retorna (seq_str, command, args_list, formato_ok).
    seq_str é sempre uma string para ser ecoada na resposta.
    """
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return "0", None, [], False
    text = text.strip("\r\n")
    # Um espaço separa os campos; tokens vazios (espaços duplicados) violam o formato.
    parts = text.split(" ")
    seq = parts[0] if parts and parts[0].lstrip("-").isdigit() else None
    echo = seq if seq is not None else "0"
    if seq is None or len(parts) < 2 or any(p == "" for p in parts):
        return echo, None, [], False
    return echo, parts[1], parts[2:], True


def handle_client(conn, addr, users):
    state = ESPERANDO
    pending = b""
    try:
        while True:
            data = conn.recv(RECV_SIZE)
            if not data:
                break  # cliente fechou a conexão

            # Cada recv() é uma mensagem; se vierem várias linhas juntas
            # (cliente que usa '\n' como terminador), trata uma a uma.
            chunk = pending + data
            pending = b""
            if b"\n" in chunk:
                messages = [m for m in chunk.split(b"\n") if m.strip(b"\r")]
            else:
                messages = [chunk]

            for raw in messages:
                seq, cmd, args, ok = parse(raw)

                def reply(body):
                    conn.sendall(("%s %s" % (seq, body)).encode("ascii"))

                if state == ESPERANDO:
                    # Só CUMP <nome> com usuário válido é aceito.
                    if ok and cmd == "CUMP" and len(args) == 1 and args[0] in users:
                        reply("OK")
                        state = PRONTO
                        continue
                    reply("NOK")
                    return  # fecha a conexão TCP

                # state == PRONTO
                if not ok:
                    reply("NOK")
                elif cmd == "LIST" and len(args) == 0:
                    names = list_files()
                    if names is None:
                        reply("NOK")
                    else:
                        reply("ARQS %d %s" % (len(names), ",".join(names)))
                elif cmd == "PEGA" and len(args) >= 1:
                    # O PTA só permite um arquivo por vez: pedidos extras são ignorados.
                    content = read_file(args[0])
                    if content is None:
                        reply("NOK")
                    else:
                        header = ("%s ARQ %d " % (seq, len(content))).encode("ascii")
                        conn.sendall(header + content)
                elif cmd == "TERM" and len(args) == 0:
                    reply("OK")
                    return  # fecha a conexão TCP
                else:
                    reply("NOK")  # comando desconhecido/mal formado; conexão segue aberta
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    users = load_users()
    print("PTA: %d usuário(s) carregado(s); servindo %s" % (len(users), FILES_DIR))

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, port))
    srv.listen(16)
    print("PTA: ouvindo na porta %d (Ctrl+C para encerrar)" % port)

    try:
        while True:
            conn, addr = srv.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, users), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\nPTA: encerrando.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()

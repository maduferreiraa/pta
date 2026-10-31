# Servidor PTA (Protocolo de Transferência de Arquivos)

Implementação do servidor descrito em `pta.pdf`.

## Requisitos

- Python 3.6 ou superior
- Nenhuma biblioteca externa (apenas a biblioteca padrão: `socket`, `threading`, `os`, `sys`)

## Como executar

A partir da raiz do repositório:

```bash
python3 pta-server/server.py          # porta padrão 11550
python3 pta-server/server.py 11550    # porta explícita (opcional)
```

O servidor lê `users.txt` (um usuário por linha) e serve os arquivos do diretório `files/`,
ambos ao lado de `server.py`, independente do diretório de onde o comando é executado.

## Como testar

Com o servidor rodando, em outro terminal:

```bash
python3 pta-client.py 127.0.0.1 11550 <usuario-presente-em-users.txt>
```

## Comportamento implementado

| Estado      | Mensagem                | Resposta                                   | Conexão  |
|-------------|-------------------------|--------------------------------------------|----------|
| Esperando   | `CUMP <nome>` válido    | `SEQ OK`                                   | aberta   |
| Esperando   | `CUMP` com usuário inválido, ou qualquer outra coisa | `SEQ NOK`     | fechada  |
| Pronto      | `LIST`                  | `SEQ ARQS <num> a1,a2,...` (ou `NOK`)      | aberta   |
| Pronto      | `PEGA <nome>` existente | `SEQ ARQ <tam> <bytes>`                    | aberta   |
| Pronto      | `PEGA <nome>` inexistente | `SEQ NOK`                                | aberta   |
| Pronto      | `TERM`                  | `SEQ OK`                                   | fechada  |
| Pronto      | qualquer outra coisa (inclusive novo `CUMP`) | `SEQ NOK`             | aberta   |

Decisões de implementação:

- O `SEQ_NUM` da resposta é sempre o do pedido correspondente. Se o pedido não tiver um
  número válido, a resposta usa `0`.
- Os nomes de usuário são comparados diferenciando maiúsculas de minúsculas.
- Mensagens fora do formato `SEQ COMMAND [ARGS]` (campos vazios, não-ASCII, número
  de sequência não numérico, argumentos a mais em `LIST`/`TERM`) recebem `NOK`.
- `PEGA` com mais de um nome: apenas o primeiro é atendido, os demais são ignorados
  (o PTA só permite um arquivo por vez).
- Nomes com `/`, `\` ou `..` são rejeitados com `NOK` (proteção contra path traversal).
- Arquivos são enviados em bytes (binário), com o tamanho exato no cabeçalho.
- As mensagens não possuem terminador; cada `recv()` é tratado como uma mensagem. Se o
  cliente enviar `\n` como terminador, as linhas também são tratadas corretamente.
- Cada conexão é atendida em uma thread própria; dentro de uma conexão as operações são
  sequenciais, portanto atômicas.

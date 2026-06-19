# brother-embroidery-connect

Sistema de **conexão e automação em rede para bordadeiras Brother** (linha
Innov-is / WLAN — testado na **BP1530L**). Monitora, envia e gerencia bordados
pela rede, **sem o app Artspira, sem o programa Design Database Transfer e sem
nuvem**.

Inclui:

- **Painel web** local para monitorar e enviar bordados (`server.py`).
- **API REST** genérica para integrar com qualquer sistema (PHP, Node, Python…).
- **CLI** para automação/scripts (`send_cli.py`).
- **Biblioteca** Python do protocolo (`brother_machine.py`).
- Documentação do protocolo descoberto por engenharia reversa (`PROTOCOL.md`).

Só precisa de **Python 3** (biblioteca padrão, nada para instalar).

> ⚠️ Projeto não-oficial, sem vínculo com a Brother. Sem garantia. Use na sua
> própria máquina, por sua conta e risco.

## Requisitos

- A bordadeira ligada e na **mesma rede** que o computador.
- Saber o **IP da máquina** (padrão deste projeto: `192.168.1.120`).

## Início rápido

### Painel web
```bash
python3 server.py            # abre http://localhost:8765 no navegador
python3 server.py --ip 192.168.1.130 --port 8765
```

No painel você vê os dados da máquina, o espaço livre, os arquivos já na
memória e pode arrastar vários `.pes` para enviar em fila.

### Linha de comando
```bash
python3 send_cli.py --info               # mostra status e arquivos
python3 send_cli.py desenho.pes          # envia um bordado
python3 send_cli.py desenho.pes --name PEDIDO123.pes
```

## API REST (para o seu sistema)

Suba o servidor (`python3 server.py`) e chame de qualquer linguagem:

| Método | Rota | Descrição |
|-------|------|-----------|
| GET | `/api/machines` | Lista as máquinas configuradas (`machines.json`) |
| GET | `/api/status?ip=...` | Dados da máquina + espaço + lista de arquivos |
| GET | `/api/catalog` | Lista os bordados da pasta local `designs/` |
| GET | `/api/history` | Histórico de envios |
| POST | `/api/send?ip=...&name=ARQ.pes` | Envia um arquivo (corpo = bytes). Converte p/ PES se preciso, checa espaço, registra histórico |
| POST | `/api/send_catalog?ip=...&file=NOME` | Envia um item do catálogo |

### Exemplos

**curl**
```bash
curl --data-binary @desenho.pes \
  "http://localhost:8765/api/send?name=PEDIDO123.pes"
```

**PHP**
```php
$pes = file_get_contents('desenho.pes');
$ch = curl_init('http://localhost:8765/api/send?name=PEDIDO123.pes');
curl_setopt_array($ch, [CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>$pes,
  CURLOPT_RETURNTRANSFER=>true, CURLOPT_HTTPHEADER=>['Content-Type: application/octet-stream']]);
echo curl_exec($ch);
```

**Node.js**
```js
import { readFileSync } from 'fs';
await fetch('http://localhost:8765/api/send?name=PEDIDO123.pes', {
  method: 'POST', headers: { 'Content-Type': 'application/octet-stream' },
  body: readFileSync('desenho.pes')
}).then(r => r.json()).then(console.log);
```

**Python**
```python
import requests
requests.post("http://localhost:8765/api/send",
              params={"name": "PEDIDO123.pes"},
              data=open("desenho.pes", "rb").read())
```

## Como funciona

A máquina expõe um servidor HTTPS local com a API `pedxml`. O envio é um
`POST multipart` para `/sewing/sewing.cgi`. Detalhes completos em
[`PROTOCOL.md`](PROTOCOL.md).

## Arquivos

| Arquivo | Função |
|--------|--------|
| `brother_machine.py` | Biblioteca do protocolo (info / status / send) |
| `convert.py` | Conversão de formatos para PES (pyembroidery) |
| `render.py` | Ficha técnica + imagem (SVG) do bordado |
| `server.py` | Painel web + API REST (multi-máquina, catálogo, histórico) |
| `send_cli.py` | Envio por linha de comando |
| `machines.json` | Lista de máquinas (criado na 1ª execução) |
| `designs/` | Pasta do catálogo de bordados |
| `PROTOCOL.md` | Documentação do protocolo |

## Recursos (v2)

- **Multi-máquina** — configure várias bordadeiras em `machines.json`.
- **Catálogo** — coloque arquivos na pasta `designs/` e envie pelo painel.
- **Conversão automática** — DST/EXP/JEF/VP3/XXX → PES (requer `pip3 install pyembroidery`).
- **Checagem de espaço** — recusa o envio se não couber na memória ou passar do limite.
- **Histórico** — registro de tudo que foi enviado (`history.json`).
- **Nomes padronizados** — o nome é higienizado e recebe extensão `.pes`.
- **Ficha + imagem do bordado** — desenha a prévia a partir dos pontos do
  arquivo (não é câmera) e mostra total de pontos, cores, tamanho e tempo
  estimado. Endpoints `/api/analyze` (POST bytes) e `/api/analyze_catalog?file=`.
- **Acompanhamento estimado** — barra de progresso por tempo (total de pontos ×
  velocidade), já que a máquina não envia o progresso real.

## Limitações / próximos passos

- **Enviar**, **listar** e **monitorar espaço** funcionam.
- **Apagar / renomear na máquina** ainda não foi mapeado. O endpoint existe
  (`/api/delete`, `/api/rename`) mas responde "não implementado": falta uma
  **captura** do software oficial fazendo essas ações para descobrir o formato.
  (Obs.: a própria máquina renomeia os arquivos com números sequenciais ao
  recebê-los, então "renomear na máquina" pode não existir do lado dela.)
- **Tempo real (câmera / progresso da costura)**: **não disponível neste modelo**.
  O `/info` reporta as APIs `monitoring`, `camera` e `streaming` em `version: 0`
  (desligadas), e todos os endpoints correspondentes retornam 404. Esses recursos
  são exclusivos das máquinas premium da Brother (ex.: Luminaire/Stellaire), que
  têm câmera embutida e essas APIs ativas. Não é uma trava destravável — o
  recurso não existe no hardware/firmware da BP1530L.
- Testado na **BP1530L** (firmware 1.73). Outros modelos WLAN da Brother usam o
  mesmo padrão, mas podem variar.

## Licença

MIT — veja [`LICENSE`](LICENSE).

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
- **Gerador de letreiros** (`/letreiro` no painel, ou `lettering.py`): digita o
  nome, escolhe fonte/cor/tamanho e já sai o `.pes` pronto para bordar.

Só precisa de **Python 3** (biblioteca padrão, nada para instalar). O gerador de
letreiros é opcional e usa algumas bibliotecas extras (`requirements-letreiro.txt`).

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

## Gerador de letreiros (nomes, datas, frases)

Abra o painel e clique em **✍️ Gerador de letreiros** (ou vá direto em
`http://localhost:8765/letreiro`). Precisa das bibliotecas extras uma vez:

```bash
pip3 install -r requirements-letreiro.txt
```

Na tela você escolhe:

- **Texto** — Enter quebra a linha (ex.: nome em cima, sobrenome embaixo).
- **Fonte** — 9 opções (Great Vibes, Parisienne, Allura, Alex Brush, Dancing
  Script, Cookie, Pacifico, Playfair Itálico, Quicksand).
- **Tamanho** — largura e/ou altura máxima em mm; o desenho cresce até o
  primeiro limite, sem deformar.
- **Esticar** na horizontal / vertical, **espaço entre letras** e **entre linhas**.
- **Cor da linha** e **preenchimento** (mais aberto / normal / mais fechado).

E depois: **Baixar .pes**, **Salvar no catálogo** ou **Enviar direto para a máquina**.

Como o arquivo é montado (automático):

- **Base + ponto cheio**: cada traço recebe uma base (caminhada e, nos traços
  largos, zigue-zague aberto) e por cima o ponto cheio.
- **Densidade em milímetros**: ao mudar tamanho ou esticar, os pontos são
  recalculados — o espaçamento entre pontos continua o mesmo.
- **Letras grossas/grandes** viram **preenchimento** (tatami com base cruzada),
  que fica melhor que ponto cheio largo demais.
- **Costura da esquerda para a direita**, linha por linha: cada traço termina
  na ponta oposta e o próximo começa ali; pingos e acentos entram quando a
  agulha passa por eles. Corte de linha só quando precisa pular para uma letra
  solta, sempre com arremate antes e depois.
- **Origem no canto (0,0)** e cortes na posição da agulha — a máquina mostra e
  borda o desenho inteiro, no lugar certo.

Pela linha de comando:

```bash
python3 lettering.py "Felipe" --fonte great_vibes --largura 80 --saida felipe.pes
python3 lettering.py "João\nFrederico" --fonte parisienne --largura 90 --altura 50
python3 lettering.py "07/11/2026" --fonte dancing --largura 60 --esticar-v 120 --cor "#d4a017"
python3 lettering.py --fontes        # lista as fontes
python3 test_lettering.py            # testes rápidos
```

As fontes ficam em `fonts/` (licença SIL Open Font License, em `fonts/licencas/`).

## Arquivos

| Arquivo | Função |
|--------|--------|
| `brother_machine.py` | Biblioteca do protocolo (info / status / send) |
| `convert.py` | Conversão de formatos para PES (pyembroidery) |
| `render.py` | Ficha técnica + imagem (SVG) do bordado |
| `server.py` | Painel web + API REST (multi-máquina, catálogo, histórico) |
| `send_cli.py` | Envio por linha de comando |
| `lettering.py` | Gerador de letreiros (texto → `.pes`) |
| `lettering_page.py` | Tela do gerador de letreiros (`/letreiro`) |
| `test_lettering.py` | Testes rápidos do gerador |
| `fonts/` | Fontes do gerador (+ licenças OFL) |
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

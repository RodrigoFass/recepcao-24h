# Recepção 24h — protótipo

Protótipo do trabalho de Gestão de Micro e Pequenas Empresas (Sistemas de Informação, UVV).

A **Recepção 24h** é uma plataforma para hotéis e pousadas pequenos (5 a 20 unidades) que vendem por vários canais.
Ela atende hóspedes automaticamente 24 horas, só com as informações daquele hotel, e passa para a equipe o que
exige uma pessoa; conduz a chegada com mensagens agendadas; unifica o calendário dos canais; pede avaliação depois
da estadia; e mostra ocupação, ADR, RevPAR e receita líquida por canal. **A mesma plataforma atende vários hotéis,
com os dados totalmente separados.**

> **Os hotéis da demo são fictícios** (Pousada Maré Alta e Chalés Serra Verde). Nomes, endereços, telefones,
> links, hóspedes e reservas são inventados.

O protótipo roda localmente e **simula** o WhatsApp e as OTAs (Airbnb, Booking). Na produção, descrita no trabalho
escrito, o orquestrador seria o n8n com a WhatsApp Cloud API. Tudo funciona **offline, em modo demo**; a API da
Anthropic é opcional.

---

## Instalação

Requisitos: Python 3.11 ou mais novo.

### Online, sem instalar nada (Render, gratuito)

1. Entre em <https://render.com> com a conta do GitHub.
2. **New → Blueprint** e escolha este repositório (o `render.yaml` já diz como subir o site).
3. Quando pedir `GEMINI_API_KEY`, cole a chave gratuita do Gemini e confirme. A primeira subida leva alguns minutos.
4. O Render mostra o endereço (algo como `https://recepcao-24h.onrender.com`).

No plano gratuito o site "dorme" depois de 15 minutos sem acesso e leva ~1 minuto para acordar: **abra o endereço uns
2 minutos antes de apresentar**. Cada vez que acorda, os dados de exemplo são recriados com a data do dia.

Reserva: **GitHub Codespaces** (no repositório: Code → Codespaces → Create). O `.devcontainer/` instala tudo, recria
os dados e abre o site; a chave do Gemini vai em Settings → Codespaces → Secrets como `GEMINI_API_KEY`.

### Windows: duplo clique

Dê duplo clique em **`Abrir Recepcao 24h.cmd`** (na pasta do projeto). Na primeira vez ele prepara o ambiente; depois
atualiza os dados com a data de hoje, liga o site e abre o navegador em <http://127.0.0.1:8000>. Para desligar, feche a
janela preta. Precisa do Python instalado e, para a IA, de internet e da chave no `.env`.

### Windows (PowerShell)

```powershell
cd "caminho\da\pasta\do\projeto"
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
python -m uvicorn app.main:app --reload
```

Se o PowerShell bloquear o `Activate.ps1`, rode antes `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
(vale só para aquela janela) — ou use direto `.venv\Scripts\python.exe` no lugar de `python`.

### Linux / macOS

```bash
cd caminho/da/pasta/do/projeto
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
python -m uvicorn app.main:app --reload
```

Depois, abra <http://localhost:8000>.

### Dados de exemplo

`python seed.py` apaga e recria o banco (`data/recepcao24h.db`). **"Hoje" é a data em que o seed roda: rode
`python seed.py` no dia da apresentação** para as datas ficarem atuais. O seed cria:

- 2 hotéis com base de conhecimento de 16 itens cada e o acesso da equipe de cada um;
- a conta da administração (a empresa da Recepção 24h), que cadastra os hotéis;
- reservas dos últimos 90 dias (ocupação ~55% na Maré e ~45% na Serra, com sexta e sábado mais cheios) e ~15 nos
  próximos 30 dias, com chegadas hoje e amanhã nos dois hotéis;
- o **próximo fim de semana lotado na Serra Verde** (para o teste de indisponibilidade);
- algumas reservas futuras de OTA sem valor (pendência), ~10 conversas antigas e ~20 avaliações por hotel;
- `data/exemplo.ics`: um bloqueio de 3 noites na suíte 101 da Maré Alta que **sobrepõe** uma reserva futura (para
  mostrar o alerta de conflito).

### Acessos (senhas de teste, todas fictícias)

| Conta | Usuário | Senha | Vê |
|---|---|---|---|
| Pousada Maré Alta | `marealta` | `mare1234` | só a Maré Alta: equipe, reservas e painel |
| Chalés Serra Verde | `serraverde` | `serra1234` | só a Serra Verde |
| Administração | `admin` | `admin1234` | a lista de hotéis clientes; cadastra hotéis novos |

O atendimento do hóspede (`/chat?hotel=<hotel>`) é público: é o lado do hóspede, que na versão final chega pelo
WhatsApp do hotel. A tela inicial tem um atalho para cada hotel.

### IA sem custo (Gemini)

1. Entre em <https://aistudio.google.com/apikey> com uma conta Google e crie uma chave (gratuita; não precisa de
   cartão nem de assinatura).
2. Abra o arquivo `.env` na raiz do projeto e cole a chave depois de `GEMINI_API_KEY=`.
3. Reinicie o servidor. O chat passa a ser respondido pela IA, com as mesmas regras e ferramentas.

No plano gratuito há limite de requisições por minuto e por dia, e o Google pode usar as conversas para melhorar os
produtos dele (os dados da demo são fictícios). Se a IA falhar (sem internet ou limite atingido), o bot responde
pelas regras, sem mostrar erro ao hóspede.

### Variáveis de ambiente (todas opcionais; podem ir no `.env`)

| Variável | Para quê | Padrão |
|---|---|---|
| `GEMINI_API_KEY` | Liga o modo IA com o Gemini (plano gratuito) | sem chave = modo demo |
| `GEMINI_MODEL` | Modelo do Gemini | `gemini-3.5-flash-lite` |
| `ANTHROPIC_API_KEY` | Liga o modo IA com o Claude (pago); se as duas chaves existirem, usa o Gemini | sem chave = modo demo |
| `MODEL` | Modelo do Claude | `claude-haiku-4-5-20251001` |
| `DEMO_MODE` | `1` força o modo demo mesmo com chave | desligado |
| `DATABASE_URL` | Outro arquivo SQLite | `sqlite:///data/recepcao24h.db` |

---

## Roteiro da demo (2 minutos)

Antes: `python seed.py` e suba o servidor.

1. **Atendimento da Maré Alta** (tela inicial → Pousada Maré Alta): "aceita pet?" → sim, até 10 kg, R$ 50. No da
   **Serra Verde**, a mesma pergunta → não aceita. Mesma plataforma, respostas diferentes.
2. **"Tem vaga de [sexta] a [domingo]?"** (datas de ~2 semanas à frente, no formato dd/mm) → tipos livres e tarifa
   base × noites, sem desconto e sem fechar a reserva.
3. **"Consegue um desconto?"** → o assistente passa para a equipe. **Entre como a Maré Alta** (`marealta`): na tela
   da equipe a conversa aparece; responda e clique em **"Devolver ao bot"**.
4. Na tela da equipe, **crie uma reserva direta para amanhã** (com telefone e consentimento) → a linha do tempo mostra
   a confirmação, as boas-vindas com o link da FNRH Digital e a pergunta do horário de chegada já enviadas (as
   etapas seguintes saem sozinhas na hora certa). No atendimento, com o mesmo telefone, aparecem as mensagens.
5. **Painel**: ocupação por dia da semana (sexta e sábado mais cheios) e receita bruta × líquida por canal.

Extras: responder "chego às 23h" na conversa de quem chega amanhã; importar `data/exemplo.ics` na unidade 101
(tela da equipe → Calendário) e ver o alerta de conflito; entrar como `admin` e cadastrar um hotel novo.

**Plano B**: sem internet ou sem chave, tudo funciona em modo demo. Há também um vídeo do funcionamento completo
(atendimento, equipe, chegada, calendário com alerta de conflito, painel e cadastro de hotel novo), com respostas da IA, animações e legendas, em
[docs/video/demo_recepcao24h.mp4](docs/video/demo_recepcao24h.mp4) (4min12s, Full HD, sem áudio: dá para narrar por cima), e
o PDF com as telas em [docs/](docs/).

Para regravar o vídeo com as datas do dia (precisa do Google Chrome e da chave de IA no `.env`):

```powershell
pip install -r requirements-dev.txt
python ferramentas/gravar_demo.py
```

O script cria um banco temporário, sobe o servidor, executa o roteiro sozinho e salva o MP4; não mexe no seu banco.

---

## Telas

| Endereço | O que tem |
|---|---|
| `/` | Apresentação, botão Entrar e o atendimento de cada hotel |
| `/entrar` | Login (equipe de um hotel ou administração) |
| `/admin` | Administração: hotéis clientes e cadastro de hotel novo |
| `/chat?hotel=mare-alta` | Atendimento do hóspede (público; na versão final, o WhatsApp do hotel): número do hóspede e a conversa, com o status "assistente" ou "com a equipe" |
| `/equipe` | Conversas escaladas (responder, devolver ao bot, encerrar), chegadas e saídas de hoje com hora prevista, alertas abertos, reservas com valor pendente, nova reserva direta e importação/exportação de iCal |
| `/reservas/<id>` | Dados da reserva e linha do tempo da jornada (etapas, horários e status) |
| `/hoteis/novo` | Cadastro M0 (só a administração): acesso do hotel, horários (validados pela Portaria MTur nº 28/2025), políticas, acomodações, canais e as perguntas-modelo que geram a base de conhecimento |
| `/painel?inicio=AAAA-MM-DD&fim=AAAA-MM-DD` | Indicadores e gráficos; padrão: últimos 30 dias |
| `/ical/<hotel>/<unidade>.ics` | iCal de saída de uma unidade (ex.: `/ical/mare-alta/101.ics`) |

---

## Como funciona

### Atendimento (M1)

O bot responde **somente** com a base de conhecimento e os dados do hotel da conversa. Ele se apresenta como
assistente virtual, recusa com educação assuntos fora do hotel (sem escalar) e **passa para a equipe** pedidos de
desconto ou negociação, reclamações, pedidos de atendente e perguntas sobre o hotel que a base não cobre. Depois de
escalar, fica em silêncio naquela conversa até a equipe devolvê-la.

- **Modo demo** (sem IA): normaliza o texto; gatilhos de escalonamento → equipe; datas dd/mm + palavras de reserva →
  consulta disponibilidade; horário de chegada ("chego às 23h") → registra na reserva do telefone; senão, busca o
  melhor item da base por palavras-chave e similaridade; sem resposta: assunto do hotel → equipe, outro assunto →
  recusa.
- **Modo IA**: Claude com *tool use*. O prompt leva só os dados e a base do hotel, as últimas 10 mensagens e três
  ferramentas (`consultar_disponibilidade`, `escalar_para_humano`, `registrar_hora_chegada`); o hotel vem da
  conversa e não é parâmetro da IA. Com `GEMINI_API_KEY`, o mesmo prompt e as mesmas ferramentas vão para o Gemini
  (`app/bot/gemini.py`). Se a API falhar, a mensagem é respondida pelo modo demo.

### Jornada de chegada (M2)

Toda reserva gera 6 mensagens: **confirmação** (na hora, com horários, early/late e cancelamento), **boas-vindas**
com o link da FNRH Digital (3 dias antes, 10h), **horário de chegada** (1 dia antes, 10h), **instruções de entrada**
(3h antes do check-in, conforme o modo de chegada), **chegada** com wifi e café (no horário do check-in) e
**pesquisa** de 1 a 5 (2h depois do check-out). Sem telefone ou consentimento, o texto fica pronto para a equipe
copiar no chat da OTA. Reserva feita em cima da hora recebe as etapas vencidas logo depois da confirmação.

Enquanto o servidor roda, um agendador confere a cada 30 segundos o que já venceu e envia (na produção, papel do
n8n). Se o hóspede não informar o horário de chegada em 6h, a pergunta é reenviada; mais 6h sem resposta geram um
alerta. Nos testes, o tempo é controlado por `app/relogio.py` (a variável `AGENDADOR=0` desliga o agendador).

### Pós-estadia (M4)

Nota de 1 a 3 gera alerta de **nota baixa** para a equipe. O convite para avaliar no canal de origem e no Google vai
para **todos**, sem oferecer vantagem (o Google proíbe pedir avaliação só a quem gostou).

### Calendário (M3)

Uma unidade não pode ter duas reservas ativas sobrepostas: a reserva manual sobreposta é recusada; a importação de
iCal que sobrepõe é gravada e gera **alerta de conflito**. Reserva de OTA sem valor gera pendência, que a equipe
completa na tela. O iCal de saída tem um arquivo por unidade, sem dados pessoais do hóspede.

### Indicadores (M5)

Contam só reservas confirmadas ou concluídas e as noites dentro do período (a receita de uma reserva que atravessa o
limite entra proporcional às noites).

| Indicador | Fórmula |
|---|---|
| Ocupação | noites vendidas ÷ (unidades ativas × dias) |
| ADR | receita de hospedagem ÷ noites vendidas (só reservas com valor) |
| RevPAR | receita de hospedagem ÷ (unidades ativas × dias) |
| Receita líquida por canal | receita do canal × (1 − comissão) |
| % reservas diretas | reservas de canais sem comissão ÷ total de reservas |
| Resolução do bot | conversas encerradas sem escalonamento ÷ total de conversas |
| Nota média | avaliações das estadias com check-out no período |

---

## Teste de bancada

```powershell
python bancada.py              # modo demo
python bancada.py --modo ia    # modo IA (precisa de ANTHROPIC_API_KEY)
```

Lê `data/perguntas_teste.csv` (colunas `hotel;pergunta;esperado`, separadas por `;` para abrir direto no Excel),
faz cada pergunta numa conversa nova e grava `resultados_bancada.csv` com a resposta, o status do bot e o acerto
automático. No `esperado`, use um trecho que precisa aparecer na resposta (sem diferenciar maiúsculas e acentos),
`ESCALAR` (a conversa tem de ir para a equipe) ou `FORA_ESCOPO` (recusa sem escalar). Ao fim, mostra o % de acerto
por hotel e quantas respostas trouxeram dado de outro hotel. A bancada roda numa cópia do banco, então não suja o
painel.

Há três baterias em `data/` (use `--entrada` para escolher): `perguntas_teste.csv` (40, a inicial),
`perguntas_variadas.csv` (60, com o jeito real de escrever no WhatsApp) e `perguntas_controle.csv` (30, escrita
depois dos ajustes e nunca usada para ajustar o bot). No modo demo: 40/40, 60/60 e **28/30 (93%) na de controle**,
sem nenhuma resposta com dado de outro hotel. Detalhes, erros corrigidos e limitações em
[docs/validacao.md](docs/validacao.md).

## Testes automatizados

```powershell
python -m pytest
```

Rodam em modo demo, sem chave e sem internet. Os testes marcados com `llm` repetem os critérios do bot usando a API
real e só rodam quando `ANTHROPIC_API_KEY` está definida (sem ela, aparecem como "skipped"); os marcados com
`gemini` fazem o mesmo com `GEMINI_API_KEY`.

---

## Estrutura

```
app/
  main.py              aplicação FastAPI (monta as rotas)
  web.py               templates Jinja2 e filtros de formatação
  db.py, models.py     SQLAlchemy + SQLite
  relogio.py           "agora" do sistema (nos testes, dá para adiantar)
  auth.py              login: senha com PBKDF2, sessão em cookie assinado, um hotel por conta
  formatacao.py        moeda, datas, normalização de texto
  bot/                 textos padrão, modo demo, modo IA (prompt + tool use) e ferramentas
  servicos/            disponibilidade, reservas, jornada, pós-estadia, conversas, indicadores, iCal,
                       cadastro e base de conhecimento
  rotas/               uma rota por tela (chat, equipe, reservas, cadastro, painel, iCal)
templates/  static/    telas; Chart.js servido localmente em static/vendor/
seed.py                dados de exemplo
bancada.py             teste de bancada
data/                  banco, exemplo.ics e perguntas_teste.csv
docs/                  Entrega 3 (E3_arquitetura.md/.pdf, diagramas em docs/e3/), PDF com as telas, capturas
                       (docs/telas/*.png), vídeo da demo e relatório de validação
ferramentas/           gravar_demo.py (vídeo do roteiro), diagramas.py (SVGs da E3), md_para_pdf.py (Markdown → PDF);
                       dependências em requirements-dev.txt
tests/                 testes (pytest)
DECISOES.md            decisões tomadas na construção
```

## Documentos do trabalho

- [docs/E3_arquitetura.md](docs/E3_arquitetura.md) (e o [PDF](docs/E3_arquitetura.pdf)) — Entrega 3: arquitetura de
  produção, modelo de dados, formulário M0, cotação de custos com fonte e data, benchmark de preço e regras atuais do
  Airbnb, do Booking.com e do WhatsApp.
- [docs/validacao.md](docs/validacao.md) — teste de bancada do bot.
- [docs/Recepcao24h_telas_do_prototipo.pdf](docs/Recepcao24h_telas_do_prototipo.pdf) — telas do protótipo.

## Fora do escopo

WhatsApp real, integração real com Airbnb/Booking, pagamento, recuperação de senha, vários usuários por hotel e
deploy.

## Licença

Copyright (c) 2026 Rodrigo Fassarella Leite. **Todos os direitos reservados.** O repositório é público só para
consulta e avaliação acadêmica: sem autorização por escrito do autor, é proibido usar, copiar, modificar, criar
obras derivadas (inclusive usar o código como base para um software igual ou semelhante), distribuir ou oferecer
como serviço. Veja [LICENSE](LICENSE).

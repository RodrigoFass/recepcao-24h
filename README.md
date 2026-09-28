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

`python seed.py` apaga e recria o banco (`data/recepcao24h.db`) e zera o relógio simulado. **"Hoje" é a data em que o
seed roda: rode `python seed.py` no dia da apresentação** para as datas ficarem atuais. O seed cria:

- 2 hotéis com base de conhecimento de 16 itens cada, 1 usuário da equipe por hotel;
- reservas dos últimos 90 dias (ocupação ~55% na Maré e ~45% na Serra, com sexta e sábado mais cheios) e ~15 nos
  próximos 30 dias, com chegadas hoje e amanhã nos dois hotéis;
- o **próximo fim de semana lotado na Serra Verde** (para o teste de indisponibilidade);
- ~20% das reservas de OTA sem valor (pendência), ~10 conversas antigas e ~20 avaliações por hotel;
- `data/exemplo.ics`: um bloqueio de 3 noites na suíte 101 da Maré Alta que **sobrepõe** uma reserva futura (para
  mostrar o alerta de conflito).

### Variáveis de ambiente (todas opcionais)

| Variável | Para quê | Padrão |
|---|---|---|
| `ANTHROPIC_API_KEY` | Liga o modo IA (Claude com tool use) | sem chave = modo demo |
| `MODEL` | Modelo usado no modo IA | `claude-haiku-4-5-20251001` |
| `DEMO_MODE` | `1` força o modo demo mesmo com chave | desligado |
| `DATABASE_URL` | Outro arquivo SQLite | `sqlite:///data/recepcao24h.db` |

No PowerShell: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`. No Linux/macOS: `export ANTHROPIC_API_KEY=sk-ant-...`.
O selo no canto superior direito mostra o modo ativo ("Modo demo" ou "Modo IA").

---

## Roteiro da demo (2 minutos)

Antes: `python seed.py` e suba o servidor. O roteiro também aparece na tela inicial, com as datas já calculadas.

1. **Chat da Maré Alta**: "aceita pet?" → sim, até 10 kg, R$ 50. **Chat da Serra Verde**: a mesma pergunta → não
   aceita. Mesma plataforma, respostas diferentes: cada hotel só enxerga os próprios dados.
2. **"Tem vaga de [sexta] a [domingo]?"** (datas de ~2 semanas à frente, no formato dd/mm; há uma pergunta rápida
   pronta no chat) → tipos livres e tarifa base × noites, sem desconto e sem fechar a reserva.
3. **"Consegue um desconto?"** → o assistente passa para a equipe (o selo muda para "Com a equipe"). Na **tela da
   equipe**, a conversa aparece; responda como equipe e clique em **"Devolver ao bot"**.
4. Na tela da equipe, **crie uma reserva direta** (com telefone e a caixa de consentimento marcada) → abre a
   **linha do tempo da jornada** → clique em **"Até a próxima mensagem"** algumas vezes → no chat daquele telefone
   aparecem a confirmação, as boas-vindas com o link da FNRH Digital, a pergunta do horário de chegada etc.
5. **Painel da Maré Alta**: ocupação por dia da semana (sexta e sábado mais cheios) e receita bruta × líquida por
   canal (quanto fica com o Airbnb e o Booking).

Extras, se sobrar tempo: responder "chego às 23h" na conversa de quem chega amanhã; importar `data/exemplo.ics` na
unidade 101 (tela da equipe → Calendário) e ver o alerta de conflito; cadastrar um hotel novo com "Preencher com um
exemplo" e conversar com ele no chat.

**Plano B**: sem internet ou sem chave, tudo funciona em modo demo. Há também um vídeo desse roteiro, com
legendas, em [docs/video/demo_recepcao24h.mp4](docs/video/demo_recepcao24h.mp4) (1min09s, sem áudio: dá para
narrar por cima), e o PDF com as telas em [docs/](docs/).

Para regravar o vídeo com as datas do dia (precisa do Google Chrome):

```powershell
pip install -r requirements-dev.txt
python ferramentas/gravar_demo.py
```

O script cria um banco temporário, sobe o servidor, executa o roteiro sozinho e salva o MP4; não mexe no seu banco.

---

## Telas

| Endereço | O que tem |
|---|---|
| `/` | Escolha do hotel e roteiro da demo |
| `/chat?hotel=mare-alta` | Chat que simula o WhatsApp do hóspede: escolha o telefone (hóspedes com reserva ou "novo contato"), perguntas rápidas e selo mostrando se a conversa está com o assistente ou com a equipe |
| `/equipe?hotel=mare-alta` | Conversas escaladas (responder, devolver ao bot, encerrar), chegadas e saídas de hoje com hora prevista, alertas abertos, reservas com valor pendente, nova reserva direta, importação/exportação de iCal e controles do relógio simulado |
| `/reservas/<id>` | Dados da reserva e linha do tempo da jornada (etapas, horários e status) |
| `/hoteis/novo` | Cadastro M0: horários (validados pela Portaria MTur nº 28/2025), políticas, acomodações, canais e as perguntas-modelo que geram a base de conhecimento |
| `/painel?hotel=mare-alta&inicio=AAAA-MM-DD&fim=AAAA-MM-DD` | Indicadores e gráficos; padrão: últimos 30 dias |
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
  conversa e não é parâmetro da IA. Se a API falhar, a mensagem é respondida pelo modo demo.

### Jornada de chegada (M2) e relógio simulado

Toda reserva gera 6 mensagens: **confirmação** (na hora, com horários, early/late e cancelamento), **boas-vindas**
com o link da FNRH Digital (3 dias antes, 10h), **horário de chegada** (1 dia antes, 10h), **instruções de entrada**
(3h antes do check-in, conforme o modo de chegada), **chegada** com wifi e café (no horário do check-in) e
**pesquisa** de 1 a 5 (2h depois do check-out). Sem telefone ou consentimento, o texto fica pronto para a equipe
copiar no chat da OTA. Reserva feita em cima da hora recebe as etapas vencidas logo depois da confirmação.

O relógio do sistema é **simulado**: "Avançar 1 hora", "Avançar 1 dia" e "Até a próxima mensagem" adiantam o relógio
e entregam no chat as mensagens vencidas. Se o hóspede não informar o horário de chegada em 6h, a pergunta é
reenviada; mais 6h sem resposta geram um alerta.

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
real e só rodam quando `ANTHROPIC_API_KEY` está definida (sem ela, aparecem como "skipped").

---

## Estrutura

```
app/
  main.py              aplicação FastAPI (monta as rotas)
  web.py               templates Jinja2 e filtros de formatação
  db.py, models.py     SQLAlchemy + SQLite
  relogio.py           relógio simulado
  formatacao.py        moeda, datas, normalização de texto
  bot/                 textos padrão, modo demo, modo IA (prompt + tool use) e ferramentas
  servicos/            disponibilidade, reservas, jornada, pós-estadia, conversas, indicadores, iCal,
                       cadastro e base de conhecimento
  rotas/               uma rota por tela (chat, equipe, reservas, cadastro, painel, iCal)
templates/  static/    telas; Chart.js servido localmente em static/vendor/
seed.py                dados de exemplo
bancada.py             teste de bancada
data/                  banco, exemplo.ics e perguntas_teste.csv
docs/                  PDF com as telas, capturas (docs/telas/*.png), vídeo da demo e relatório de validação
ferramentas/           gravar_demo.py: grava o vídeo do roteiro (dependências em requirements-dev.txt)
tests/                 testes (pytest)
DECISOES.md            decisões tomadas na construção
```

## Fora do escopo

WhatsApp real, integração real com Airbnb/Booking, pagamento, login completo (basta o seletor de hotel) e deploy.

## Licença

Copyright (c) 2026 Rodrigo Fassarella Leite. **Todos os direitos reservados.** O repositório é público só para
consulta e avaliação acadêmica: sem autorização por escrito do autor, é proibido usar, copiar, modificar, criar
obras derivadas (inclusive usar o código como base para um software igual ou semelhante), distribuir ou oferecer
como serviço. Veja [LICENSE](LICENSE).

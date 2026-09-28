# Recepção 24h — protótipo

Instruções para o Claude Code construir e manter este projeto. Leia este arquivo inteiro antes de começar.

## Contexto

Trabalho acadêmico individual da disciplina Gestão de Micro e Pequenas Empresas (Sistemas de Informação, UVV). O protótipo precisa estar pronto até **27/10/2026**, e a apresentação é em 12/11/2026.

A **Recepção 24h** é uma plataforma para hotéis e pousadas pequenos (5 a 20 unidades) que vendem por vários canais (Airbnb, Booking, WhatsApp, telefone). Ela:
- atende hóspedes automaticamente 24h, só com as informações daquele hotel, e passa para a equipe o que exige uma pessoa;
- conduz a chegada do hóspede com mensagens agendadas;
- unifica o calendário dos canais;
- pede avaliação depois da estadia e alerta a equipe em caso de nota baixa;
- mostra um painel com ocupação, ADR, RevPAR e receita líquida por canal.

A mesma plataforma atende **vários hotéis com dados totalmente separados**. Esse é o ponto central da demo.

Na produção (descrita no trabalho escrito), o orquestrador seria o n8n com a WhatsApp Cloud API. **Este protótipo não usa nenhum dos dois:** é uma aplicação local que simula tudo.

## Como trabalhar

- Prioridade: **a demo funcionar bem**, com código simples e legível. Não é para produção.
- Construa pelas **Etapas** abaixo, na ordem. Ao fim de cada etapa: rode `pytest`, corrija o que falhar, atualize o `README.md` e dê um resumo curto do que foi feito. Se o projeto for um repositório git, faça um commit por etapa.
- Só pare para perguntar se algo bloquear. Nas demais decisões, escolha a opção mais simples e registre em `DECISOES.md` (uma linha por decisão).
- Interface, textos do bot, nomes de telas e README em **português do Brasil**. Código e nomes de variáveis podem ficar em português ou inglês, mas mantenha um padrão só.
- Nenhum serviço externo além da API da Anthropic (opcional). Tudo roda localmente e **funciona offline em modo demo**.
- O visual do chat pode lembrar um app de mensagens (balões, cores neutras), mas **sem logo, nome ou identidade visual do WhatsApp**.

## Stack

- Python 3.11+, **FastAPI**, **SQLite** com SQLAlchemy, templates **Jinja2** e JavaScript simples (HTMX opcional).
- Gráficos com **Chart.js servido localmente** em `static/vendor/` (sem CDN).
- IA: SDK `anthropic`. Chave em `ANTHROPIC_API_KEY`; modelo em `MODEL` (padrão `claude-haiku-4-5-20251001`).
- **Modo demo:** ativo automaticamente sem `ANTHROPIC_API_KEY`, ou forçado com `DEMO_MODE=1`.
- Fuso `America/Sao_Paulo`; datas ISO no banco; moeda exibida como `R$ 1.234,56`.
- Testes com `pytest`. Seed determinístico (semente fixa, `random.seed(42)`).
- `requirements.txt` enxuto.

Estrutura sugerida:

```
app/
  main.py            # FastAPI, rotas
  db.py, models.py   # SQLAlchemy
  relogio.py         # relógio simulado
  bot/
    prompt.py        # prompt de sistema montado por hotel
    llm.py           # modo IA (tool use)
    demo.py          # modo demo (regras + busca)
    ferramentas.py   # consultar_disponibilidade, escalar_para_humano, registrar_hora_chegada
  servicos/          # disponibilidade, jornada, indicadores, ical
templates/  static/
seed.py  bancada.py
data/exemplo.ics  data/perguntas_teste.csv
tests/
README.md  DECISOES.md
```

## Modelo de dados

| Entidade | Campos |
|---|---|
| **Hotel** | id, nome, slug, cidade, endereco, telefone, whatsapp, checkin_hora, checkout_hora, early_checkin_permite, early_checkin_preco, late_checkout_permite, late_checkout_preco, modo_chegada (`recepcao_24h` / `recepcao_horario` / `autoatendimento`), recepcao_inicio, recepcao_fim, link_fnrh, politicas (json), fuso |
| **TipoAcomodacao** | id, hotel_id, nome, capacidade, tarifa_base, descricao |
| **Unidade** | id, hotel_id, tipo_id, identificacao, ativa |
| **Canal** | id, hotel_id, tipo (`airbnb` / `booking` / `whatsapp` / `telefone` / `balcao`), comissao_pct, anuncio_por (`unidade` / `tipo`) |
| **CalendarioExterno** | id, hotel_id, unidade_id, canal_id, ical_url, ultima_sincronizacao |
| **Hospede** | id, hotel_id, nome, telefone, email, consentimento_whatsapp_em (datetime ou nulo), idioma. **Não guardar documento** (fica na FNRH Digital) |
| **Reserva** | id, hotel_id, unidade_id, hospede_id, canal_id, check_in (data), check_out (data), num_hospedes, valor_total (nulo permitido), status (`confirmada` / `cancelada` / `concluida`), hora_prevista_chegada, origem (`manual` / `ical` / `csv` / `seed`), codigo_externo, criada_em |
| **ItemBaseConhecimento** | id, hotel_id, categoria, pergunta, palavras_chave, resposta, atualizado_em |
| **Conversa** | id, hotel_id, hospede_id (nulo permitido), telefone, status (`bot` / `humano` / `encerrada`), motivo_escalonamento, criada_em, atualizada_em |
| **Mensagem** | id, conversa_id, autor (`hospede` / `bot` / `equipe` / `sistema`), texto, criada_em |
| **MensagemAgendada** | id, reserva_id, etapa, enviar_em, status (`pendente` / `enviada` / `reenviada` / `sem_resposta` / `cancelada`), texto, meio (`whatsapp` / `ota_manual`) |
| **Avaliacao** | id, reserva_id, nota, comentario, alerta_enviado, convite_enviado |
| **Alerta** | id, hotel_id, tipo (`conflito` / `sem_resposta` / `nota_baixa` / `escalonamento` / `valor_pendente`), referencia, texto, resolvido, criado_em |
| **UsuarioEquipe** | id, hotel_id, nome, papel, contato_alerta |

**Toda** entidade ligada a um hotel tem `hotel_id`, e toda consulta filtra por ele.

## Indicadores (painel)

Considere só reservas `confirmada` ou `concluida` e conte as noites dentro do período.
- **Ocupação** = noites vendidas ÷ (unidades ativas × dias do período)
- **ADR** = receita de hospedagem ÷ noites vendidas (só reservas com `valor_total`)
- **RevPAR** = receita de hospedagem ÷ (unidades ativas × dias)
- **Receita líquida por canal** = receita do canal × (1 − comissao_pct/100)
- **% reservas diretas** = reservas de canais com comissão 0 ÷ total de reservas
- **Taxa de resolução do bot** = conversas encerradas sem escalonamento ÷ total de conversas
- Ocupação **por dia da semana** (seg a dom) no período

Receita de uma reserva que atravessa o fim do período: proporcional às noites dentro dele.

## Regras de negócio

**Bot (M1)**
- Responde **somente** com a base de conhecimento e os dados do hotel da conversa, mais o resultado das ferramentas. Nunca usa informação de outro hotel.
- Escopo: o hotel, a estadia, a reserva e a região (conforme a base). Para qualquer outro assunto, responde com uma frase padrão de recusa educada e **não escala**.
- Na primeira mensagem de uma conversa, apresenta-se como "assistente virtual" do hotel. Se perguntarem se é humano, diz que é um assistente virtual e oferece chamar a equipe.
- **Escala** (a conversa vira `humano`, cria um `Alerta` do tipo `escalonamento` e o bot para de responder nela) quando: há pedido de desconto ou negociação; há reclamação; o hóspede pede atendente/pessoa/gerente; ou a base não cobre a pergunta sobre o hotel. Ao escalar, avisa o hóspede que a equipe vai responder e informa o horário de atendimento da recepção, se houver.
- **Disponibilidade:** usa a ferramenta; informa tipos livres e tarifa base × noites. **Nunca** dá desconto nem confirma reserva: oferece passar para a equipe.
- Se o hóspede informar o horário de chegada (ex.: "chego às 23h"), usa `registrar_hora_chegada` na reserva ativa daquele telefone.
- Respostas curtas (até ~4 frases), numa mensagem só.

**Modo IA (`bot/llm.py`):** prompt de sistema montado por hotel (dados do hotel + base de conhecimento + regras acima), histórico das últimas 10 mensagens e **tool use** com:
- `consultar_disponibilidade(check_in, check_out, tipo=None)` (o `hotel_id` vem da conversa e não é parâmetro exposto à IA)
- `escalar_para_humano(motivo)`
- `registrar_hora_chegada(hora)`

**Modo demo (`bot/demo.py`), determinístico:**
1. Normaliza o texto (minúsculas, sem acentos).
2. Se tiver gatilho de escalonamento (desconto, abatimento, mais barato, negociar, reclama*, pessimo, sujo, problema, atendente, humano, pessoa, gerente, "falar com alguem"), escala.
3. Se tiver datas (dd/mm, sem ano = próxima ocorrência a partir do relógio simulado) e palavras de reserva/vaga/disponibilidade, consulta disponibilidade.
4. Se tiver horário de chegada ("chego as 23h", "chegada 22:30"), registra.
5. Senão, busca o melhor item da base por palavras-chave + similaridade (`difflib`). Se passar do limiar, responde com o item.
6. Se não houver correspondência: se a mensagem tiver vocabulário do domínio (quarto, reserva, diaria, check, cafe, pet, estacionamento, chale, pousada, hotel, hospedagem, praia, vaga, preco, chegar, wifi…), escala; caso contrário, é **fora do escopo** (recusa padrão, sem escalar).

**Cadastro (M0)**
- Rejeitar se o intervalo entre `checkout_hora` e `checkin_hora` passar de **3 horas** (Portaria MTur 28/2025), com mensagem de erro clara.
- As políticas de early/late e horários aparecem na mensagem de confirmação da reserva.

**Jornada (M2)** — ao criar uma reserva com telefone e consentimento, gerar `MensagemAgendada`:

| Etapa | Quando | Conteúdo |
|---|---|---|
| `confirmacao` | na criação | resumo, horários de check-in/out, early/late com preço, cancelamento |
| `boas_vindas` | check-in − 3 dias, 10h | endereço, estacionamento, link da FNRH Digital (`link_fnrh`) |
| `hora_chegada` | check-in − 1 dia, 10h | pergunta o horário previsto de chegada |
| `instrucoes_entrada` | dia do check-in, 3h antes do `checkin_hora` | conforme `modo_chegada` (quem recebe; ou cofre/senha) |
| `chegada` | dia do check-in, no `checkin_hora` | wifi, café, contato de emergência |
| `pesquisa` | dia do check-out, 2h depois do `checkout_hora` | pede nota de 1 a 5 |

- Reserva criada com menos de 3 dias de antecedência: as etapas já vencidas (exceto `pesquisa`) são enviadas juntas, em ordem, logo após a confirmação.
- Sem telefone ou sem consentimento: gerar com `meio = ota_manual` (texto pronto para copiar para o chat da OTA) e não "enviar".
- `hora_chegada` sem resposta em 6h: reenvia uma vez (`reenviada`). Sem resposta de novo em 6h: `sem_resposta` + `Alerta`.
- **Relógio simulado** global (`app/relogio.py`): começa em "agora" e a tela da equipe tem os botões "avançar 1h / 1 dia / até a próxima mensagem". Ao avançar, as mensagens vencidas são "enviadas": entram como mensagens do bot na conversa daquele telefone.

**Pós-estadia (M4)**
- Nota de 1 a 3: `Alerta` do tipo `nota_baixa`.
- Convite para avaliar (canal de origem + Google) enviado para **todos**, independentemente da nota, sem oferecer vantagem.

**Calendário (M3)**
- Uma unidade não pode ter duas reservas ativas sobrepostas. Criação manual sobreposta: recusar. Importação que sobreponha: gravar e gerar `Alerta` de conflito.
- Reserva de OTA sem `valor_total`: `Alerta` do tipo `valor_pendente`; a tela da equipe permite completar o valor.

## Dados de exemplo (`seed.py`)

Hotéis **fictícios** (deixar claro no README). Endereços e telefones inventados.

**Pousada Maré Alta** (`mare-alta`), litoral do ES
- 12 unidades anunciadas uma a uma: 8 "Suíte Casal" (2 pessoas, R$ 280) nº 101–108 e 4 "Suíte Família" (4 pessoas, R$ 380) nº 201–204.
- Check-in 14h, check-out 12h. Early check-in a partir de 11h por R$ 60 e late check-out até 14h por R$ 60, ambos sujeitos a disponibilidade.
- Modo de chegada `recepcao_horario`, recepção 8h–22h. Depois das 22h, chave em cofre com código enviado no dia.
- **Aceita pet** de até 10 kg, 1 por quarto, taxa de R$ 50 por estadia.
- Café da manhã incluso, 7h30–10h. Estacionamento gratuito, 10 vagas, sem reserva.
- Wifi `MareAlta_Hospedes`, senha `marealta2026`. Piscina 8h–20h. 150 m da praia. Silêncio após 22h.
- Crianças até 5 anos grátis no quarto dos pais; berço sem custo, mediante pedido.
- Cancelamento grátis até 7 dias antes; depois, 50%. Reservas diretas: sinal de 30% via Pix.
- Canais: Airbnb 16%, Booking 15%, WhatsApp 0%, telefone 0%.

**Chalés Serra Verde** (`serra-verde`), região serrana do ES
- 8 chalés: 6 "Chalé Casal" (2 pessoas, R$ 420) C1–C6 e 2 "Chalé Família" (4 pessoas, R$ 560) F1–F2.
- Check-in 15h, check-out 12h. **Não oferece** early check-in nem late check-out.
- Modo de chegada `autoatendimento`: senha da fechadura enviada no dia, 3h antes do check-in; zelador disponível por telefone das 8h às 20h.
- **Não aceita pet.**
- Café da manhã em cesta entregue no chalé às 8h, incluso. Estacionamento gratuito, 1 vaga em frente a cada chalé.
- Wifi `SerraVerde`, senha `serra2026`; sinal de celular fraco. Lareira com lenha inclusa (1 cesto por dia).
- Acesso por 3 km de estrada de terra, que carro comum passa.
- Crianças só no Chalé Família.
- Cancelamento grátis até 15 dias antes; depois, sem reembolso.
- Canais: Airbnb 16%, Booking 15%, WhatsApp 0%.

**Para cada hotel:**
- ~15 itens de base de conhecimento cobrindo check-in/out, early/late, pet, café, estacionamento, wifi, como chegar, chegada fora do horário, crianças/berço, cancelamento, pagamento, lazer (piscina/lareira), silêncio, roupa de cama e toalhas, pontos turísticos próximos.
- "Hoje" é a data em que o seed roda (o README orienta rodar `python seed.py` no dia da apresentação para as datas ficarem atuais).
- Reservas dos **últimos 90 dias até hoje** atingindo ocupação de ~55% (Maré) e ~45% (Serra), com sexta e sábado mais cheios; mais ~15 reservas nos próximos 30 dias, incluindo **pelo menos 1 chegada hoje e 1 amanhã** em cada hotel.
- O **próximo fim de semana (sexta a domingo) fica lotado na Serra Verde** (todas as unidades), para o teste de indisponibilidade. Deixar livres pelo menos algumas unidades em outros fins de semana.
- Canais: Maré 50% Airbnb, 20% Booking, 30% direto (WhatsApp/telefone); Serra 40% Airbnb, 10% Booking, 50% WhatsApp.
- `valor_total` = tarifa base × noites, com +20% nas noites de sexta e sábado. ~20% das reservas de OTA ficam **sem valor** (para demonstrar a pendência).
- Estadia de 1 a 4 noites (média ~2,5). Hóspedes com nomes e telefones fictícios; as reservas diretas têm consentimento.
- ~10 conversas antigas por hotel (algumas escaladas e encerradas) e ~20 avaliações, para o painel não começar vazio.
- 1 usuário da equipe por hotel.

`data/exemplo.ics`: um VEVENT bloqueando 3 noites na unidade 101 da Maré Alta, **sobrepondo** uma reserva futura do seed (para demonstrar o alerta de conflito). Gerar o arquivo a partir do seed, para as datas baterem.

`data/perguntas_teste.csv` (colunas `hotel`, `pergunta`, `esperado`): ~40 linhas iniciais, 20 por hotel, com `esperado` = trecho que precisa aparecer na resposta, `ESCALAR` ou `FORA_ESCOPO`. O usuário vai substituir por perguntas da pesquisa de campo.

## Telas

- `/` — seletor de hotel e links para as telas.
- `/chat?hotel=<slug>` — chat estilo app de mensagens. Campo para escolher o "telefone do hóspede" (lista dos hóspedes com reserva + "novo contato"). Mostra se a conversa está com o bot ou com humano.
- `/equipe?hotel=<slug>` — conversas escaladas (ler, responder como equipe, "devolver ao bot"); chegadas e saídas de hoje com hora prevista; alertas abertos (resolver); reservas com valor pendente (completar); criar reserva direta (com telefone e consentimento); controles do relógio simulado.
- `/reservas/<id>` — detalhes e **linha do tempo da jornada** (etapas, horários e status).
- `/hoteis/novo` — cadastro M0 completo, com ~15 perguntas-modelo para gerar a base. Depois de salvar, o novo hotel já funciona no chat.
- `/painel?hotel=<slug>&inicio=&fim=` — cartões (ocupação, ADR, RevPAR, % diretas, resolução do bot, nota média); gráficos de ocupação diária, ocupação por dia da semana e receita bruta × líquida por canal. Período padrão: últimos 30 dias.
- `/ical/<slug>/<unidade>.ics` — exportação. Importação pela tela da equipe (upload do `.ics` para uma unidade).

## Etapas

1. **Base:** estrutura, modelo, `seed.py`, relógio simulado, `README` inicial. Testes: seed cria os 2 hotéis; unidades e reservas sem sobreposição; ocupação próxima do alvo.
2. **Bot em modo demo + chat.** Testes de aceite do bot (abaixo) passando em modo demo.
3. **Tela da equipe + escalonamento + reserva direta.**
4. **Cadastro M0** com validação das 3h.
5. **Jornada + relógio + pós-estadia** (linha do tempo, reenvio, alertas).
6. **Painel** e testes dos indicadores.
7. **Modo IA** (`llm.py` com tool use). Testes marcados com `@pytest.mark.llm`, pulados sem chave.
8. **Bancada:** `python bancada.py [--modo demo|ia]` lê `data/perguntas_teste.csv`, roda cada pergunta numa conversa nova, grava `resultados_bancada.csv` (hotel, pergunta, esperado, resposta, status do bot, acerto automático) e imprime o % de acerto por hotel. O acerto automático é: trecho esperado contido na resposta; `ESCALAR` → conversa escalada; `FORA_ESCOPO` → recusa sem escalar.
9. **iCal:** importar e exportar, com alerta de conflito.
10. **Acabamento:** visual limpo e consistente; README final com instalação (Windows PowerShell e Linux/macOS), `python seed.py`, comando para subir o servidor, variáveis de ambiente e **roteiro de demo de 2 minutos**.

## Critérios de aceite (testes em `tests/`)

Rodam em modo demo por padrão; os marcados `llm` repetem os do bot quando há chave.
- "Aceita pet?" → Maré Alta: sim, com a condição (10 kg / R$ 50); Serra Verde: não.
- "Qual o horário do check-in?" → "14h" na Maré e "15h" na Serra.
- "Posso fazer late checkout?" → Maré: sim, até 14h por R$ 60; Serra: não oferece.
- "Qual a senha do wifi?" → a senha do hotel certo, nunca a do outro.
- "Consegue um desconto?", "Quero reclamar do quarto" e "Quero falar com uma pessoa" → conversa `humano`, `Alerta` criado, e a mensagem seguinte do hóspede não recebe resposta do bot.
- "Me ajuda a fazer meu trabalho da faculdade?" → recusa padrão, conversa continua `bot`.
- Disponibilidade: o próximo fim de semana da Serra Verde (lotado no seed) retorna indisponível; um período com unidades livres (o teste procura um) retorna os tipos e a tarifa base × noites.
- "Chego às 23h" (telefone com reserva amanhã) → `hora_prevista_chegada = 23:00`.
- **Isolamento:** para cada item da base de um hotel, perguntar no outro hotel nunca retorna a resposta do primeiro.
- Criar reserva com consentimento gera as 6 etapas nos horários certos; avançar o relógio entrega as mensagens vencidas no chat.
- Cadastro recusa check-out 11h + check-in 15h e aceita 12h + 15h.
- Reserva manual sobreposta é recusada; importação de `exemplo.ics` gera alerta de conflito.
- Indicadores do painel batem com um cálculo independente feito no teste direto do banco.
- Tudo funciona **sem `ANTHROPIC_API_KEY`**.

## Fora do escopo

WhatsApp real, integração real com Airbnb/Booking, pagamento, login completo (basta o seletor de hotel) e deploy.

## Roteiro da demo (2 min, incluir no README)

1. Chat da Maré Alta: "aceita pet?". Chat da Serra Verde: a mesma pergunta, com resposta diferente.
2. "Tem vaga de [sexta] a [domingo]?" (datas de ~2 semanas à frente, no formato dd/mm) → tipos e preço base.
3. "Consegue um desconto?" → escala; a tela da equipe mostra a conversa; a equipe responde e devolve ao bot.
4. Criar uma reserva direta → linha do tempo → "avançar até a próxima mensagem" algumas vezes → mensagens no chat.
5. Painel da Maré Alta: ocupação por dia da semana e receita líquida por canal.

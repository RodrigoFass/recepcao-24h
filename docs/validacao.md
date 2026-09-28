# Validação do bot — teste de bancada

Medições do **modo demo** (regras + busca na base, sem IA), feitas em 28/09/2026 com o banco do `seed.py`.
Cada pergunta roda numa conversa nova (`python bancada.py --entrada <arquivo>`), e o acerto é automático:

- trecho esperado → o trecho aparece na resposta (sem diferenciar maiúsculas e acentos);
- `ESCALAR` → a conversa foi passada para a equipe;
- `FORA_ESCOPO` → o bot recusou com a frase padrão, sem escalar;
- qualquer resposta com dado de outro hotel (nome, senha do wifi ou resposta da base) conta como erro.

## Resultados

| Bateria | Perguntas | Acertos | Dado de outro hotel | Como foi usada |
|---|---|---|---|---|
| `perguntas_teste.csv` (inicial) | 40 | 40 (100%) | 0 | Escrita junto com o bot |
| `perguntas_variadas.csv` — antes dos ajustes | 60 | 50 (83%) | 0 | Linha de base com linguagem de WhatsApp |
| `perguntas_variadas.csv` — depois dos ajustes | 60 | 60 (100%) | 0 | Usada para ajustar o bot (resultado otimista) |
| **`perguntas_controle.csv`** | **30** | **28 (93%)** | **0** | **Escrita depois dos ajustes e rodada uma vez, sem ajuste** |

**O número honesto é o da bateria de controle: 93% de acerto e nenhum vazamento entre hotéis.** A bateria
variada mediu o bot antes e depois dos ajustes; como os ajustes foram feitos olhando para ela, os 100% dela não
medem a capacidade de generalizar.

Meta do plano (hipótese H3): ≥ 80% de respostas certas ou escaladas corretamente e 0 respostas com dado de outro
hotel. **Atingida no modo demo.**

## O que a bateria variada revelou (e foi corrigido)

| Erro (antes) | Causa | Correção |
|---|---|---|
| "posso levar meu gatinho" → recusa | palavra ausente na base | palavra-chave "gatinh" |
| "que horas libera o chalé?", "dá pra sair às 14h?" | formas de perguntar horário não previstas | palavras-chave "horas libera", "entrar", "sair", "desocupar" |
| "dá pra chegar às 10h?", "vou chegar meia-noite, tem alguém?" → "não encontrei sua reserva" | pergunta tratada como aviso de horário de chegada | sem reserva ativa, pergunta com horário segue para a base |
| "se eu desistir da reserva perco o dinheiro?" → formas de pagamento | empate entre cancelamento e pagamento | palavras-chave "desist reserva", "multa" |
| "quero falar com a recepção" → horário da recepção | pedido de atendimento não reconhecido | gatilho "falar com a recepção/equipe/dono…" |
| "tem como fazer um precinho camarada?" | negociação informal não reconhecida | gatilhos "precinho", "camarada", "mais em conta", "por menos" |
| "quanto é 2+2?" → tabela de preços | "quanto" sozinho tratado como preço | preço só com "quanto custa/fica/sai/cobra" |
| "como funciona a entrada no chalé?" → endereço | tolerância a erro de digitação confundia "entrada" com "estrada" | similaridade mínima de 0,85 para 0,88 |
| "tem jacuzzi?" → recusa | item de estrutura fora do vocabulário | "tem/possui/oferece …?" conta como assunto do hotel (escala) |

## Erros que continuam (bateria de controle)

| Pergunta | O que o bot fez | Tipo de erro |
|---|---|---|
| "Tem cofre dentro do quarto?" (Maré Alta) | respondeu sobre o cofre da entrada, onde fica a chave depois das 22h | **resposta errada**: confusão de palavra-chave |
| "Cabem 4 pessoas no Chalé Casal?" (Serra Verde) | passou para a equipe | **erro seguro**: a equipe responde |

Limitações conhecidas do modo demo (esperado que o modo IA trate melhor):

- entende uma pergunta por mensagem; "aceita pet e tem estacionamento?" recebe só uma das respostas;
- não interpreta o sentido da frase, só palavras-chave: termos com dois sentidos (cofre da entrada × cofre do
  quarto) podem levar à resposta errada;
- perguntas sobre capacidade ("cabem 4 pessoas?") vão para a equipe.

## Próximos passos da validação

1. Rodar as três baterias no **modo IA** (`python bancada.py --modo ia --entrada ...`), com a chave da API, e comparar.
2. Quando houver perguntas reais de hóspedes, criar uma nova bateria com elas e medir sem ajustar antes.
3. Pedir a um colega para conferir 10 respostas à mão, como prevê o plano.

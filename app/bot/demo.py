"""Modo demo: bot determinístico, sem IA (regras + busca na base do hotel).

Ordem das regras (CLAUDE.md):
  1. normaliza o texto;
  2. gatilho de escalonamento -> escala;
  3. datas + palavras de reserva -> consulta disponibilidade;
  4. horário de chegada -> registra na reserva;
  5. busca o melhor item da base (palavras-chave + difflib);
  6. sem correspondência: vocabulário do domínio -> escala; senão, fora do escopo.
Antes disso tratamos o que é conversa pura: saudação, agradecimento,
"você é humano?" e o "sim" depois de o bot oferecer chamar a equipe.
"""
import re
from datetime import date, timedelta
from difflib import SequenceMatcher

from app import relogio
from app.bot import ferramentas, textos
from app.formatacao import hora_br, minutos, moeda_curta, normalizar
from app.models import ItemBaseConhecimento, TipoAcomodacao
from app.servicos.base_conhecimento import item_por_categoria

MOTIVO_DESCONTO = "Pedido de desconto ou negociação"
MOTIVO_RECLAMACAO = "Reclamação"
MOTIVO_HUMANO = "Hóspede pediu atendimento humano"
MOTIVO_SEM_RESPOSTA = "Pergunta sem resposta na base"
MOTIVO_RESERVA = "Hóspede quer fechar uma reserva"

GATILHOS = [
    (r"\bdescont", MOTIVO_DESCONTO),
    (r"\babatiment", MOTIVO_DESCONTO),
    (r"\bmais barat", MOTIVO_DESCONTO),
    (r"\bnegoci", MOTIVO_DESCONTO),
    (r"\bpreco melhor|\bpromoc|\bprecinho|\bcamarada\b|\bmais em conta|\bpor menos\b|\bbaixar (o )?(preco|valor)",
     MOTIVO_DESCONTO),
    (r"\breclam", MOTIVO_RECLAMACAO),
    (r"\bpessim", MOTIVO_RECLAMACAO),
    (r"\bsuj[oa]s?\b|\bsujeira", MOTIVO_RECLAMACAO),
    (r"\bnao (esta )?funciona|\bquebrad|\bestragad|\bdefeito", MOTIVO_RECLAMACAO),
    (r"\bproblema", "Hóspede relatou um problema"),
    (r"\batendente", MOTIVO_HUMANO),
    (r"\bhumano\b", MOTIVO_HUMANO),
    (r"\bpessoa\b", MOTIVO_HUMANO),
    (r"\bgerente", MOTIVO_HUMANO),
    (r"\bfalar com alguem\b", MOTIVO_HUMANO),
    (r"\bfalar com (a |o )?(recepcao|equipe|dono|dona|responsavel|proprietari\w*|funcionari\w*|atendimento|gente)\b",
     MOTIVO_HUMANO),
    (r"\bme (liga|ligue|ligar)\b|\bligar pra mim\b", MOTIVO_HUMANO),
]

RE_IDENTIDADE = re.compile(
    r"\b(voce|vc|voces|vcs|isso|aqui)\s+(e|eh|sao)\s+(um\s+|uma\s+)?"
    r"(robo|bot|humano|humana|pessoa|gente|real|maquina|ia|atendente|automatico)\b"
    r"|^(e|eh)\s+(um\s+|uma\s+)?(robo|bot|humano|pessoa|gente|maquina)\b"
    r"|\b(falando|conversando)\s+com\s+(um\s+|uma\s+)?(robo|bot|maquina|humano|pessoa|gente|ia)\b"
)
RE_SAUDACAO_INICIO = re.compile(r"^(oi+|ola|opa|bom dia|boa tarde|boa noite|e ai|hello|hi|hey)\b\s*(tudo bem\b\s*)?")
RE_AGRADECIMENTO = re.compile(r"^(muito\s+)?(obrigad[oa]|valeu|brigad[oa]|agradeco|beleza|perfeito|otimo|show|entendi|ok)\b")
RE_SIM = re.compile(r"^(sim|s|quero|pode|claro|ok|isso|yes|por favor|com certeza|chama|chame|manda|pode ser)\b")
RE_NAO = re.compile(r"^(nao|n|agora nao|deixa|tudo bem)\b")

RE_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
RE_FAIXA = re.compile(r"\b(\d{1,2})\s+(?:a|ate|e)?\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
RE_RESERVA = re.compile(
    r"\b(reserv\w*|vagas?|disponi\w*|livres?|hospedagem|hospedar|quartos?|chales?|suites?|acomodac\w*|"
    r"diarias?|precos?|valor|valores|quanto|custa|tarifas?|pernoite|estadia|lugar)\b"
)
RE_PEDIDO_RESERVA = re.compile(r"\b(reserv\w*|vagas?|disponi\w*|livres?|hospedar|lugar)\b")
RE_PRECO = re.compile(r"\b(precos?|valor|valores|custa|tarifas?|diarias?)\b|\bquanto (custa|fica|sai|cobra\w*|seria)\b")
# pergunta (e não informação): "dá pra chegar às 10h?" não é o hóspede avisando o horário
RE_PERGUNTA = re.compile(r"^(da pra|da para|posso|podemos|pode|tem como|consigo|conseguimos|e possivel|tudo bem se)\b")
# "tem jacuzzi?", "vocês têm academia?": pergunta sobre a estrutura do hotel
RE_TEM_ESTRUTURA = re.compile(r"^(voces |vcs |vc |aqui |ai )?(tem|possui|possuem|oferece|oferecem)\b(?! como)")
RE_PESSOAS = re.compile(r"\b(\d{1,2})\s*(pessoas|pessoa|hospedes|adultos)\b")
RE_HORA = re.compile(r"\b(\d{1,2})\s*(?:horas?|hs|h|:)\s*(\d{2})?\b")
RE_CHEGADA = re.compile(r"\bcheg\w*|\bprevis\w*|\bestarei ai\b|\bestaremos ai\b")

STOPWORDS = set(
    "a o as os um uma uns umas de do da dos das e em no na nos nas para pra pro por com que qual quais se "
    "meu minha meus minhas seu sua voce voces vc vcs tem ter tenho posso pode podem ha eu me mais muito ao aos "
    "sobre como quando quanto ola oi dia gostaria queria quero saber favor obrigado obrigada la ai aqui isso "
    "esse essa este esta ja so nao sim ok hoje amanha tambem algum alguma fazer vai vou sao e".split()
)

DOMINIO = [
    "quarto", "reserv", "diaria", "check", "cafe", "pet", "estacion", "chale", "pousada", "hotel", "hosped",
    "praia", "vaga", "preco", "cheg", "wifi", "suite", "cama", "toalha", "piscina", "lareira", "crianca", "berco",
    "cancel", "pagament", "pix", "cartao", "cofre", "chave", "senha", "recepca", "banheir", "chuveir", "ventilador",
    "televis", "frigobar", "geladeira", "cozinha", "microondas", "secador", "acessib", "cadeira", "elevador",
    "escada", "limpeza", "arrumac", "faxina", "lavanderia", "almoc", "jantar", "refeic", "restaurante", "churras",
    "fumar", "cigarro", "estadia", "pernoite", "acomodac", "apartamento", "varanda", "valor", "tarifa", "taxa",
    "promoc", "pacote", "feriado", "reveillon", "carnaval", "acompanhante", "aniversario", "evento", "roupa",
    "travesseiro", "colchao", "lencol", "barulho", "silencio", "trilha", "cachoeira", "passeio", "turis",
    "estrada", "endereco", "localiz", "mapa", "uber", "taxi", "onibus", "aeroporto", "rodoviaria", "transfer",
    "sauna", "academia", "hidro", "equipe", "funcionari", "dono", "proprietari", "zelador", "hospedagem",
    "jacuzzi", "ofuro", "spa", "banheira", "massag", "bicicleta", "caiaque", "brinquedo",
]
DOMINIO_EXATO = {"tv", "mar", "ar", "gps"}


# ------------------------------------------------------------------ auxiliares

def _tokens(texto: str) -> list[str]:
    return [t for t in texto.split() if t not in STOPWORDS]


def _casa_palavra(palavra: str, tokens: list[str]) -> bool:
    for t in tokens:
        if t == palavra:
            return True
        if len(palavra) >= 4 and t.startswith(palavra):
            return True
        # pequenos erros de digitação; 0,88 separa "estacionamneto" (casa) de "entrada" x "estrada" (não casa)
        if len(palavra) >= 6 and len(t) >= 6 and SequenceMatcher(None, palavra, t).ratio() >= 0.88:
            return True
    return False


def pontuar(item: ItemBaseConhecimento, tokens: list[str]) -> int:
    """Soma, para cada palavra-chave presente, o número de palavras dela (mais específica vale mais)."""
    pontos = 0
    for chave in item.palavras_chave.split(","):
        palavras = [p for p in normalizar(chave).split() if p not in STOPWORDS]
        if palavras and all(_casa_palavra(p, tokens) for p in palavras):
            pontos += len(palavras)
    return pontos


def buscar_na_base(db, hotel_id: int, texto_normalizado: str):
    """Melhor item da base DESTE hotel, ou None se nada passar do limiar."""
    itens = db.query(ItemBaseConhecimento).filter_by(hotel_id=hotel_id).all()
    if not itens:
        return None
    tokens = _tokens(texto_normalizado)
    avaliados = [
        (pontuar(it, tokens), SequenceMatcher(None, texto_normalizado, normalizar(it.pergunta)).ratio(), it)
        for it in itens
    ]
    pontos, similaridade, melhor = max(avaliados, key=lambda x: (x[0], x[1]))
    if pontos >= 1 or similaridade >= 0.75:
        return melhor
    return None


def _do_dominio(texto_normalizado: str) -> bool:
    if "ar condicionado" in texto_normalizado:
        return True
    for t in texto_normalizado.split():
        if t in DOMINIO_EXATO:
            return True
        if any(t.startswith(r) for r in DOMINIO if len(r) >= 3):
            return True
    return False


def _resolver_data(dia: int, mes: int, ano: str | None, hoje: date) -> date | None:
    try:
        if ano:
            a = int(ano)
            return date(a + 2000 if a < 100 else a, mes, dia)
        d = date(hoje.year, mes, dia)
        return d if d >= hoje else date(hoje.year + 1, mes, dia)
    except ValueError:
        return None


def extrair_datas(texto: str, hoje: date) -> list[date]:
    """Datas dd/mm (sem ano = próxima ocorrência a partir de hoje)."""
    achadas = RE_DATA.findall(texto)
    if len(achadas) == 1:
        faixa = RE_FAIXA.search(texto)  # "16 a 18/10"
        if faixa:
            d1, d2, mes, ano = faixa.groups()
            datas = [_resolver_data(int(d1), int(mes), ano, hoje), _resolver_data(int(d2), int(mes), ano, hoje)]
            return [d for d in datas if d]
    datas = [_resolver_data(int(d), int(m), a, hoje) for d, m, a in achadas]
    datas = [d for d in datas if d]
    # "30/12 a 02/01": a saída cai no ano seguinte
    if len(datas) >= 2 and datas[1] <= datas[0] and not achadas[1][2]:
        try:
            datas[1] = datas[1].replace(year=datas[0].year + (1 if datas[1].month < datas[0].month else 0))
        except ValueError:
            pass
    return datas


def extrair_hora(texto: str) -> str | None:
    if "meia noite" in texto:
        return "00:00"
    if "meio dia" in texto:
        return "12:00"
    m = RE_HORA.search(texto)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def _tipo_mencionado(db, hotel_id: int, texto: str) -> str | None:
    tipos = db.query(TipoAcomodacao).filter_by(hotel_id=hotel_id).all()
    palavras = set(texto.split())
    for t in tipos:
        outras = set()
        for o in tipos:
            if o.id != t.id:
                outras |= set(normalizar(o.nome).split())
        distintas = set(normalizar(t.nome).split()) - outras
        if distintas & palavras:
            return t.nome
    return None


def _ultima_do_bot(conversa):
    """Última mensagem que não é do hóspede (ignora a que acabou de chegar)."""
    for m in reversed(conversa.mensagens):
        if m.autor != "hospede":
            return m
    return None


def _aguardando_hora_chegada(db, conversa) -> bool:
    """A jornada perguntou o horário de chegada e o hóspede ainda não respondeu."""
    r = ferramentas.reserva_ativa_do_telefone(db, conversa.hotel_id, conversa.telefone)
    if r is None or r.hora_prevista_chegada:
        return False
    return any(m.etapa == "hora_chegada" and m.status in ("enviada", "reenviada") for m in r.mensagens_agendadas)


# ---------------------------------------------------------------- respostas

def texto_disponibilidade(res: dict) -> str:
    if "erro" in res:
        return f"{res['erro']} Pode me mandar as datas de entrada e saída? (ex.: 16/10 a 18/10)"
    n = res["noites"]
    periodo = f"de {res['check_in']:%d/%m} a {res['check_out']:%d/%m} ({n} noite{'s' if n > 1 else ''})"
    if not res["disponivel"]:
        alvo = f" em {res['tipo_pedido']}" if res.get("tipo_pedido") else ""
        pessoas = f" para {res['pessoas']} pessoas" if res.get("pessoas") else ""
        return f"Infelizmente não temos acomodação livre{alvo}{pessoas} {periodo}. Quer consultar outras datas?"
    partes = [
        f"{t['tipo']} (até {t['capacidade']} pessoas) por {moeda_curta(t['tarifa_base'])} a diária, "
        f"{moeda_curta(t['total'])} no total"
        for t in res["tipos"]
    ]
    return (
        f"Temos disponível {periodo}: {'; '.join(partes)}. Os valores são da tarifa base. "
        "Quer que eu passe para a equipe confirmar a reserva?"
    )


def _texto_hora_registrada(db, hotel, res: dict) -> str:
    hora = res["hora_prevista_chegada"]
    dia = date.fromisoformat(res["check_in"])
    partes = [f"Anotado! Registrei sua chegada prevista para as {hora_br(hora)} do dia {dia:%d/%m}."]
    h = minutos(hora)
    if hotel.modo_chegada == "recepcao_horario" and hotel.recepcao_inicio and hotel.recepcao_fim and (
        h >= minutos(hotel.recepcao_fim) or h < minutos(hotel.recepcao_inicio)
    ):
        item = item_por_categoria(db, hotel.id, "chegada_fora_horario")
        if item:
            partes.append(item.resposta)
    elif hotel.modo_chegada == "autoatendimento":
        partes.append("A senha da fechadura chega por mensagem no dia, 3h antes do check-in.")
    if 6 * 60 <= h < minutos(hotel.checkin_hora):
        partes.append(f"Lembrando que o check-in é a partir das {hora_br(hotel.checkin_hora)}.")
    return " ".join(partes)


def _texto_tarifas(db, hotel) -> str:
    tipos = db.query(TipoAcomodacao).filter_by(hotel_id=hotel.id).order_by(TipoAcomodacao.tarifa_base).all()
    lista = " e ".join(f"{moeda_curta(t.tarifa_base)} ({t.nome}, até {t.capacidade} pessoas)" for t in tipos)
    return (
        f"As diárias partem de {lista}, na tarifa base. Me diga as datas de entrada e saída "
        "(ex.: 16/10 a 18/10) que eu consulto a disponibilidade."
    )


def _escalar(db, conversa, motivo: str) -> str:
    return ferramentas.escalar_para_humano(db, conversa, motivo)["mensagem_ao_hospede"]


def responder(db, hotel, conversa, texto: str) -> str:
    """Resposta do bot para a mensagem do hóspede (já gravada na conversa)."""
    t = normalizar(texto)
    hoje = relogio.hoje(db)

    # conversa pura
    anterior = _ultima_do_bot(conversa)
    ofereceu_equipe = anterior is not None and anterior.autor == "bot" and anterior.texto.rstrip().endswith("?") \
        and "equipe" in anterior.texto
    if ofereceu_equipe and RE_SIM.match(t) and len(t.split()) <= 4:
        motivo = MOTIVO_RESERVA if "reserva?" in anterior.texto else MOTIVO_HUMANO
        return _escalar(db, conversa, motivo)
    if ofereceu_equipe and RE_NAO.match(t) and len(t.split()) <= 4:
        return "Tudo bem! Posso ajudar com mais alguma coisa?"

    if RE_IDENTIDADE.search(t):
        return textos.identidade(hotel)

    sem_saudacao = RE_SAUDACAO_INICIO.sub("", t).strip()
    if not sem_saudacao:
        return (
            f"{textos.apresentacao(hotel)} Posso ajudar com dúvidas sobre a hospedagem, disponibilidade de datas e a "
            "sua reserva. Como posso ajudar?"
        )
    t = sem_saudacao
    if RE_AGRADECIMENTO.match(t) and len(t.split()) <= 4:
        return "Por nada! Se precisar de algo, é só chamar."

    # 2. escalonamento
    for padrao, motivo in GATILHOS:
        if re.search(padrao, t):
            return _escalar(db, conversa, motivo)

    # 3. disponibilidade
    datas = extrair_datas(t, hoje)
    if datas and RE_RESERVA.search(t):
        check_in = datas[0]
        check_out = datas[1] if len(datas) > 1 else check_in + timedelta(days=1)
        pessoas = RE_PESSOAS.search(t)
        res = ferramentas.consultar_disponibilidade(
            db,
            conversa,
            check_in,
            check_out,
            tipo=_tipo_mencionado(db, hotel.id, t),
            pessoas=int(pessoas.group(1)) if pessoas else None,
        )
        return texto_disponibilidade(res)

    # 4. horário de chegada
    hora = extrair_hora(t)
    if hora and (RE_CHEGADA.search(t) or _aguardando_hora_chegada(db, conversa)):
        tem_reserva = ferramentas.reserva_ativa_do_telefone(db, conversa.hotel_id, conversa.telefone) is not None
        eh_pergunta = "?" in texto or RE_PERGUNTA.match(t)
        # sem reserva, "dá pra chegar às 10h?" é uma dúvida: segue para a base de conhecimento
        if tem_reserva or not eh_pergunta:
            res = ferramentas.registrar_hora_chegada(db, conversa, hora)
            if res["ok"]:
                return _texto_hora_registrada(db, hotel, res)
            return (
                "Não encontrei uma reserva ativa para este telefone. Se você já reservou, a equipe pode verificar. "
                "Quer que eu chame alguém da equipe?"
            )

    # 5. base de conhecimento
    item = buscar_na_base(db, hotel.id, t)
    if item:
        return item.resposta

    # pedido de reserva ou de preço sem datas
    if RE_PRECO.search(t):
        return _texto_tarifas(db, hotel)
    if RE_PEDIDO_RESERVA.search(t):
        return (
            "Para consultar a disponibilidade, me diga as datas de entrada e saída (ex.: 16/10 a 18/10) "
            "e quantas pessoas vão se hospedar."
        )

    # 6. sem correspondência
    if _do_dominio(t) or RE_TEM_ESTRUTURA.match(t):
        return _escalar(db, conversa, MOTIVO_SEM_RESPOSTA)
    return textos.recusa(hotel)

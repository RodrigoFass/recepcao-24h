"""Templates Jinja2 e funções comuns às rotas."""
from pathlib import Path
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import bot, formatacao, relogio
from app.models import Hotel

RAIZ = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(RAIZ / "templates"))

_f = templates.env.filters
_f["moeda"] = formatacao.moeda
_f["moeda_curta"] = formatacao.moeda_curta
_f["data_br"] = formatacao.data_br
_f["data_curta"] = formatacao.data_curta
_f["hora_br"] = formatacao.hora_br
_f["pct"] = formatacao.pct
_f["numero"] = formatacao.numero
_f["dia_semana"] = lambda d: formatacao.DIAS_SEMANA[d.weekday()]

NOMES_ETAPAS = {
    "confirmacao": "Confirmação",
    "boas_vindas": "Boas-vindas (3 dias antes)",
    "hora_chegada": "Horário de chegada (1 dia antes)",
    "instrucoes_entrada": "Instruções de entrada (3h antes)",
    "chegada": "Chegada (wifi, café, emergência)",
    "pesquisa": "Pesquisa pós-estadia",
}
NOMES_STATUS = {
    "pendente": "agendada",
    "enviada": "enviada",
    "reenviada": "reenviada",
    "sem_resposta": "sem resposta",
    "cancelada": "cancelada",
    "confirmada": "confirmada",
    "concluida": "concluída",
    "bot": "assistente virtual",
    "humano": "equipe",
    "encerrada": "encerrada",
}
NOMES_MODO_CHEGADA = {
    "recepcao_24h": "Recepção 24h",
    "recepcao_horario": "Recepção com horário",
    "autoatendimento": "Autoatendimento",
}
NOMES_ALERTA = {
    "conflito": "Conflito de calendário",
    "sem_resposta": "Hóspede sem resposta",
    "nota_baixa": "Nota baixa",
    "escalonamento": "Conversa escalada",
    "valor_pendente": "Valor pendente",
}
templates.env.globals.update(
    NOMES_ETAPAS=NOMES_ETAPAS,
    NOMES_STATUS=NOMES_STATUS,
    NOMES_MODO_CHEGADA=NOMES_MODO_CHEGADA,
    NOMES_ALERTA=NOMES_ALERTA,
)


def obter_hotel(db, slug: str | None) -> Hotel:
    if not slug:
        hotel = db.query(Hotel).order_by(Hotel.id).first()
    else:
        hotel = db.query(Hotel).filter_by(slug=slug).first()
    if hotel is None:
        raise HTTPException(404, "Hotel não encontrado. Rode python seed.py ou cadastre um hotel.")
    return hotel


def render(request: Request, db, nome: str, hotel: Hotel | None = None, pagina: str = "", **ctx):
    agora = relogio.agora(db)
    contexto = {
        "request": request,
        "hotel": hotel,
        "hoteis": db.query(Hotel).order_by(Hotel.id).all(),
        "agora": agora,
        "hoje": agora.date(),
        "modo_bot": bot.modo(),
        "pagina": pagina,
        "msg": request.query_params.get("msg"),
        "erro": request.query_params.get("erro"),
        **ctx,
    }
    return templates.TemplateResponse(request, nome, contexto)


def redirecionar(caminho: str, **params) -> RedirectResponse:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    url = f"{caminho}?{urlencode(params)}" if params else caminho
    return RedirectResponse(url, status_code=303)

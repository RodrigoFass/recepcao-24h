"""Painel de gestão (M5)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from app import relogio
from app.db import get_db
from app.servicos.indicadores import calcular
from app.web import obter_hotel, render

router = APIRouter()


def _data(texto: str | None, padrao: date) -> date:
    try:
        return date.fromisoformat(texto) if texto else padrao
    except ValueError:
        return padrao


@router.get("/painel")
def tela_painel(request: Request, hotel: str | None = None, inicio: str | None = None, fim: str | None = None,
                db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    hoje = relogio.hoje(db)
    fim_d = _data(fim, hoje)
    inicio_d = _data(inicio, fim_d - timedelta(days=29))  # padrão: últimos 30 dias
    if inicio_d > fim_d:
        inicio_d, fim_d = fim_d, inicio_d
    if (fim_d - inicio_d).days > 365:
        inicio_d = fim_d - timedelta(days=365)
    ind = calcular(db, h.id, inicio_d, fim_d)
    atalhos = [
        ("Últimos 7 dias", hoje - timedelta(days=6), hoje),
        ("Últimos 30 dias", hoje - timedelta(days=29), hoje),
        ("Últimos 90 dias", hoje - timedelta(days=89), hoje),
        ("Próximos 30 dias", hoje, hoje + timedelta(days=29)),
    ]
    graficos = {
        "diaria": {
            "rotulos": [d.strftime("%d/%m") for d, _ in ind["ocupacao_diaria"]],
            "fds": [d.weekday() in (4, 5) for d, _ in ind["ocupacao_diaria"]],
            "valores": [round(v * 100, 1) for _, v in ind["ocupacao_diaria"]],
        },
        "semana": {
            "rotulos": [d for d, _ in ind["ocupacao_semana"]],
            "valores": [round(v * 100, 1) if v is not None else None for _, v in ind["ocupacao_semana"]],
        },
        "canais": {
            "rotulos": [c["nome"] for c in ind["canais"]],
            "liquida": [round(c["liquida"], 2) for c in ind["canais"]],
            "comissao": [round(c["bruta"] - c["liquida"], 2) for c in ind["canais"]],
            "bruta": [round(c["bruta"], 2) for c in ind["canais"]],
        },
    }
    return render(request, db, "painel.html", hotel=h, pagina="painel", ind=ind, graficos=graficos,
                  atalhos=atalhos)

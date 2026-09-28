"""Aplicação FastAPI: monta as rotas de cada tela.

Subir o servidor:  uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app import db as banco
from app import relogio
from app.db import get_db
from app.models import Hotel, Reserva, Unidade
from app.rotas import cadastro, chat, equipe, ical, painel, reservas
from app.servicos.disponibilidade import proxima_sexta
from app.web import RAIZ, render


@asynccontextmanager
async def ciclo_de_vida(_app):
    banco.criar_tabelas()  # banco vazio não quebra; os dados vêm do seed.py
    yield


app = FastAPI(title="Recepção 24h — protótipo", lifespan=ciclo_de_vida)
app.mount("/static", StaticFiles(directory=str(RAIZ / "static")), name="static")


@app.get("/")
def inicio(request: Request, db=Depends(get_db)):
    hoteis = db.query(Hotel).order_by(Hotel.id).all()
    resumo = {
        h.id: {
            "unidades": db.query(Unidade).filter_by(hotel_id=h.id, ativa=True).count(),
            "reservas": db.query(Reserva).filter_by(hotel_id=h.id).count(),
        }
        for h in hoteis
    }
    sexta = proxima_sexta(relogio.hoje(db)) + timedelta(days=7)
    return render(request, db, "index.html", hotel=hoteis[0] if hoteis else None, pagina="inicio",
                  lista_hoteis=hoteis, resumo=resumo, sexta_demo=sexta, domingo_demo=sexta + timedelta(days=2))


app.include_router(chat.router)
app.include_router(equipe.router)
app.include_router(reservas.router)
app.include_router(cadastro.router)
app.include_router(painel.router)
app.include_router(ical.router)

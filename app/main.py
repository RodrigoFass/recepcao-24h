"""Aplicação FastAPI: monta as rotas de cada tela.

Subir o servidor:  uvicorn app.main:app --reload

Enquanto o servidor roda, um agendador confere a cada 30 s as mensagens da
jornada que já venceram e as envia (na produção, papel do n8n).
AGENDADOR=0 desliga (os testes controlam o tempo sozinhos).
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import auth, relogio
from app import db as banco
from app.db import get_db
from app.models import Hotel
from app.rotas import cadastro, chat, contas, equipe, ical, painel, reservas
from app.servicos.jornada import processar_ate
from app.web import RAIZ, redirecionar, render

log = logging.getLogger("recepcao24h.agendador")
INTERVALO_AGENDADOR = 30


def processar_vencidas():
    """Envia as mensagens agendadas que já venceram (e aplica os prazos de resposta)."""
    with banco.sessao() as db:
        resumo = processar_ate(db, relogio.agora(db))
        db.commit()
    return resumo


async def _agendador():
    while True:
        try:
            await asyncio.to_thread(processar_vencidas)
        except Exception:  # noqa: BLE001  (o agendador não pode parar por um erro pontual)
            log.exception("Falha ao processar as mensagens agendadas")
        await asyncio.sleep(INTERVALO_AGENDADOR)


@asynccontextmanager
async def ciclo_de_vida(_app):
    banco.criar_tabelas()  # banco vazio não quebra; os dados vêm do seed.py
    tarefa = None
    if os.environ.get("AGENDADOR", "1") != "0":
        tarefa = asyncio.create_task(_agendador())
    yield
    if tarefa:
        tarefa.cancel()


app = FastAPI(title="Recepção 24h", lifespan=ciclo_de_vida)
app.mount("/static", StaticFiles(directory=str(RAIZ / "static")), name="static")


@app.exception_handler(auth.PrecisaLogin)
def precisa_login(request: Request, _erro):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"erro": "faça login"}, status_code=401)
    return redirecionar("/entrar")


@app.exception_handler(StarletteHTTPException)
def erro_http(request: Request, erro: StarletteHTTPException):
    """Nas telas, uma página de erro; na API e no iCal, a resposta padrão em JSON."""
    if request.url.path.startswith(("/api/", "/ical/", "/static/")):
        return JSONResponse({"detail": erro.detail}, status_code=erro.status_code)
    titulos = {403: "Acesso restrito", 404: "Página não encontrada"}
    with banco.sessao() as db:
        resposta = render(request, db, "erro.html", titulo_erro=titulos.get(erro.status_code, "Algo deu errado"),
                          detalhe=erro.detail)
    resposta.status_code = erro.status_code
    return resposta


@app.get("/")
def inicio(request: Request, db=Depends(get_db)):
    usuario = auth.usuario_logado(request, db)
    if usuario:
        return redirecionar(contas.destino_da_conta(usuario))
    hoteis = db.query(Hotel).order_by(Hotel.id).all()
    return render(request, db, "index.html", pagina="inicio", lista_hoteis=hoteis)


app.include_router(contas.router)
app.include_router(chat.router)
app.include_router(equipe.router)
app.include_router(reservas.router)
app.include_router(cadastro.router)
app.include_router(painel.router)
app.include_router(ical.router)

"""Atendimento do hóspede (o lado do hóspede, que na versão final é o WhatsApp do
hotel) e a API usada por ele. É público: não depende do login da equipe."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.bot.ferramentas import reserva_ativa_do_telefone
from app.db import get_db
from app.formatacao import formatar_telefone
from app.servicos.conversas import (
    conversa_ativa,
    hospede_do_telefone,
    mensagens_do_telefone,
    receber_mensagem_hospede,
)
from app.web import obter_hotel, render

router = APIRouter()


@router.get("/chat")
def tela_chat(request: Request, hotel: str | None = None, telefone: str | None = None, db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    return render(request, db, "chat.html", pagina="chat", hotel_chat=h,
                  telefone=formatar_telefone(telefone) if telefone else "")


def conversa_json(db, hotel, telefone: str) -> dict:
    tel = formatar_telefone(telefone)
    conv = conversa_ativa(db, hotel.id, tel, criar=False)
    hosp = hospede_do_telefone(db, hotel.id, tel)
    reserva = reserva_ativa_do_telefone(db, hotel.id, tel)
    return {
        "telefone": tel,
        "status": conv.status if conv else "bot",
        "motivo": conv.motivo_escalonamento if conv and conv.status == "humano" else None,
        "hospede": hosp.nome if hosp else None,
        "reserva": (
            f"{reserva.unidade.tipo.nome} {reserva.unidade.identificacao}, "
            f"{reserva.check_in:%d/%m} a {reserva.check_out:%d/%m}"
            if reserva
            else None
        ),
        "mensagens": [
            {"id": m.id, "autor": m.autor, "texto": m.texto, "hora": m.criada_em.strftime("%d/%m %H:%M")}
            for m in mensagens_do_telefone(db, hotel.id, tel)
        ],
    }


@router.get("/api/conversa")
def api_conversa(hotel: str, telefone: str, db=Depends(get_db)):
    return conversa_json(db, obter_hotel(db, hotel), telefone)


class NovaMensagem(BaseModel):
    hotel: str
    telefone: str
    texto: str


@router.post("/api/mensagem")
def api_mensagem(dados: NovaMensagem, db=Depends(get_db)):
    h = obter_hotel(db, dados.hotel)
    if dados.texto.strip():
        receber_mensagem_hospede(db, h, dados.telefone, dados.texto)
    return conversa_json(db, h, dados.telefone)

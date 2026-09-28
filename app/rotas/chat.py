"""Tela de chat (simula o WhatsApp do hóspede) e a API usada por ela."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app import relogio
from app.bot.ferramentas import reserva_ativa_do_telefone
from app.db import get_db
from app.formatacao import formatar_telefone
from app.models import Conversa, Hospede, Reserva
from app.servicos.conversas import (
    conversa_ativa,
    hospede_do_telefone,
    mensagens_do_telefone,
    receber_mensagem_hospede,
)
from app.servicos.disponibilidade import proxima_sexta
from app.web import obter_hotel, render

router = APIRouter()


def listar_contatos(db, hotel) -> dict[str, list[tuple[str, str]]]:
    """Telefones para o seletor: hóspedes com reserva ativa, estadias recentes e outros contatos."""
    hoje = relogio.hoje(db)
    base = (
        db.query(Reserva, Hospede)
        .join(Hospede, Reserva.hospede_id == Hospede.id)
        .filter(Reserva.hotel_id == hotel.id, Hospede.telefone.is_not(None), Reserva.status != "cancelada")
    )
    vistos: set[str] = set()
    ativos, anteriores, outros = [], [], []
    for r, h in base.filter(Reserva.check_out >= hoje).order_by(Reserva.check_in):
        if h.telefone not in vistos:
            vistos.add(h.telefone)
            if r.check_out == hoje:
                quando = "sai hoje"
            elif r.check_in < hoje:
                quando = f"hospedado até {r.check_out:%d/%m}"
            elif r.check_in == hoje:
                quando = "chega hoje"
            else:
                quando = f"chega {r.check_in:%d/%m}"
            ativos.append((h.telefone, f"{h.nome} · {quando} · {r.unidade.identificacao}"))
    for r, h in base.filter(Reserva.check_out < hoje).order_by(Reserva.check_out.desc()).limit(40):
        if h.telefone not in vistos and len(anteriores) < 20:
            vistos.add(h.telefone)
            anteriores.append((h.telefone, f"{h.nome} · saiu {r.check_out:%d/%m}"))
    for c in db.query(Conversa).filter_by(hotel_id=hotel.id).order_by(Conversa.atualizada_em.desc()).limit(60):
        if c.telefone not in vistos and len(outros) < 15:
            vistos.add(c.telefone)
            outros.append((c.telefone, "contato sem reserva"))
    return {"Com reserva ativa": ativos, "Estadias recentes": anteriores, "Outros contatos": outros}


def sugestoes(hoje) -> list[str]:
    sexta = proxima_sexta(hoje) + timedelta(days=7)
    return [
        "Aceita pet?",
        "Qual o horário do check-in?",
        "Posso fazer late checkout?",
        "Qual a senha do wifi?",
        f"Tem vaga de {sexta:%d/%m} a {sexta + timedelta(days=2):%d/%m}?",
        "Consegue um desconto?",
        "Chego às 23h",
        "Você é humano?",
        "Me ajuda a fazer meu trabalho da faculdade?",
    ]


@router.get("/chat")
def tela_chat(request: Request, hotel: str | None = None, telefone: str | None = None, db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    contatos = listar_contatos(db, h)
    telefone = formatar_telefone(telefone) if telefone else ""
    return render(
        request,
        db,
        "chat.html",
        hotel=h,
        pagina="chat",
        contatos=contatos,
        telefone=telefone,
        telefone_listado=any(tel == telefone for itens in contatos.values() for tel, _ in itens),
        sugestoes=sugestoes(relogio.hoje(db)),
    )


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

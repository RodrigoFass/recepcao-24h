"""Conversas: entrada das mensagens do hóspede, respostas do bot e da equipe.

No protótipo, o chat web faz o papel do WhatsApp: o hóspede é identificado
pelo telefone, e cada hotel tem suas próprias conversas.
"""
from datetime import datetime

from app import relogio
from app.bot import textos
from app.formatacao import formatar_telefone
from app.models import Conversa, Hospede, Mensagem


def hospede_do_telefone(db, hotel_id: int, telefone: str) -> Hospede | None:
    return (
        db.query(Hospede)
        .filter_by(hotel_id=hotel_id, telefone=telefone)
        .order_by(Hospede.id.desc())
        .first()
    )


def conversa_ativa(db, hotel_id: int, telefone: str, criar: bool = True, momento: datetime | None = None):
    """Última conversa aberta (bot ou humano) do telefone; cria uma se não houver."""
    telefone = formatar_telefone(telefone)
    conv = (
        db.query(Conversa)
        .filter(Conversa.hotel_id == hotel_id, Conversa.telefone == telefone, Conversa.status != "encerrada")
        .order_by(Conversa.id.desc())
        .first()
    )
    if conv is None and criar:
        momento = momento or relogio.agora(db)
        hosp = hospede_do_telefone(db, hotel_id, telefone)
        conv = Conversa(
            hotel_id=hotel_id,
            hospede_id=hosp.id if hosp else None,
            telefone=telefone,
            status="bot",
            criada_em=momento,
            atualizada_em=momento,
        )
        db.add(conv)
        db.flush()
    return conv


def registrar(db, conversa: Conversa, autor: str, texto: str, momento: datetime | None = None) -> Mensagem:
    momento = momento or relogio.agora(db)
    msg = Mensagem(conversa=conversa, autor=autor, texto=texto, criada_em=momento)
    db.add(msg)
    if momento > conversa.atualizada_em:
        conversa.atualizada_em = momento
    db.flush()
    return msg


def receber_mensagem_hospede(db, hotel, telefone: str, texto: str, modo: str | None = None):
    """Grava a mensagem do hóspede e, se a conversa estiver com o bot, responde.

    Devolve (conversa, resposta). A resposta é None quando a conversa está com
    a equipe: nesse caso o bot fica em silêncio. `modo` ("demo"/"ia") força um
    modo do bot; sem ele, vale a configuração do ambiente.
    """
    from app import bot
    from app.servicos import pos_estadia

    texto = (texto or "").strip()
    conv = conversa_ativa(db, hotel.id, telefone)
    registrar(db, conv, "hospede", texto)
    db.commit()  # a mensagem do hóspede fica gravada mesmo se o bot falhar

    if conv.status == "humano":
        return conv, None

    ja_se_apresentou = any(m.autor == "bot" for m in conv.mensagens[:-1])
    resposta = pos_estadia.tratar_resposta_pesquisa(db, hotel, conv, texto)
    if resposta is None:
        resposta = bot.responder(db, hotel, conv, texto, forcar_modo=modo)
    if not ja_se_apresentou and "assistente virtual" not in resposta.lower():
        resposta = f"{textos.apresentacao(hotel)} {resposta}"
    registrar(db, conv, "bot", resposta)
    db.commit()
    return conv, resposta


def responder_como_equipe(db, conversa: Conversa, texto: str):
    registrar(db, conversa, "equipe", texto.strip())
    db.commit()


def devolver_ao_bot(db, conversa: Conversa):
    """A equipe resolveu: o bot volta a responder. O motivo fica registrado
    (a conversa continua contando como escalada no painel)."""
    conversa.status = "bot"
    registrar(db, conversa, "sistema", "A equipe devolveu a conversa ao assistente virtual.")
    db.commit()


def encerrar(db, conversa: Conversa):
    conversa.status = "encerrada"
    conversa.atualizada_em = relogio.agora(db)
    db.commit()


def mensagens_do_telefone(db, hotel_id: int, telefone: str) -> list[Mensagem]:
    """Histórico completo do telefone neste hotel (todas as conversas)."""
    telefone = formatar_telefone(telefone)
    return (
        db.query(Mensagem)
        .join(Conversa)
        .filter(Conversa.hotel_id == hotel_id, Conversa.telefone == telefone)
        .order_by(Mensagem.criada_em, Mensagem.id)
        .all()
    )

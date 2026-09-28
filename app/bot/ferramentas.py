"""Ferramentas do bot, usadas pelos dois modos.

O hotel vem sempre da conversa: nenhuma ferramenta recebe hotel_id como
parâmetro, então o bot não tem como consultar dados de outro hotel.
"""
import re
from datetime import date

from app import relogio
from app.bot import textos
from app.formatacao import normalizar
from app.models import Alerta, Hospede, Hotel, Reserva, TipoAcomodacao
from app.servicos import disponibilidade


def _tipo_por_nome(db, hotel_id: int, nome: str | None):
    if not nome:
        return None
    alvo = normalizar(nome)
    tipos = db.query(TipoAcomodacao).filter_by(hotel_id=hotel_id).all()
    for t in tipos:
        if normalizar(t.nome) == alvo:
            return t
    for t in tipos:
        n = normalizar(t.nome)
        if alvo in n or n in alvo:
            return t
    # palavra que só existe no nome de um tipo (ex.: "familia")
    for t in tipos:
        outras = set().union(*(set(normalizar(o.nome).split()) for o in tipos if o.id != t.id)) if len(tipos) > 1 else set()
        distintas = set(normalizar(t.nome).split()) - outras
        if distintas & set(alvo.split()):
            return t
    return None


def consultar_disponibilidade(db, conversa, check_in: date, check_out: date, tipo: str | None = None,
                              pessoas: int | None = None) -> dict:
    tipo_obj = _tipo_por_nome(db, conversa.hotel_id, tipo)
    if tipo and tipo_obj is None:
        nomes = [t.nome for t in db.query(TipoAcomodacao).filter_by(hotel_id=conversa.hotel_id)]
        return {"erro": f"Tipo de acomodação não encontrado. Tipos deste hotel: {', '.join(nomes)}."}
    return disponibilidade.consultar(
        db,
        conversa.hotel_id,
        check_in,
        check_out,
        tipo_obj.id if tipo_obj else None,
        pessoas,
        hoje=relogio.hoje(db),
    )


def escalar_para_humano(db, conversa, motivo: str) -> dict:
    """Passa a conversa para a equipe: o bot para de responder nela."""
    ultima = next((m.texto for m in reversed(conversa.mensagens) if m.autor == "hospede"), "")
    conversa.status = "humano"
    conversa.motivo_escalonamento = motivo
    conversa.atualizada_em = relogio.agora(db)
    db.add(
        Alerta(
            hotel_id=conversa.hotel_id,
            tipo="escalonamento",
            referencia=f"conversa:{conversa.id}",
            texto=f"{motivo}: \"{ultima[:160]}\" — {conversa.telefone}",
            resolvido=False,
            criado_em=relogio.agora(db),
        )
    )
    db.flush()
    return {"ok": True, "mensagem_ao_hospede": textos.escalonamento(db.get(Hotel, conversa.hotel_id))}


def reserva_ativa_do_telefone(db, hotel_id: int, telefone: str) -> Reserva | None:
    """Próxima reserva confirmada (ou em andamento) do telefone, neste hotel."""
    hoje = relogio.hoje(db)
    return (
        db.query(Reserva)
        .join(Hospede, Reserva.hospede_id == Hospede.id)
        .filter(
            Reserva.hotel_id == hotel_id,
            Hospede.telefone == telefone,
            Reserva.status == "confirmada",
            Reserva.check_out >= hoje,
        )
        .order_by(Reserva.check_in)
        .first()
    )


def registrar_hora_chegada(db, conversa, hora: str) -> dict:
    """Grava a hora prevista de chegada ("HH:MM") na reserva ativa do telefone."""
    achou = re.fullmatch(r"\s*(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*", (hora or "").lower())
    if not achou:
        return {"ok": False, "erro": "Hora inválida. Use o formato HH:MM."}
    h, m = int(achou.group(1)), int(achou.group(2) or 0)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return {"ok": False, "erro": "Hora inválida. Use o formato HH:MM."}
    reserva = reserva_ativa_do_telefone(db, conversa.hotel_id, conversa.telefone)
    if reserva is None:
        return {"ok": False, "erro": "Não há reserva ativa para este telefone neste hotel."}
    reserva.hora_prevista_chegada = f"{h:02d}:{m:02d}"
    db.flush()
    return {
        "ok": True,
        "reserva_id": reserva.id,
        "check_in": reserva.check_in.isoformat(),
        "hora_prevista_chegada": reserva.hora_prevista_chegada,
    }

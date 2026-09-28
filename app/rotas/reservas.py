"""Detalhes da reserva e linha do tempo da jornada."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app.db import get_db
from app.models import Alerta, Hotel, MensagemAgendada, Reserva
from app.servicos import jornada, reservas
from app.web import redirecionar, render

router = APIRouter()


def _reserva(db, reserva_id: int) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(404, "Reserva não encontrada.")
    return reserva


@router.get("/reservas/{reserva_id}")
def tela_reserva(request: Request, reserva_id: int, db=Depends(get_db)):
    reserva = _reserva(db, reserva_id)
    hotel = db.get(Hotel, reserva.hotel_id)
    agendadas = sorted(reserva.mensagens_agendadas, key=lambda m: (m.enviar_em, m.id))
    proxima = next((m for m in agendadas if m.status == "pendente" and m.meio == "whatsapp"), None)
    alertas = (
        db.query(Alerta)
        .filter_by(hotel_id=hotel.id, referencia=f"reserva:{reserva.id}")
        .order_by(Alerta.criado_em.desc())
        .all()
    )
    return render(
        request,
        db,
        "reserva.html",
        hotel=hotel,
        pagina="equipe",
        reserva=reserva,
        agendadas=agendadas,
        proxima=proxima,
        alertas=alertas,
        proximo_evento=jornada.proximo_evento(db, reserva_id=reserva.id),
    )


@router.post("/reservas/{reserva_id}/cancelar")
def cancelar(reserva_id: int, db=Depends(get_db)):
    reserva = _reserva(db, reserva_id)
    reservas.cancelar_reserva(db, reserva)
    return redirecionar(f"/reservas/{reserva.id}", msg="Reserva cancelada; as mensagens pendentes foram canceladas.")


@router.post("/reservas/{reserva_id}/mensagens/{mensagem_id}/enviada")
def marcar_enviada(reserva_id: int, mensagem_id: int, db=Depends(get_db)):
    """Mensagens de OTA são copiadas à mão para o chat da OTA; a equipe marca quando enviou."""
    reserva = _reserva(db, reserva_id)
    msg = db.get(MensagemAgendada, mensagem_id)
    if msg is None or msg.reserva_id != reserva.id:
        raise HTTPException(404, "Mensagem não encontrada nesta reserva.")
    msg.status = "enviada"
    db.commit()
    return redirecionar(f"/reservas/{reserva.id}", msg="Mensagem marcada como enviada pela OTA.")

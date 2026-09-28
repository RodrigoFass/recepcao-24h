"""Tela da equipe: conversas escaladas, chegadas e saídas, alertas, valores
pendentes, reserva direta e controles do relógio simulado."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app import relogio
from app.db import get_db
from app.formatacao import data_br, ler_moeda
from app.models import Alerta, CalendarioExterno, Canal, Conversa, Reserva, TipoAcomodacao, Unidade
from app.servicos import conversas, jornada, reservas
from app.web import obter_hotel, redirecionar, render

router = APIRouter()


def _conversa(db, hotel, conversa_id: int) -> Conversa:
    conv = db.get(Conversa, conversa_id)
    if conv is None or conv.hotel_id != hotel.id:
        raise HTTPException(404, "Conversa não encontrada neste hotel.")
    return conv


def _link_referencia(db, hotel, referencia: str | None) -> str | None:
    if not referencia or ":" not in referencia:
        return None
    tipo, _, ident = referencia.partition(":")
    if tipo == "reserva":
        return f"/reservas/{ident}"
    if tipo == "conversa":
        conv = db.get(Conversa, int(ident))
        if conv and conv.hotel_id == hotel.id:
            return f"/chat?hotel={hotel.slug}&telefone={conv.telefone}"
    return None


@router.get("/equipe")
def tela_equipe(request: Request, hotel: str | None = None, db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    hoje = relogio.hoje(db)
    escaladas = (
        db.query(Conversa).filter_by(hotel_id=h.id, status="humano").order_by(Conversa.atualizada_em.desc()).all()
    )
    chegadas = (
        db.query(Reserva)
        .filter(Reserva.hotel_id == h.id, Reserva.check_in == hoje, Reserva.status == "confirmada")
        .order_by(Reserva.hora_prevista_chegada.is_(None), Reserva.hora_prevista_chegada)
        .all()
    )
    saidas = (
        db.query(Reserva)
        .filter(Reserva.hotel_id == h.id, Reserva.check_out == hoje, Reserva.status != "cancelada")
        .all()
    )
    alertas = (
        db.query(Alerta)
        .filter(Alerta.hotel_id == h.id, Alerta.resolvido.is_(False), Alerta.tipo != "valor_pendente")
        .order_by(Alerta.criado_em.desc())
        .all()
    )
    pendentes = (
        db.query(Reserva)
        .filter(Reserva.hotel_id == h.id, Reserva.valor_total.is_(None), Reserva.status != "cancelada")
        .order_by(Reserva.check_in.desc())
        .all()
    )
    return render(
        request,
        db,
        "equipe.html",
        hotel=h,
        pagina="equipe",
        escaladas=escaladas,
        chegadas=chegadas,
        saidas=saidas,
        alertas=[(a, _link_referencia(db, h, a.referencia)) for a in alertas],
        pendentes=pendentes,
        tipos=db.query(TipoAcomodacao).filter_by(hotel_id=h.id).order_by(TipoAcomodacao.id).all(),
        unidades=db.query(Unidade).filter_by(hotel_id=h.id, ativa=True).order_by(Unidade.id).all(),
        canais_diretos=[c for c in db.query(Canal).filter_by(hotel_id=h.id).order_by(Canal.id) if c.direto],
        canais_ota=[c for c in db.query(Canal).filter_by(hotel_id=h.id).order_by(Canal.id) if not c.direto],
        proximo_evento=jornada.proximo_evento(db, hotel_id=h.id),
        calendarios=db.query(CalendarioExterno).filter_by(hotel_id=h.id)
        .order_by(CalendarioExterno.ultima_sincronizacao.desc()).all(),
        assinatura=assinatura_pendencias(db, h),
        sugestao_check_in=hoje + timedelta(days=5),
        sugestao_check_out=hoje + timedelta(days=7),
    )


def assinatura_pendencias(db, hotel) -> str:
    """Muda quando chega mensagem numa conversa escalada ou surge um alerta (a tela avisa)."""
    conversas = db.query(Conversa).filter_by(hotel_id=hotel.id, status="humano").all()
    ultima = max((m.id for c in conversas for m in c.mensagens), default=0)
    alertas = db.query(Alerta).filter_by(hotel_id=hotel.id, resolvido=False).count()
    return f"{len(conversas)}-{ultima}-{alertas}"


@router.get("/api/equipe/pendencias")
def api_pendencias(hotel: str, db=Depends(get_db)):
    return {"assinatura": assinatura_pendencias(db, obter_hotel(db, hotel))}


# ------------------------------------------------------------------ conversas

@router.post("/equipe/conversas/{conversa_id}/responder")
def responder(conversa_id: int, hotel: str = Form(...), texto: str = Form(...), db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    conv = _conversa(db, h, conversa_id)
    if texto.strip():
        conversas.responder_como_equipe(db, conv, texto)
    return redirecionar("/equipe", hotel=h.slug, msg="Resposta enviada ao hóspede.")


@router.post("/equipe/conversas/{conversa_id}/devolver")
def devolver(conversa_id: int, hotel: str = Form(...), db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    conversas.devolver_ao_bot(db, _conversa(db, h, conversa_id))
    _resolver_alertas(db, h, f"conversa:{conversa_id}", "escalonamento")
    return redirecionar("/equipe", hotel=h.slug, msg="Conversa devolvida ao assistente virtual.")


@router.post("/equipe/conversas/{conversa_id}/encerrar")
def encerrar(conversa_id: int, hotel: str = Form(...), db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    conversas.encerrar(db, _conversa(db, h, conversa_id))
    _resolver_alertas(db, h, f"conversa:{conversa_id}", "escalonamento")
    return redirecionar("/equipe", hotel=h.slug, msg="Conversa encerrada.")


def _resolver_alertas(db, hotel, referencia: str, tipo: str):
    for a in db.query(Alerta).filter_by(hotel_id=hotel.id, referencia=referencia, tipo=tipo, resolvido=False):
        a.resolvido = True
    db.commit()


# ------------------------------------------------------------------ alertas e valores

@router.post("/equipe/alertas/{alerta_id}/resolver")
def resolver_alerta(alerta_id: int, hotel: str = Form(...), db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    alerta = db.get(Alerta, alerta_id)
    if alerta is None or alerta.hotel_id != h.id:
        raise HTTPException(404, "Alerta não encontrado neste hotel.")
    alerta.resolvido = True
    db.commit()
    return redirecionar("/equipe", hotel=h.slug, msg="Alerta resolvido.")


@router.post("/equipe/reservas/{reserva_id}/valor")
def completar_valor(reserva_id: int, hotel: str = Form(...), valor: str = Form(""), voltar: str = Form("/equipe"),
                    db=Depends(get_db)):
    h = obter_hotel(db, hotel)
    reserva = db.get(Reserva, reserva_id)
    if reserva is None or reserva.hotel_id != h.id:
        raise HTTPException(404, "Reserva não encontrada neste hotel.")
    destino = voltar if voltar.startswith("/") else "/equipe"
    try:
        numero = ler_moeda(valor)
        if numero is None:
            raise reservas.ErroReserva("Informe o valor.")
        reservas.completar_valor(db, reserva, numero)
    except (ValueError, reservas.ErroReserva) as erro:
        return redirecionar(destino, hotel=h.slug, erro=f"Valor inválido: {erro}")
    return redirecionar(destino, hotel=h.slug, msg=f"Valor da reserva #{reserva.id} registrado.")


# ------------------------------------------------------------------ reserva direta

@router.post("/equipe/reservas")
def criar_reserva_direta(
    hotel: str = Form(...),
    nome: str = Form(...),
    telefone: str = Form(""),
    email: str = Form(""),
    consentimento: str | None = Form(None),
    canal_id: int = Form(...),
    acomodacao: str = Form(...),
    check_in: str = Form(...),
    check_out: str = Form(...),
    num_hospedes: int = Form(2),
    valor: str = Form(""),
    db=Depends(get_db),
):
    h = obter_hotel(db, hotel)
    try:
        ci, co = date.fromisoformat(check_in), date.fromisoformat(check_out)
        canal = db.get(Canal, canal_id)
        if canal is None or canal.hotel_id != h.id or not canal.direto:
            raise reservas.ErroReserva("Escolha um canal direto (sem comissão).")
        tipo, _, ident = acomodacao.partition(":")
        if tipo == "tipo":
            unidade = reservas.escolher_unidade(db, h, int(ident), ci, co)
        else:
            unidade = db.get(Unidade, int(ident))
            if unidade is None or unidade.hotel_id != h.id:
                raise reservas.ErroReserva("Unidade não encontrada.")
        numero = ler_moeda(valor)
        if numero is None:
            numero = reservas.valor_sugerido(unidade.tipo.tarifa_base, ci, co)
        hospede = reservas.criar_hospede(db, h, nome, telefone, email, consentimento=bool(consentimento))
        reserva = reservas.criar_reserva(
            db,
            h,
            unidade_id=unidade.id,
            canal_id=canal.id,
            check_in=ci,
            check_out=co,
            hospede=hospede,
            num_hospedes=num_hospedes,
            valor_total=numero,
        )
        db.commit()
    except (ValueError, reservas.ErroReserva) as erro:
        db.rollback()
        return redirecionar("/equipe", hotel=h.slug, erro=f"Reserva não criada: {erro}")
    return redirecionar(f"/reservas/{reserva.id}", msg="Reserva direta criada. Veja a jornada de mensagens abaixo.")


# ------------------------------------------------------------------ relógio simulado

@router.post("/relogio/avancar")
def avancar_relogio(
    hotel: str = Form(...),
    passo: str = Form(...),
    reserva_id: int | None = Form(None),
    voltar: str = Form("/equipe"),
    db=Depends(get_db),
):
    h = obter_hotel(db, hotel)
    destino = voltar if voltar.startswith("/") else "/equipe"
    if passo == "1h":
        novo = relogio.avancar(db, timedelta(hours=1))
    elif passo == "1d":
        novo = relogio.avancar(db, timedelta(days=1))
    elif passo == "proxima":
        evento = jornada.proximo_evento(db, hotel_id=h.id, reserva_id=reserva_id)
        if evento is None:
            return redirecionar(destino, hotel=h.slug, erro="Não há mensagens agendadas pela frente.")
        novo = relogio.avancar_ate(db, evento)
    else:
        raise HTTPException(400, "Passo inválido.")
    return redirecionar(destino, hotel=h.slug, msg=f"Relógio simulado em {data_br(novo)}.")

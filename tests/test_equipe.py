"""Etapa 3: tela da equipe, escalonamento e reserva direta."""
from datetime import timedelta
from urllib.parse import unquote_plus

import pytest

from app import relogio
from app.models import Alerta, Canal, Conversa, Hotel, Reserva, TipoAcomodacao
from app.servicos.reservas import ErroReserva, criar_reserva, valor_sugerido


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def _mensagem(client, slug, tel, texto):
    return client.post("/api/mensagem", json={"hotel": slug, "telefone": tel, "texto": texto}).json()


def test_fluxo_escalonamento_equipe_devolve_ao_bot(client, db):
    tel = "(27) 95555-0001"
    dados = _mensagem(client, "mare-alta", tel, "Consegue um desconto de 50%?")
    assert dados["status"] == "humano"

    pagina = client.get("/equipe?hotel=mare-alta").text
    assert "Consegue um desconto de 50%?" in pagina
    assert "Consegue um desconto de 50%?" not in client.get("/equipe?hotel=serra-verde").text

    conv = db.query(Conversa).filter_by(telefone=tel).one()
    r = client.post(
        f"/equipe/conversas/{conv.id}/responder",
        data={"hotel": "mare-alta", "texto": "Oi! Aqui é a Carla, da recepção."},
        follow_redirects=False,
    )
    assert r.status_code == 303
    dados = client.get("/api/conversa", params={"hotel": "mare-alta", "telefone": tel}).json()
    assert dados["mensagens"][-1]["autor"] == "equipe"
    assert dados["status"] == "humano"

    client.post(f"/equipe/conversas/{conv.id}/devolver", data={"hotel": "mare-alta"})
    dados = _mensagem(client, "mare-alta", tel, "Qual a senha do wifi?")
    assert dados["status"] == "bot"
    assert "marealta2026" in dados["mensagens"][-1]["texto"]

    db.expire_all()
    alerta = db.query(Alerta).filter_by(referencia=f"conversa:{conv.id}", tipo="escalonamento").one()
    assert alerta.resolvido


def test_equipe_nao_mexe_em_conversa_de_outro_hotel(client, db):
    tel = "(27) 95555-0002"
    _mensagem(client, "serra-verde", tel, "Quero falar com o gerente")
    conv = db.query(Conversa).filter_by(telefone=tel).one()
    r = client.post(f"/equipe/conversas/{conv.id}/responder", data={"hotel": "mare-alta", "texto": "oi"})
    assert r.status_code == 404


def test_criar_reserva_direta(client, db):
    mare = _hotel(db, "mare-alta")
    hoje = relogio.hoje(db)
    tipo = db.query(TipoAcomodacao).filter_by(hotel_id=mare.id, nome="Suíte Casal").one()
    whatsapp = db.query(Canal).filter_by(hotel_id=mare.id, tipo="whatsapp").one()
    ci, co = hoje + timedelta(days=40), hoje + timedelta(days=42)
    r = client.post(
        "/equipe/reservas",
        data={
            "hotel": "mare-alta", "nome": "Ana Teste", "telefone": "27 95555-0100", "consentimento": "1",
            "canal_id": whatsapp.id, "acomodacao": f"tipo:{tipo.id}", "check_in": ci.isoformat(),
            "check_out": co.isoformat(), "num_hospedes": 2, "valor": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    assert r.headers["location"].startswith("/reservas/")
    reserva_id = int(r.headers["location"].split("/")[2].split("?")[0])
    reserva = db.get(Reserva, reserva_id)
    assert reserva.hospede.nome == "Ana Teste"
    assert reserva.hospede.telefone == "(27) 95555-0100"
    assert reserva.hospede.consentimento_whatsapp_em is not None
    assert reserva.valor_total == valor_sugerido(tipo.tarifa_base, ci, co)
    assert reserva.origem == "manual"
    assert "Ana Teste" in client.get(f"/reservas/{reserva_id}").text


def test_reserva_manual_sobreposta_e_recusada(client, db):
    mare = _hotel(db, "mare-alta")
    hoje = relogio.hoje(db)
    existente = (
        db.query(Reserva)
        .filter(Reserva.hotel_id == mare.id, Reserva.check_in > hoje, Reserva.status == "confirmada")
        .first()
    )
    whatsapp = db.query(Canal).filter_by(hotel_id=mare.id, tipo="whatsapp").one()
    with pytest.raises(ErroReserva):
        criar_reserva(
            db, mare, unidade_id=existente.unidade_id, canal_id=whatsapp.id,
            check_in=existente.check_in, check_out=existente.check_out,
        )
    db.rollback()

    antes = db.query(Reserva).filter_by(hotel_id=mare.id).count()
    r = client.post(
        "/equipe/reservas",
        data={
            "hotel": "mare-alta", "nome": "Conflito", "telefone": "", "canal_id": whatsapp.id,
            "acomodacao": f"un:{existente.unidade_id}", "check_in": existente.check_in.isoformat(),
            "check_out": (existente.check_in + timedelta(days=1)).isoformat(),
        },
        follow_redirects=False,
    )
    assert "já está reservada" in unquote_plus(r.headers["location"])
    db.expire_all()
    assert db.query(Reserva).filter_by(hotel_id=mare.id).count() == antes


def test_completar_valor_pendente(client, db):
    mare = _hotel(db, "mare-alta")
    reserva = db.query(Reserva).filter_by(hotel_id=mare.id, valor_total=None).first()
    alerta = db.query(Alerta).filter_by(referencia=f"reserva:{reserva.id}", tipo="valor_pendente").one()
    assert not alerta.resolvido
    client.post(f"/equipe/reservas/{reserva.id}/valor", data={"hotel": "mare-alta", "valor": "1.234,56"})
    db.expire_all()
    assert db.get(Reserva, reserva.id).valor_total == 1234.56
    assert db.get(Alerta, alerta.id).resolvido


def test_resolver_alerta(client, db):
    mare = _hotel(db, "mare-alta")
    alerta = db.query(Alerta).filter_by(hotel_id=mare.id, resolvido=False).first()
    client.post(f"/equipe/alertas/{alerta.id}/resolver", data={"hotel": "mare-alta"})
    db.expire_all()
    assert db.get(Alerta, alerta.id).resolvido
    # alerta de um hotel não é resolvido pela tela do outro
    outro = db.query(Alerta).filter_by(hotel_id=mare.id, resolvido=False).first()
    r = client.post(f"/equipe/alertas/{outro.id}/resolver", data={"hotel": "serra-verde"})
    assert r.status_code == 404


def test_paginas_da_equipe_e_da_reserva_abrem(client, db):
    for slug in ("mare-alta", "serra-verde"):
        assert client.get(f"/equipe?hotel={slug}").status_code == 200
    reserva = db.query(Reserva).first()
    assert client.get(f"/reservas/{reserva.id}").status_code == 200

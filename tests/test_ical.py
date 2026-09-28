"""Etapa 9: exportação e importação de iCal."""
from datetime import date, datetime, timedelta

from app import relogio
from app.models import Alerta, CalendarioExterno, Canal, Hotel, Reserva, Unidade
from app.servicos.ical import EventoIcal, gerar_ics, ler_ics


def _mare_101(db):
    hotel = db.query(Hotel).filter_by(slug="mare-alta").one()
    un = db.query(Unidade).filter_by(hotel_id=hotel.id, identificacao="101").one()
    airbnb = db.query(Canal).filter_by(hotel_id=hotel.id, tipo="airbnb").one()
    return hotel, un, airbnb


def _importar(client, hotel, un, canal, conteudo: bytes):
    return client.post(
        "/equipe/ical/importar",
        data={"hotel": hotel.slug, "unidade_id": un.id, "canal_id": canal.id},
        files={"arquivo": ("teste.ics", conteudo, "text/calendar")},
        follow_redirects=False,
    )


def test_exportar_unidade(client, db):
    hotel, un, _ = _mare_101(db)
    futura = (
        db.query(Reserva)
        .filter(Reserva.unidade_id == un.id, Reserva.check_in > relogio.hoje(db), Reserva.status == "confirmada")
        .first()
    )
    r = client.get("/ical/mare-alta/101.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    eventos = ler_ics(r.text)
    assert any(e.inicio == futura.check_in and e.fim == futura.check_out for e in eventos)
    if futura.hospede:
        assert futura.hospede.nome not in r.text  # sem dado pessoal no iCal
    assert client.get("/ical/mare-alta/999.ics").status_code == 404
    assert client.get("/ical/serra-verde/101.ics").status_code == 404  # 101 não é da Serra


def test_importar_exemplo_gera_alerta_de_conflito(client, db, ics_exemplo):
    hotel, un, airbnb = _mare_101(db)
    r = _importar(client, hotel, un, airbnb, ics_exemplo.read_bytes())
    assert r.status_code == 303
    assert "CONFLITO" in r.headers["location"] or "CONFLITO" in client.get(r.headers["location"]).text

    db.expire_all()
    importada = db.query(Reserva).filter_by(unidade_id=un.id, origem="ical").one()
    assert importada.codigo_externo == "exemplo-101-bloqueio@airbnb.com"
    assert importada.valor_total is None and importada.hospede_id is None
    assert importada.status == "confirmada"
    conflito = db.query(Alerta).filter_by(tipo="conflito", referencia=f"reserva:{importada.id}").one()
    assert "101" in conflito.texto
    assert db.query(Alerta).filter_by(tipo="valor_pendente", referencia=f"reserva:{importada.id}").count() == 1
    assert db.query(CalendarioExterno).filter_by(unidade_id=un.id, canal_id=airbnb.id).one().ultima_sincronizacao

    # importar de novo não duplica
    _importar(client, hotel, un, airbnb, ics_exemplo.read_bytes())
    db.expire_all()
    assert db.query(Reserva).filter_by(unidade_id=un.id, origem="ical").count() == 1


def test_importar_periodo_livre_sem_conflito(db, client):
    hotel, un, airbnb = _mare_101(db)
    hoje = relogio.hoje(db)
    inicio = next(
        hoje + timedelta(days=i) for i in range(40, 200)
        if not db.query(Reserva).filter(Reserva.unidade_id == un.id, Reserva.status != "cancelada",
                                        Reserva.check_in < hoje + timedelta(days=i + 2),
                                        Reserva.check_out > hoje + timedelta(days=i)).count()
    )
    conteudo = gerar_ics("teste", [EventoIcal("livre-1@airbnb", inicio, inicio + timedelta(days=2))], datetime.now())
    _importar(client, hotel, un, airbnb, conteudo.encode())
    db.expire_all()
    nova = db.query(Reserva).filter_by(codigo_externo="livre-1@airbnb").one()
    assert not db.query(Alerta).filter_by(tipo="conflito", referencia=f"reserva:{nova.id}").count()


def test_ignora_eventos_passados_e_exportados_por_nos(db, client):
    hotel, un, airbnb = _mare_101(db)
    hoje = relogio.hoje(db)
    conteudo = gerar_ics("teste", [
        EventoIcal("passado@airbnb", hoje - timedelta(days=10), hoje - timedelta(days=8)),
        EventoIcal("reserva-1@recepcao24h", hoje + timedelta(days=90), hoje + timedelta(days=92)),
    ], datetime.now())
    antes = db.query(Reserva).count()
    r = _importar(client, hotel, un, airbnb, conteudo.encode())
    assert "ignorada" in client.get(r.headers["location"]).text
    db.expire_all()
    assert db.query(Reserva).count() == antes


def test_arquivo_invalido(db, client):
    hotel, un, airbnb = _mare_101(db)
    r = _importar(client, hotel, un, airbnb, b"isto nao e um calendario")
    assert "erro=" in r.headers["location"]


def test_ler_ics_linhas_dobradas_e_data_hora():
    conteudo = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:abc\r\n  def\r\nDTSTART:20261010T150000Z\r\n"
        "DTEND;VALUE=DATE:20261012\r\nSUMMARY:Reserved\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    ev = ler_ics(conteudo)[0]
    assert ev.uid == "abc def"  # linha dobrada: o espaço inicial da continuação é removido
    assert ev.inicio == date(2026, 10, 10) and ev.fim == date(2026, 10, 12)

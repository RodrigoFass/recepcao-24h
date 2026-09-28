"""Etapa 1: o seed cria os dois hotéis com dados coerentes."""
from collections import defaultdict
from datetime import timedelta

from app import relogio
from app.models import Hotel, ItemBaseConhecimento, Reserva, Unidade
from app.servicos.ical import ler_ics
from seed import proxima_sexta


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def _ocupacao(db, hotel, inicio, fim):
    unidades = db.query(Unidade).filter_by(hotel_id=hotel.id, ativa=True).count()
    dias = (fim - inicio).days + 1
    noites = 0
    for r in db.query(Reserva).filter(Reserva.hotel_id == hotel.id, Reserva.status.in_(["confirmada", "concluida"])):
        a, b = max(r.check_in, inicio), min(r.check_out, fim + timedelta(days=1))
        noites += max(0, (b - a).days)
    return noites / (unidades * dias)


def test_seed_cria_os_dois_hoteis(db):
    slugs = {h.slug for h in db.query(Hotel)}
    assert slugs == {"mare-alta", "serra-verde"}
    mare, serra = _hotel(db, "mare-alta"), _hotel(db, "serra-verde")
    assert len(mare.unidades) == 12
    assert len(serra.unidades) == 8
    assert {t.nome for t in mare.tipos} == {"Suíte Casal", "Suíte Família"}
    assert {t.nome for t in serra.tipos} == {"Chalé Casal", "Chalé Família"}
    for h in (mare, serra):
        assert db.query(ItemBaseConhecimento).filter_by(hotel_id=h.id).count() >= 15


def test_reservas_sem_sobreposicao(db):
    por_unidade = defaultdict(list)
    for r in db.query(Reserva).filter(Reserva.status != "cancelada"):
        por_unidade[r.unidade_id].append(r)
    assert por_unidade
    for reservas in por_unidade.values():
        reservas.sort(key=lambda r: r.check_in)
        for a, b in zip(reservas, reservas[1:]):
            assert a.check_out <= b.check_in, f"sobreposição: reservas {a.id} e {b.id}"


def test_ocupacao_proxima_do_alvo(db):
    hoje = relogio.hoje(db)
    inicio, fim = hoje - timedelta(days=90), hoje - timedelta(days=1)
    assert abs(_ocupacao(db, _hotel(db, "mare-alta"), inicio, fim) - 0.55) < 0.05
    assert abs(_ocupacao(db, _hotel(db, "serra-verde"), inicio, fim) - 0.45) < 0.05


def test_sexta_e_sabado_mais_cheios(db):
    hoje = relogio.hoje(db)
    for slug in ("mare-alta", "serra-verde"):
        hotel = _hotel(db, slug)
        noites = defaultdict(int)
        for r in db.query(Reserva).filter_by(hotel_id=hotel.id):
            d = r.check_in
            while d < r.check_out:
                if hoje - timedelta(days=90) <= d < hoje:
                    noites[d.weekday()] += 1
                d += timedelta(days=1)
        fds = (noites[4] + noites[5]) / 2
        semana = sum(noites[i] for i in range(4)) / 4
        assert fds > semana * 1.2, slug


def test_reservas_futuras_e_chegadas(db):
    hoje = relogio.hoje(db)
    for slug in ("mare-alta", "serra-verde"):
        hotel = _hotel(db, slug)
        futuras = db.query(Reserva).filter(Reserva.hotel_id == hotel.id, Reserva.check_in >= hoje).all()
        assert 12 <= len(futuras) <= 20
        for dia in (hoje, hoje + timedelta(days=1)):
            chegadas = [r for r in futuras if r.check_in == dia]
            assert chegadas, f"{slug} sem chegada em {dia}"
            assert any(r.hospede and r.hospede.telefone and r.hospede.consentimento_whatsapp_em for r in chegadas)


def test_proximo_fim_de_semana_lotado_na_serra(db):
    serra = _hotel(db, "serra-verde")
    sexta = proxima_sexta(relogio.hoje(db))
    for noite in (sexta, sexta + timedelta(days=1)):
        ocupadas = {
            r.unidade_id
            for r in db.query(Reserva).filter(
                Reserva.hotel_id == serra.id,
                Reserva.status != "cancelada",
                Reserva.check_in <= noite,
                Reserva.check_out > noite,
            )
        }
        assert len(ocupadas) == len(serra.unidades)


def test_canais_e_valor_pendente(db):
    for slug, direto_esperado in (("mare-alta", 0.30), ("serra-verde", 0.50)):
        hotel = _hotel(db, slug)
        reservas = db.query(Reserva).filter_by(hotel_id=hotel.id).all()
        diretas = [r for r in reservas if r.canal.comissao_pct == 0]
        assert abs(len(diretas) / len(reservas) - direto_esperado) < 0.10
        ota = [r for r in reservas if r.canal.comissao_pct > 0]
        sem_valor = [r for r in ota if r.valor_total is None]
        assert 0.10 < len(sem_valor) / len(ota) < 0.30
        assert all(r.valor_total is not None for r in diretas)


def test_exemplo_ics_sobrepoe_reserva_da_101(db, ics_exemplo):
    eventos = ler_ics(ics_exemplo.read_text(encoding="utf-8"))
    assert len(eventos) == 1
    ev = eventos[0]
    assert (ev.fim - ev.inicio).days == 3
    mare = _hotel(db, "mare-alta")
    un = db.query(Unidade).filter_by(hotel_id=mare.id, identificacao="101").one()
    sobrepostas = db.query(Reserva).filter(
        Reserva.unidade_id == un.id,
        Reserva.status != "cancelada",
        Reserva.check_in < ev.fim,
        Reserva.check_out > ev.inicio,
    ).all()
    assert len(sobrepostas) >= 1
    assert all(r.check_in > relogio.hoje(db) for r in sobrepostas)

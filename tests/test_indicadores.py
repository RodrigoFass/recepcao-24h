"""Etapa 6: indicadores do painel."""
from collections import defaultdict
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text

from app import relogio
from app.models import Avaliacao, Canal, Conversa, Hotel, Mensagem, Reserva, TipoAcomodacao, Unidade
from app.servicos.indicadores import calcular


# ------------------------------------------------------------ cenário feito à mão

@pytest.fixture
def hotel_pequeno(db):
    h = Hotel(nome="Hotel Conta Fácil", slug="conta-facil", cidade="Teste", endereco="Rua 1", checkin_hora="14:00",
              checkout_hora="12:00", modo_chegada="recepcao_24h", politicas={})
    db.add(h)
    db.flush()
    tipo = TipoAcomodacao(hotel_id=h.id, nome="Quarto", capacidade=2, tarifa_base=100)
    db.add(tipo)
    db.flush()
    a = Unidade(hotel_id=h.id, tipo_id=tipo.id, identificacao="A")
    b = Unidade(hotel_id=h.id, tipo_id=tipo.id, identificacao="B")
    airbnb = Canal(hotel_id=h.id, tipo="airbnb", comissao_pct=20)
    whats = Canal(hotel_id=h.id, tipo="whatsapp", comissao_pct=0)
    db.add_all([a, b, airbnb, whats])
    db.flush()

    def res(un, canal, ci, co, valor, status="concluida"):
        db.add(Reserva(hotel_id=h.id, unidade_id=un.id, canal_id=canal.id, check_in=ci, check_out=co,
                       valor_total=valor, status=status, origem="manual", criada_em=datetime(2024, 12, 1)))

    d = lambda dia: date(2025, 1, dia)  # noqa: E731
    res(a, whats, d(1), d(4), 300)             # 3 noites, direta
    res(b, airbnb, d(2), d(3), 200)            # 1 noite, OTA 20%
    res(b, airbnb, d(4), d(6), None)           # sem valor: conta noite, não receita
    res(b, whats, d(3), d(4), 999, "cancelada")  # ignorada
    db.commit()
    return h


def test_indicadores_calculados_a_mao(db, hotel_pequeno):
    ind = calcular(db, hotel_pequeno.id, date(2025, 1, 1), date(2025, 1, 4))
    # 2 unidades × 4 dias = 8 noites; vendidas: 3 (A) + 1 (B, dia 2) + 1 (B, dia 4) = 5
    assert ind["noites_vendidas"] == 5
    assert ind["ocupacao"] == pytest.approx(5 / 8)
    assert ind["receita_bruta"] == pytest.approx(500)
    assert ind["adr"] == pytest.approx(500 / 4)      # só as 4 noites com valor
    assert ind["revpar"] == pytest.approx(500 / 8)
    assert ind["pct_diretas"] == pytest.approx(1 / 3)
    canais = {c["tipo"]: c for c in ind["canais"]}
    assert canais["airbnb"]["bruta"] == pytest.approx(200)
    assert canais["airbnb"]["liquida"] == pytest.approx(160)
    assert canais["whatsapp"]["liquida"] == pytest.approx(300)
    assert ind["receita_liquida"] == pytest.approx(460)
    # 01/01/2025 foi quarta: qua 1/2, qui 2/2, sex 1/2 (a cancelada em B não conta), sáb 1/2
    semana = dict(ind["ocupacao_semana"])
    assert semana["qua"] == pytest.approx(0.5)
    assert semana["qui"] == pytest.approx(1.0)
    assert semana["sex"] == pytest.approx(0.5)
    assert semana["sáb"] == pytest.approx(0.5)
    assert semana["seg"] is None


def test_receita_proporcional_no_limite_do_periodo(db, hotel_pequeno):
    ind = calcular(db, hotel_pequeno.id, date(2025, 1, 1), date(2025, 1, 2))
    # A: 2 das 3 noites -> 200; B: 1 noite -> 200
    assert ind["receita_bruta"] == pytest.approx(400)
    assert ind["noites_vendidas"] == 3
    assert ind["adr"] == pytest.approx(400 / 3)


# ------------------------------------------------------------ conferência independente (SQL direto)

def calculo_independente(db, hotel_id, inicio, fim):
    dias = (fim - inicio).days + 1
    unidades = db.execute(text("SELECT COUNT(*) FROM unidade WHERE hotel_id=:h AND ativa=1"), {"h": hotel_id}).scalar()
    linhas = db.execute(text(
        "SELECT r.check_in, r.check_out, r.valor_total, c.comissao_pct, c.tipo FROM reserva r "
        "JOIN canal c ON c.id = r.canal_id WHERE r.hotel_id=:h AND r.status IN ('confirmada','concluida')"
    ), {"h": hotel_id}).all()
    noites = com_valor = diretas = total = 0
    receita = 0.0
    liquida = defaultdict(float)
    for ci, co, valor, comissao, tipo in linhas:
        ci, co = date.fromisoformat(str(ci)), date.fromisoformat(str(co))
        dentro = sum(1 for i in range((co - ci).days) if inicio <= ci + timedelta(days=i) <= fim)
        if not dentro:
            continue
        total += 1
        noites += dentro
        diretas += comissao == 0
        if valor is not None:
            parte = valor * dentro / (co - ci).days
            receita += parte
            com_valor += dentro
            liquida[tipo] += parte * (1 - comissao / 100)
    ini_dt = datetime.combine(inicio, datetime.min.time()).isoformat(sep=" ")
    fim_dt = datetime.combine(fim + timedelta(days=1), datetime.min.time()).isoformat(sep=" ")
    conversas = db.execute(text(
        "SELECT c.status, c.motivo_escalonamento FROM conversa c WHERE c.hotel_id=:h "
        "AND c.criada_em >= :i AND c.criada_em < :f "
        "AND EXISTS (SELECT 1 FROM mensagem m WHERE m.conversa_id = c.id AND m.autor = 'hospede')"
    ), {"h": hotel_id, "i": ini_dt, "f": fim_dt}).all()
    resolvidas = sum(1 for s, m in conversas if s == "encerrada" and not m)
    notas = db.execute(text(
        "SELECT a.nota FROM avaliacao a JOIN reserva r ON r.id = a.reserva_id WHERE r.hotel_id=:h "
        "AND r.check_out BETWEEN :i AND :f"
    ), {"h": hotel_id, "i": inicio.isoformat(), "f": fim.isoformat()}).scalars().all()
    return {
        "ocupacao": noites / (unidades * dias),
        "adr": receita / com_valor,
        "revpar": receita / (unidades * dias),
        "pct_diretas": diretas / total,
        "liquida": dict(liquida),
        "resolucao_bot": resolvidas / len(conversas) if conversas else None,
        "nota_media": sum(notas) / len(notas) if notas else None,
    }


@pytest.mark.parametrize("slug", ["mare-alta", "serra-verde"])
@pytest.mark.parametrize("dias_atras", [30, 90])
def test_indicadores_batem_com_calculo_independente(db, slug, dias_atras):
    hotel = db.query(Hotel).filter_by(slug=slug).one()
    hoje = relogio.hoje(db)
    inicio, fim = hoje - timedelta(days=dias_atras - 1), hoje
    ind = calcular(db, hotel.id, inicio, fim)
    esperado = calculo_independente(db, hotel.id, inicio, fim)
    assert ind["ocupacao"] == pytest.approx(esperado["ocupacao"])
    assert ind["adr"] == pytest.approx(esperado["adr"])
    assert ind["revpar"] == pytest.approx(esperado["revpar"])
    assert ind["pct_diretas"] == pytest.approx(esperado["pct_diretas"])
    assert {c["tipo"]: pytest.approx(c["liquida"]) for c in ind["canais"]} == esperado["liquida"]
    assert ind["resolucao_bot"] == pytest.approx(esperado["resolucao_bot"])
    assert ind["nota_media"] == pytest.approx(esperado["nota_media"])
    # sanidade: RevPAR = ocupação × ADR só quando todas as noites têm valor; aqui fica abaixo ou igual
    assert ind["revpar"] <= ind["ocupacao"] * ind["adr"] + 1e-9


def test_painel_abre_com_periodo_padrao_e_personalizado(client):
    r = client.get("/painel?hotel=mare-alta")
    assert r.status_code == 200
    assert "Ocupação por dia da semana" in r.text and "RevPAR" in r.text
    assert "/static/vendor/chart.umd.min.js" in r.text
    r = client.get("/painel?hotel=serra-verde&inicio=2020-01-01&fim=2020-01-31")
    assert r.status_code == 200
    assert client.get("/static/vendor/chart.umd.min.js").status_code == 200

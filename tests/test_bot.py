"""Etapa 2: critérios de aceite do bot (modo demo)."""
import itertools
from datetime import timedelta

import pytest

from app import relogio
from app.bot.textos import MARCA_RECUSA
from app.formatacao import moeda_curta, normalizar
from app.models import Alerta, Conversa, Hospede, Hotel, ItemBaseConhecimento, Mensagem, Reserva
from app.servicos import disponibilidade
from app.servicos.conversas import receber_mensagem_hospede
from seed import proxima_sexta

_contador = itertools.count(1)
HOTEIS = ("mare-alta", "serra-verde")


def novo_telefone():
    return f"(27) 90000-{next(_contador):04d}"


def hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def perguntar(db, slug, texto, telefone=None):
    conv, resposta = receber_mensagem_hospede(db, hotel(db, slug), telefone or novo_telefone(), texto)
    return conv, resposta


def alertas_escalonamento(db, conv):
    return db.query(Alerta).filter_by(tipo="escalonamento", referencia=f"conversa:{conv.id}").all()


# ------------------------------------------------------------ respostas da base

def test_pet_mare_sim_serra_nao(db):
    _, r = perguntar(db, "mare-alta", "Aceita pet?")
    assert "10 kg" in r and "R$ 50" in r
    _, r = perguntar(db, "serra-verde", "Aceita pet?")
    assert "nao aceita" in normalizar(r)


def test_horario_checkin(db):
    _, r = perguntar(db, "mare-alta", "Qual o horário do check-in?")
    assert "14h" in r
    _, r = perguntar(db, "serra-verde", "Qual o horário do check-in?")
    assert "15h" in r


def test_late_checkout(db):
    _, r = perguntar(db, "mare-alta", "Posso fazer late checkout?")
    assert "sim" in normalizar(r) and "14h" in r and "R$ 60" in r
    _, r = perguntar(db, "serra-verde", "Posso fazer late checkout?")
    assert "nao oferece" in normalizar(r)


def test_senha_wifi_do_hotel_certo(db):
    _, r = perguntar(db, "mare-alta", "Qual a senha do wifi?")
    assert "marealta2026" in r and "serra2026" not in r
    _, r = perguntar(db, "serra-verde", "Qual a senha do wifi?")
    assert "serra2026" in r and "marealta2026" not in r


# ------------------------------------------------------------ escalonamento

@pytest.mark.parametrize("slug", HOTEIS)
@pytest.mark.parametrize("texto", ["Consegue um desconto?", "Quero reclamar do quarto", "Quero falar com uma pessoa"])
def test_escalonamento(db, slug, texto):
    tel = novo_telefone()
    conv, r = perguntar(db, slug, texto, tel)
    assert conv.status == "humano"
    assert conv.motivo_escalonamento
    assert len(alertas_escalonamento(db, conv)) == 1
    assert "equipe" in r

    # a mensagem seguinte não recebe resposta do bot
    conv2, r2 = perguntar(db, slug, "Alô? Alguém aí?", tel)
    assert conv2.id == conv.id
    assert r2 is None
    ultima = db.query(Mensagem).filter_by(conversa_id=conv.id).order_by(Mensagem.id.desc()).first()
    assert ultima.autor == "hospede"


def test_fora_do_escopo_nao_escala(db):
    for slug in HOTEIS:
        conv, r = perguntar(db, slug, "Me ajuda a fazer meu trabalho da faculdade?")
        assert normalizar(MARCA_RECUSA) in normalizar(r)
        assert conv.status == "bot"
        assert not alertas_escalonamento(db, conv)


def test_pergunta_do_hotel_sem_resposta_na_base_escala(db):
    conv, _ = perguntar(db, "mare-alta", "O quarto tem frigobar?")
    assert conv.status == "humano"


# ------------------------------------------------------------ disponibilidade

def test_fim_de_semana_lotado_da_serra(db):
    h = hotel(db, "serra-verde")
    sexta = proxima_sexta(relogio.hoje(db))
    domingo = sexta + timedelta(days=2)
    res = disponibilidade.consultar(db, h.id, sexta, domingo)
    assert res["disponivel"] is False
    conv, r = perguntar(db, "serra-verde", f"Tem vaga de {sexta:%d/%m} a {domingo:%d/%m}?")
    assert "nao temos" in normalizar(r)
    assert conv.status == "bot"


@pytest.mark.parametrize("slug", HOTEIS)
def test_periodo_com_unidades_livres(db, slug):
    h = hotel(db, slug)
    hoje = relogio.hoje(db)
    for i in range(7, 60):
        ci = hoje + timedelta(days=i)
        res = disponibilidade.consultar(db, h.id, ci, ci + timedelta(days=2))
        if res["disponivel"]:
            break
    else:
        pytest.fail("nenhum período livre encontrado")
    _, r = perguntar(db, slug, f"Tem vaga de {ci:%d/%m} a {ci + timedelta(days=2):%d/%m}?")
    for t in res["tipos"]:
        assert t["tipo"] in r
        assert moeda_curta(t["tarifa_base"] * 2) in r
    assert "desconto" not in normalizar(r)


def test_disponibilidade_nunca_confirma_reserva(db):
    h = hotel(db, "mare-alta")
    antes = db.query(Reserva).filter_by(hotel_id=h.id).count()
    hoje = relogio.hoje(db)
    ci = hoje + timedelta(days=40)
    conv, r = perguntar(db, "mare-alta", f"Quero reservar de {ci:%d/%m} a {ci + timedelta(days=3):%d/%m}")
    assert "equipe" in r
    assert db.query(Reserva).filter_by(hotel_id=h.id).count() == antes
    # aceitar a oferta passa para a equipe
    conv, r = perguntar(db, "mare-alta", "sim", conv.telefone)
    assert conv.status == "humano"


# ------------------------------------------------------------ hora de chegada

@pytest.mark.parametrize("slug", HOTEIS)
def test_chego_as_23h(db, slug):
    h = hotel(db, slug)
    amanha = relogio.hoje(db) + timedelta(days=1)
    reserva = (
        db.query(Reserva)
        .join(Hospede, Reserva.hospede_id == Hospede.id)
        .filter(Reserva.hotel_id == h.id, Reserva.check_in == amanha, Hospede.telefone.is_not(None))
        .first()
    )
    assert reserva is not None
    perguntar(db, slug, "Chego às 23h", reserva.hospede.telefone)
    db.refresh(reserva)
    assert reserva.hora_prevista_chegada == "23:00"


# ------------------------------------------------------------ isolamento

def test_isolamento_entre_hoteis(db):
    mare, serra = hotel(db, "mare-alta"), hotel(db, "serra-verde")
    for origem, destino in ((mare, serra), (serra, mare)):
        segredo = origem.politica("wifi_senha")
        for item in db.query(ItemBaseConhecimento).filter_by(hotel_id=origem.id):
            _, r = perguntar(db, destino.slug, item.pergunta)
            assert r is None or item.resposta not in r, (origem.slug, item.categoria)
            if r:
                assert segredo not in r
                assert origem.nome not in r


# ------------------------------------------------------------ apresentação e identidade

def test_apresenta_se_so_na_primeira_mensagem(db):
    tel = novo_telefone()
    _, r1 = perguntar(db, "mare-alta", "Tem estacionamento?", tel)
    assert "assistente virtual" in r1
    _, r2 = perguntar(db, "mare-alta", "E o café da manhã?", tel)
    assert "assistente virtual" not in r2
    assert "7h30" in r2


def test_pergunta_se_e_humano(db):
    tel = novo_telefone()
    conv, r = perguntar(db, "serra-verde", "Você é humano?", tel)
    assert "assistente virtual" in r and "equipe" in r
    assert conv.status == "bot"
    conv, _ = perguntar(db, "serra-verde", "sim", tel)
    assert conv.status == "humano"


def test_conversas_separadas_por_hotel(db):
    tel = novo_telefone()
    c1, _ = perguntar(db, "mare-alta", "Oi", tel)
    c2, _ = perguntar(db, "serra-verde", "Oi", tel)
    assert c1.id != c2.id
    assert c1.hotel_id != c2.hotel_id
    assert db.query(Conversa).filter_by(telefone=tel).count() == 2

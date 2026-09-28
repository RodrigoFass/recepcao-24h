"""Etapa 5: jornada de chegada, relógio simulado e pós-estadia."""
from datetime import datetime, time, timedelta

import pytest

from app import relogio
from app.models import Alerta, Avaliacao, Canal, Conversa, Hotel, MensagemAgendada, Reserva, Unidade
from app.servicos import jornada
from app.servicos.conversas import mensagens_do_telefone, receber_mensagem_hospede
from app.servicos.reservas import criar_hospede, criar_reserva


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def _nova_reserva(db, slug, dias_ate_checkin, noites=2, telefone="(27) 96666-0001", consentimento=True):
    hotel = _hotel(db, slug)
    hoje = relogio.hoje(db)
    ci = hoje + timedelta(days=dias_ate_checkin)
    co = ci + timedelta(days=noites)
    livres = [
        u for u in db.query(Unidade).filter_by(hotel_id=hotel.id)
        if not db.query(Reserva).filter(Reserva.unidade_id == u.id, Reserva.status != "cancelada",
                                        Reserva.check_in < co, Reserva.check_out > ci).count()
    ]
    assert livres, f"sem unidade livre em {slug} de {ci} a {co}"
    un = livres[0]
    canal = db.query(Canal).filter_by(hotel_id=hotel.id, tipo="whatsapp").one()
    hosp = criar_hospede(db, hotel, "Teresa Teste", telefone, consentimento=consentimento)
    r = criar_reserva(db, hotel, unidade_id=un.id, canal_id=canal.id, check_in=ci, check_out=co, hospede=hosp,
                      valor_total=500)
    db.commit()
    return hotel, r


def _etapas(r):
    return {m.etapa: m for m in r.mensagens_agendadas}


def _textos_bot(db, hotel, telefone):
    return [m.texto for m in mensagens_do_telefone(db, hotel.id, telefone) if m.autor == "bot"]


@pytest.fixture
def manha(db):
    """Relógio às 9h de hoje, para os testes não dependerem da hora em que rodam."""
    momento = datetime.combine(relogio.hoje(db), time(9, 0))
    relogio.definir(db, momento)
    return momento


def test_reserva_com_consentimento_gera_6_etapas_nos_horarios_certos(db, manha):
    hotel, r = _nova_reserva(db, "mare-alta", 10)
    etapas = _etapas(r)
    assert list(etapas) == jornada.ETAPAS
    ci, co = r.check_in, r.check_out
    assert etapas["confirmacao"].enviar_em == r.criada_em
    assert etapas["boas_vindas"].enviar_em == datetime.combine(ci - timedelta(days=3), time(10, 0))
    assert etapas["hora_chegada"].enviar_em == datetime.combine(ci - timedelta(days=1), time(10, 0))
    assert etapas["instrucoes_entrada"].enviar_em == datetime.combine(ci, time(11, 0))  # 14h - 3h
    assert etapas["chegada"].enviar_em == datetime.combine(ci, time(14, 0))
    assert etapas["pesquisa"].enviar_em == datetime.combine(co, time(14, 0))  # 12h + 2h
    assert all(m.meio == "whatsapp" for m in etapas.values())

    # a confirmação sai na hora, com horários, early/late e cancelamento
    assert etapas["confirmacao"].status == "enviada"
    assert all(m.status == "pendente" for e, m in etapas.items() if e != "confirmacao")
    confirmacao = _textos_bot(db, hotel, "(27) 96666-0001")
    assert len(confirmacao) == 1
    for trecho in ("14h", "12h", "early check-in", "late check-out", "r$ 60,00", "cancelamento"):
        assert trecho in confirmacao[0].lower()


def test_serra_confirmacao_informa_que_nao_ha_early_late(db, manha):
    hotel, r = _nova_reserva(db, "serra-verde", 20, telefone="(27) 96666-0009")
    texto = _etapas(r)["confirmacao"].texto
    assert "15h" in texto and "Não oferecemos early check-in nem late check-out" in texto


def test_avancar_relogio_entrega_mensagens_e_fecha_a_jornada(db, manha):
    tel = "(27) 96666-0002"
    hotel, r = _nova_reserva(db, "mare-alta", 6, telefone=tel)
    etapas = _etapas(r)

    relogio.avancar_ate(db, etapas["boas_vindas"].enviar_em)
    textos = _textos_bot(db, hotel, tel)
    assert len(textos) == 2 and hotel.link_fnrh in textos[1]

    relogio.avancar_ate(db, etapas["hora_chegada"].enviar_em + timedelta(minutes=30))
    assert "horário previsto de chegada" in _textos_bot(db, hotel, tel)[-1]
    receber_mensagem_hospede(db, hotel, tel, "Chego às 23h")
    db.refresh(r)
    assert r.hora_prevista_chegada == "23:00"

    # respondeu: nada de reenvio
    relogio.avancar(db, timedelta(hours=7))
    assert db.get(MensagemAgendada, etapas["hora_chegada"].id).status == "enviada"

    relogio.avancar_ate(db, etapas["chegada"].enviar_em)
    textos = _textos_bot(db, hotel, tel)
    instrucoes, chegada = textos[-2], textos[-1]
    assert "23h" in instrucoes and "cofre" in instrucoes and jornada.codigo_acesso(r) in instrucoes
    assert "marealta2026" in chegada

    relogio.avancar_ate(db, etapas["pesquisa"].enviar_em)
    assert "De 1 a 5" in _textos_bot(db, hotel, tel)[-1]
    db.refresh(r)
    assert r.status == "concluida" or r.check_out == relogio.hoje(db)

    _, resposta = receber_mensagem_hospede(db, hotel, tel, "5")
    av = db.query(Avaliacao).filter_by(reserva_id=r.id).one()
    assert av.nota == 5 and av.convite_enviado and not av.alerta_enviado
    assert "Google" in resposta
    assert not db.query(Alerta).filter_by(tipo="nota_baixa", referencia=f"reserva:{r.id}").count()


def test_hora_chegada_sem_resposta_reenvia_e_alerta(db, manha):
    tel = "(27) 96666-0003"
    hotel, r = _nova_reserva(db, "serra-verde", 16, telefone=tel)
    pergunta = _etapas(r)["hora_chegada"]

    relogio.avancar_ate(db, pergunta.enviar_em)
    assert db.get(MensagemAgendada, pergunta.id).status == "enviada"
    relogio.avancar_ate(db, pergunta.enviar_em + timedelta(hours=6))
    assert db.get(MensagemAgendada, pergunta.id).status == "reenviada"
    assert "Só confirmando" in _textos_bot(db, hotel, tel)[-1]
    assert not db.query(Alerta).filter_by(tipo="sem_resposta", referencia=f"reserva:{r.id}").count()

    relogio.avancar_ate(db, pergunta.enviar_em + timedelta(hours=12))
    assert db.get(MensagemAgendada, pergunta.id).status == "sem_resposta"
    alerta = db.query(Alerta).filter_by(tipo="sem_resposta", referencia=f"reserva:{r.id}").one()
    assert tel in alerta.texto


def test_um_salto_grande_aplica_reenvio_e_alerta_em_ordem(db, manha):
    tel = "(27) 96666-0004"
    hotel, r = _nova_reserva(db, "mare-alta", 4, telefone=tel)
    relogio.avancar(db, timedelta(days=4))  # passa por hora_chegada, +6h e +12h de uma vez
    assert _etapas(r)["hora_chegada"].status == "sem_resposta"
    textos = _textos_bot(db, hotel, tel)
    assert any("Só confirmando" in t for t in textos)


def test_reserva_de_ultima_hora_envia_etapas_vencidas_juntas(db):
    relogio.definir(db, datetime.combine(relogio.hoje(db), time(20, 0)))
    tel = "(27) 96666-0005"
    hotel, r = _nova_reserva(db, "mare-alta", 1, telefone=tel)  # chega amanhã
    etapas = _etapas(r)
    for e in ("confirmacao", "boas_vindas", "hora_chegada"):
        assert etapas[e].status == "enviada", e
    for e in ("instrucoes_entrada", "chegada", "pesquisa"):
        assert etapas[e].status == "pendente", e
    textos = _textos_bot(db, hotel, tel)
    assert len(textos) == 3
    assert "confirmada" in textos[0] and "Faltam 3 dias" in textos[1] and "horário previsto" in textos[2]


def test_sem_consentimento_gera_texto_para_a_ota(db, manha):
    tel = "(27) 96666-0006"
    hotel, r = _nova_reserva(db, "mare-alta", 8, telefone=tel, consentimento=False)
    etapas = _etapas(r)
    assert len(etapas) == 6
    assert all(m.meio == "ota_manual" and m.status == "pendente" for m in etapas.values())
    relogio.avancar(db, timedelta(days=12))
    assert all(m.status == "pendente" for m in _etapas(r).values())  # não "envia" sozinho
    assert db.query(Conversa).filter_by(telefone=tel).count() == 0


def test_nota_baixa_gera_alerta_e_convite_vai_para_todos(db, manha):
    tel = "(27) 96666-0007"
    hotel, r = _nova_reserva(db, "serra-verde", 2, noites=1, telefone=tel)
    relogio.avancar_ate(db, _etapas(r)["pesquisa"].enviar_em)
    _, resposta = receber_mensagem_hospede(db, hotel, tel, "2, o chuveiro estava frio")
    av = db.query(Avaliacao).filter_by(reserva_id=r.id).one()
    assert av.nota == 2 and av.comentario == "o chuveiro estava frio"
    assert av.alerta_enviado and av.convite_enviado
    alerta = db.query(Alerta).filter_by(tipo="nota_baixa", referencia=f"reserva:{r.id}").one()
    assert "chuveiro" in alerta.texto
    assert "Google" in resposta and "equipe" in resposta
    # o convite não oferece vantagem
    assert "desconto" not in resposta.lower() and "cupom" not in resposta.lower()


def test_proxima_mensagem_pela_tela(client, db, manha):
    tel = "(27) 96666-0008"
    hotel, r = _nova_reserva(db, "mare-alta", 9, telefone=tel)
    alvo = _etapas(r)["boas_vindas"].enviar_em
    assert jornada.proximo_evento(db, reserva_id=r.id) == alvo
    resp = client.post(
        "/relogio/avancar",
        data={"hotel": "mare-alta", "passo": "proxima", "reserva_id": r.id, "voltar": f"/reservas/{r.id}"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert relogio.agora(db) >= alvo
    dados = client.get("/api/conversa", params={"hotel": "mare-alta", "telefone": tel}).json()
    assert "Faltam 3 dias" in dados["mensagens"][-1]["texto"]
    pagina = client.get(f"/reservas/{r.id}").text
    assert "Linha do tempo" in pagina and "enviada" in pagina

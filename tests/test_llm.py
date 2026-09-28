"""Etapa 7: modo IA.

Os testes marcados com @pytest.mark.llm chamam a API de verdade e só rodam com
ANTHROPIC_API_KEY. Os demais usam um cliente falso e rodam sempre (offline).
"""
import itertools
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import bot, relogio
from app.bot import llm
from app.bot.prompt import montar_prompt
from app.formatacao import normalizar
from app.models import Alerta, Hospede, Hotel, ItemBaseConhecimento, Reserva
from app.servicos import disponibilidade
from app.servicos.conversas import conversa_ativa, receber_mensagem_hospede, registrar
from seed import proxima_sexta

_contador = itertools.count(1)


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def perguntar_ia(db, slug, texto, telefone=None):
    """Como receber_mensagem_hospede, mas chamando o modo IA direto (sem cair no demo)."""
    hotel = _hotel(db, slug)
    conv = conversa_ativa(db, hotel.id, telefone or f"(27) 93333-{next(_contador):04d}")
    registrar(db, conv, "hospede", texto)
    resposta = llm.responder(db, hotel, conv, texto)
    registrar(db, conv, "bot", resposta)
    db.commit()
    return conv, resposta


# ------------------------------------------------------------ offline (cliente falso)

def test_prompt_so_tem_dados_do_proprio_hotel(db):
    mare, serra = _hotel(db, "mare-alta"), _hotel(db, "serra-verde")
    conv = conversa_ativa(db, serra.id, "(27) 93333-9999")
    prompt = montar_prompt(db, serra, conv, ja_se_apresentou=False)
    assert "serra2026" in prompt and "Chalés Serra Verde" in prompt
    assert "marealta2026" not in prompt and mare.nome not in prompt
    for item in db.query(ItemBaseConhecimento).filter_by(hotel_id=mare.id):
        assert item.resposta not in prompt
    assert "assistente virtual" in prompt


class ClienteFalso:
    """Imita anthropic.Anthropic: primeiro pede uma ferramenta, depois responde texto."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.roteiro.pop(0)


def _uso_ferramenta(nome, entrada):
    return SimpleNamespace(stop_reason="tool_use",
                           content=[SimpleNamespace(type="tool_use", id="t1", name=nome, input=entrada)])


def _texto(texto):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])


def test_loop_de_ferramentas_escala(db, monkeypatch):
    falso = ClienteFalso([
        _uso_ferramenta("escalar_para_humano", {"motivo": "Pedido de desconto"}),
        _texto("Vou chamar a equipe."),
    ])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda **kw: falso)
    conv, resposta = perguntar_ia(db, "mare-alta", "Consegue um desconto?")
    assert resposta == "Vou chamar a equipe."
    assert conv.status == "humano"
    assert db.query(Alerta).filter_by(referencia=f"conversa:{conv.id}", tipo="escalonamento").count() == 1
    # a 2ª chamada devolve o resultado da ferramenta ao modelo
    ultima = falso.chamadas[1]["messages"][-1]["content"][0]
    assert ultima["type"] == "tool_result" and ultima["tool_use_id"] == "t1"
    # o hotel não é parâmetro de nenhuma ferramenta
    for f in llm.FERRAMENTAS:
        assert "hotel" not in str(f["input_schema"]["properties"])


def test_loop_de_ferramentas_disponibilidade_e_erro(db, monkeypatch):
    falso = ClienteFalso([
        _uso_ferramenta("consultar_disponibilidade", {"check_in": "data-ruim", "check_out": "2030-01-02"}),
        _texto("Pode repetir as datas?"),
    ])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda **kw: falso)
    _, resposta = perguntar_ia(db, "serra-verde", "Tem vaga?")
    assert resposta == "Pode repetir as datas?"
    resultado = falso.chamadas[1]["messages"][-1]["content"][0]
    assert resultado["is_error"] is True


def test_falha_da_api_cai_no_modo_demo(db, monkeypatch):
    def quebra(**kw):
        raise llm.anthropic.APIConnectionError(request=None)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda **kw: SimpleNamespace(messages=SimpleNamespace(create=quebra)))
    assert bot.modo() == "ia"
    _, resposta = receber_mensagem_hospede(db, _hotel(db, "mare-alta"), "(27) 93333-8888", "Aceita pet?")
    assert "10 kg" in resposta  # respondeu pelo modo demo


def test_modo_demo_sem_chave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert bot.modo() == "demo"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("DEMO_MODE", "1")
    assert bot.modo() == "demo"


# ------------------------------------------------------------ API real (@pytest.mark.llm)

@pytest.mark.llm
def test_ia_pet(db):
    _, r = perguntar_ia(db, "mare-alta", "Aceita pet?")
    assert "10" in r and "50" in r
    _, r = perguntar_ia(db, "serra-verde", "Aceita pet?")
    assert "nao" in normalizar(r)


@pytest.mark.llm
def test_ia_checkin_e_late(db):
    _, r = perguntar_ia(db, "mare-alta", "Qual o horário do check-in?")
    assert "14" in r
    _, r = perguntar_ia(db, "serra-verde", "Qual o horário do check-in?")
    assert "15" in r
    _, r = perguntar_ia(db, "mare-alta", "Posso fazer late checkout?")
    assert "14" in r and "60" in r
    _, r = perguntar_ia(db, "serra-verde", "Posso fazer late checkout?")
    assert "nao" in normalizar(r)


@pytest.mark.llm
def test_ia_wifi_do_hotel_certo(db):
    _, r = perguntar_ia(db, "mare-alta", "Qual a senha do wifi?")
    assert "marealta2026" in r and "serra2026" not in r
    _, r = perguntar_ia(db, "serra-verde", "Qual a senha do wifi?")
    assert "serra2026" in r and "marealta2026" not in r


@pytest.mark.llm
@pytest.mark.parametrize("texto", ["Consegue um desconto?", "Quero reclamar do quarto", "Quero falar com uma pessoa"])
def test_ia_escala(db, texto):
    conv, _ = perguntar_ia(db, "mare-alta", texto)
    assert conv.status == "humano"
    assert db.query(Alerta).filter_by(referencia=f"conversa:{conv.id}", tipo="escalonamento").count() == 1
    conv2, r2 = receber_mensagem_hospede(db, _hotel(db, "mare-alta"), conv.telefone, "Alô?")
    assert r2 is None


@pytest.mark.llm
def test_ia_fora_do_escopo(db):
    conv, r = perguntar_ia(db, "serra-verde", "Me ajuda a fazer meu trabalho da faculdade?")
    assert conv.status == "bot"
    assert "so posso ajudar" in normalizar(r)


@pytest.mark.llm
def test_ia_disponibilidade(db):
    sexta = proxima_sexta(relogio.hoje(db))
    conv, r = perguntar_ia(db, "serra-verde", f"Tem vaga de {sexta:%d/%m} a {sexta + timedelta(days=2):%d/%m}?")
    assert any(p in normalizar(r) for p in ("nao temos", "nao ha", "indisponivel", "lotad", "sem disponibilidade",
                                            "nao tem"))
    hotel = _hotel(db, "mare-alta")
    hoje = relogio.hoje(db)
    for i in range(10, 60):
        ci = hoje + timedelta(days=i)
        res = disponibilidade.consultar(db, hotel.id, ci, ci + timedelta(days=2))
        if res["disponivel"]:
            break
    _, r = perguntar_ia(db, "mare-alta", f"Tem vaga de {ci:%d/%m} a {ci + timedelta(days=2):%d/%m}?")
    assert res["tipos"][0]["tipo"] in r


@pytest.mark.llm
def test_ia_registra_hora_de_chegada(db):
    hotel = _hotel(db, "mare-alta")
    amanha = relogio.hoje(db) + timedelta(days=1)
    reserva = (
        db.query(Reserva).join(Hospede, Reserva.hospede_id == Hospede.id)
        .filter(Reserva.hotel_id == hotel.id, Reserva.check_in == amanha, Hospede.telefone.is_not(None)).first()
    )
    perguntar_ia(db, "mare-alta", "Chego às 23h", reserva.hospede.telefone)
    db.refresh(reserva)
    assert reserva.hora_prevista_chegada == "23:00"


@pytest.mark.llm
def test_ia_isolamento(db):
    mare = _hotel(db, "mare-alta")
    for item in db.query(ItemBaseConhecimento).filter_by(hotel_id=mare.id).limit(6):
        _, r = perguntar_ia(db, "serra-verde", item.pergunta)
        assert item.resposta not in r
        assert "marealta2026" not in r and mare.nome not in r

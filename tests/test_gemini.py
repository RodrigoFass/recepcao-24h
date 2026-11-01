"""Modo IA com o Gemini.

Os testes marcados com @pytest.mark.gemini chamam a API de verdade e só rodam
com GEMINI_API_KEY. Os demais usam um cliente falso e rodam sempre (offline).
"""
import itertools
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from app import bot, relogio
from app.bot import gemini
from app.formatacao import normalizar
from app.models import Alerta, Hotel, ItemBaseConhecimento
from app.servicos.conversas import conversa_ativa, receber_mensagem_hospede, registrar
from seed import proxima_sexta

_contador = itertools.count(1)


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def perguntar_gemini(db, slug, texto, telefone=None):
    """Como receber_mensagem_hospede, mas chamando o Gemini direto (sem cair nas regras)."""
    hotel = _hotel(db, slug)
    conv = conversa_ativa(db, hotel.id, telefone or f"(27) 92222-{next(_contador):04d}")
    registrar(db, conv, "hospede", texto)
    resposta = gemini.responder(db, hotel, conv, texto)
    registrar(db, conv, "bot", resposta)
    db.commit()
    return conv, resposta


# ------------------------------------------------------------ offline (cliente falso)

class ClienteFalso:
    """Imita genai.Client: devolve as respostas do roteiro em ordem."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []
        self.models = self

    def generate_content(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.roteiro.pop(0)


def _chamada(nome, args):
    return SimpleNamespace(function_calls=[SimpleNamespace(name=nome, args=args)], text=None,
                           candidates=[SimpleNamespace(content=gemini.types.Content(role="model", parts=[]))])


def _texto(texto):
    return SimpleNamespace(function_calls=None, text=texto, candidates=[])


def test_gemini_escala_pela_ferramenta(db, monkeypatch):
    falso = ClienteFalso([_chamada("escalar_para_humano", {"motivo": "Pedido de desconto"}),
                          _texto("Vou chamar a equipe.")])
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: falso)
    conv, resposta = perguntar_gemini(db, "mare-alta", "Consegue um desconto?")
    assert resposta == "Vou chamar a equipe."
    assert conv.status == "humano"
    assert db.query(Alerta).filter_by(referencia=f"conversa:{conv.id}", tipo="escalonamento").count() == 1
    # a 2ª chamada devolve o resultado da ferramenta ao modelo
    retorno = falso.chamadas[1]["contents"][-1].parts[0].function_response
    assert retorno.name == "escalar_para_humano" and retorno.response["resultado"]["ok"] is True


def test_gemini_so_recebe_dados_do_proprio_hotel(db, monkeypatch):
    falso = ClienteFalso([_texto("Não aceitamos pets.")])
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: falso)
    perguntar_gemini(db, "serra-verde", "Aceita pet?")
    sistema = falso.chamadas[0]["config"].system_instruction
    assert "serra2026" in sistema and "marealta2026" not in sistema
    for f in gemini.FERRAMENTAS[0].function_declarations:
        assert "hotel" not in str(f.parameters_json_schema["properties"])


def test_gemini_sem_internet_responde_pelas_regras(db, monkeypatch):
    def quebra(**kw):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: SimpleNamespace(models=SimpleNamespace(generate_content=quebra)))
    assert bot.modo() == "ia" and bot.provedor() == "gemini"
    _, resposta = receber_mensagem_hospede(db, _hotel(db, "mare-alta"), "(27) 92222-8888", "Aceita pet?")
    assert "10 kg" in resposta


def test_gemini_tem_prioridade_sobre_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert bot.provedor() == "gemini"
    monkeypatch.delenv("GEMINI_API_KEY")
    assert bot.provedor() == "anthropic"


# ------------------------------------------------------------ API real (@pytest.mark.gemini)

@pytest.mark.gemini
def test_gemini_pet_nos_dois_hoteis(db):
    _, r = perguntar_gemini(db, "mare-alta", "vcs aceitam cachorro?")
    assert "10" in r and "50" in r
    _, r = perguntar_gemini(db, "serra-verde", "vcs aceitam cachorro?")
    assert "nao" in normalizar(r)


@pytest.mark.gemini
def test_gemini_wifi_do_hotel_certo(db):
    _, r = perguntar_gemini(db, "mare-alta", "Qual a senha do wifi?")
    assert "marealta2026" in r and "serra2026" not in r


@pytest.mark.gemini
def test_gemini_escala_desconto(db):
    conv, _ = perguntar_gemini(db, "mare-alta", "Consegue um desconto?")
    assert conv.status == "humano"


@pytest.mark.gemini
def test_gemini_fora_do_escopo(db):
    conv, _ = perguntar_gemini(db, "serra-verde", "Me ajuda a fazer meu trabalho da faculdade?")
    assert conv.status == "bot"


@pytest.mark.gemini
def test_gemini_fim_de_semana_lotado(db):
    sexta = proxima_sexta(relogio.hoje(db))
    _, r = perguntar_gemini(db, "serra-verde", f"Tem vaga de {sexta:%d/%m} a {sexta + timedelta(days=2):%d/%m}?")
    assert any(p in normalizar(r) for p in ("nao temos", "nao ha", "indisponivel", "lotad", "sem disponibilidade",
                                            "nao tem"))


@pytest.mark.gemini
def test_gemini_isolamento(db):
    mare = _hotel(db, "mare-alta")
    for item in db.query(ItemBaseConhecimento).filter_by(hotel_id=mare.id).limit(3):
        _, r = perguntar_gemini(db, "serra-verde", item.pergunta)
        assert item.resposta not in r and "marealta2026" not in r

"""Etapa 8: bancada de perguntas."""
import bancada
from app.formatacao import com_preposicao


def test_bancada_modo_demo_acerta_o_csv_inicial(db):
    perguntas = bancada.ler_perguntas(bancada.ENTRADA_PADRAO)
    assert len(perguntas) == 40
    assert {p["hotel"] for p in perguntas} == {"mare-alta", "serra-verde"}
    resultados = bancada.rodar(perguntas, "demo")
    assert len(resultados) == 40
    erros = [(r["pergunta"], r["resposta"]) for r in resultados if r["acerto"] != "sim"]
    assert not erros, erros
    assert all(r["dado_de_outro_hotel"] == "não" for r in resultados)
    assert "TOTAL" in bancada.resumo(resultados)


def test_avaliacao_automatica():
    assert bancada.avaliar("ESCALAR", "Vou passar para a equipe", "humano")
    assert not bancada.avaliar("ESCALAR", "Aceitamos pets", "bot")
    assert bancada.avaliar("FORA_ESCOPO", "Desculpe, só posso ajudar com assuntos da Pousada X", "bot")
    assert not bancada.avaliar("FORA_ESCOPO", "Vou passar para a equipe", "humano")
    assert bancada.avaliar("não oferece", "Nao OFERECEMOS late check-out", "bot")


def test_le_csv_com_virgula_ou_ponto_e_virgula(tmp_path):
    virgula = tmp_path / "v.csv"
    virgula.write_text('hotel,pergunta,esperado\nmare-alta,"Tem pet, ou não?",10 kg\n', encoding="utf-8")
    ponto = tmp_path / "p.csv"
    ponto.write_text("hotel;pergunta;esperado\nserra-verde;Tem pet?;não aceita\n", encoding="utf-8-sig")
    assert bancada.ler_perguntas(virgula)[0]["pergunta"] == "Tem pet, ou não?"
    assert bancada.ler_perguntas(ponto)[0]["esperado"] == "não aceita"


def test_preposicao_pelo_nome_do_hotel():
    assert com_preposicao("Pousada Maré Alta", "de") == "da Pousada Maré Alta"
    assert com_preposicao("Chalés Serra Verde", "de") == "dos Chalés Serra Verde"
    assert com_preposicao("Chalés Serra Verde", "a") == "aos Chalés Serra Verde"
    assert com_preposicao("Hostel Centro", "em") == "no Hostel Centro"
    assert com_preposicao("Paris Hotel", "de") == "do Paris Hotel"

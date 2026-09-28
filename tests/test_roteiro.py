"""Etapa 10: o roteiro de 2 minutos da apresentação, de ponta a ponta pelas telas."""
from datetime import timedelta

from app import relogio
from app.formatacao import normalizar
from app.models import Canal, Conversa, Hotel, TipoAcomodacao
from app.servicos.disponibilidade import proxima_sexta


def _msg(client, slug, tel, texto):
    return client.post("/api/mensagem", json={"hotel": slug, "telefone": tel, "texto": texto}).json()


def test_roteiro_da_demo(client, db):
    assert "Roteiro da demo" in client.get("/").text

    # 1. pet nos dois hotéis
    assert "10 kg" in _msg(client, "mare-alta", "(27) 94444-0001", "aceita pet?")["mensagens"][-1]["texto"]
    assert "nao aceita" in normalizar(_msg(client, "serra-verde", "(27) 94444-0001", "aceita pet?")["mensagens"][-1]["texto"])

    # 2. vaga daqui a ~2 semanas
    sexta = proxima_sexta(relogio.hoje(db)) + timedelta(days=7)
    texto = f"Tem vaga de {sexta:%d/%m} a {sexta + timedelta(days=2):%d/%m}?"
    resposta = _msg(client, "mare-alta", "(27) 94444-0002", texto)["mensagens"][-1]["texto"]
    assert "Suíte Casal" in resposta and "R$" in resposta

    # 3. desconto -> equipe responde e devolve ao bot
    tel = "(27) 94444-0003"
    antes = client.get("/api/equipe/pendencias", params={"hotel": "mare-alta"}).json()["assinatura"]
    assert _msg(client, "mare-alta", tel, "Consegue um desconto?")["status"] == "humano"
    assert client.get("/api/equipe/pendencias", params={"hotel": "mare-alta"}).json()["assinatura"] != antes
    assert "Consegue um desconto?" in client.get("/equipe?hotel=mare-alta").text
    conv = db.query(Conversa).filter_by(telefone=tel).one()
    client.post(f"/equipe/conversas/{conv.id}/responder", data={"hotel": "mare-alta", "texto": "Consigo 5% no Pix!"})
    client.post(f"/equipe/conversas/{conv.id}/devolver", data={"hotel": "mare-alta"})
    dados = client.get("/api/conversa", params={"hotel": "mare-alta", "telefone": tel}).json()
    assert dados["status"] == "bot" and any(m["autor"] == "equipe" for m in dados["mensagens"])

    # 4. reserva direta -> linha do tempo -> avançar até a próxima mensagem -> chat
    mare = db.query(Hotel).filter_by(slug="mare-alta").one()
    tipo = db.query(TipoAcomodacao).filter_by(hotel_id=mare.id, nome="Suíte Família").one()
    canal = db.query(Canal).filter_by(hotel_id=mare.id, tipo="whatsapp").one()
    hoje = relogio.hoje(db)
    tel = "(27) 94444-0004"
    r = client.post("/equipe/reservas", data={
        "hotel": "mare-alta", "nome": "Beatriz Demo", "telefone": tel, "consentimento": "1", "canal_id": canal.id,
        "acomodacao": f"tipo:{tipo.id}", "check_in": (hoje + timedelta(days=5)).isoformat(),
        "check_out": (hoje + timedelta(days=7)).isoformat(), "num_hospedes": 3,
    }, follow_redirects=False)
    reserva_id = int(r.headers["location"].split("/")[2].split("?")[0])
    assert "Linha do tempo" in client.get(f"/reservas/{reserva_id}").text
    for _ in range(3):
        client.post("/relogio/avancar", data={"hotel": "mare-alta", "passo": "proxima", "reserva_id": reserva_id,
                                              "voltar": f"/reservas/{reserva_id}"})
    bot = [m for m in client.get("/api/conversa", params={"hotel": "mare-alta", "telefone": tel}).json()["mensagens"]
           if m["autor"] == "bot"]
    assert len(bot) >= 3
    assert "confirmada" in bot[0]["texto"] and "Faltam 3 dias" in bot[1]["texto"]

    # 5. painel
    pagina = client.get("/painel?hotel=mare-alta").text
    assert "Ocupação por dia da semana" in pagina and "Receita bruta × líquida por canal" in pagina

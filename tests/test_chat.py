"""Etapa 2: telas e API do chat."""


def test_paginas_abrem(client):
    assert client.get("/").status_code == 200
    r = client.get("/chat?hotel=serra-verde")
    assert r.status_code == 200
    assert "Chalés Serra Verde" in r.text
    assert client.get("/chat?hotel=nao-existe").status_code == 404


def test_api_mensagem_responde_e_guarda_historico(client):
    tel = "(27) 91234-0001"
    r = client.post("/api/mensagem", json={"hotel": "mare-alta", "telefone": tel, "texto": "Aceita pet?"})
    dados = r.json()
    assert dados["status"] == "bot"
    assert [m["autor"] for m in dados["mensagens"]] == ["hospede", "bot"]
    assert "10 kg" in dados["mensagens"][-1]["texto"]

    r = client.get("/api/conversa", params={"hotel": "mare-alta", "telefone": tel})
    assert len(r.json()["mensagens"]) == 2
    # o mesmo telefone no outro hotel é outra conversa
    r = client.get("/api/conversa", params={"hotel": "serra-verde", "telefone": tel})
    assert r.json()["mensagens"] == []


def test_api_mostra_status_humano(client):
    tel = "27 91234-0002"
    r = client.post("/api/mensagem", json={"hotel": "serra-verde", "telefone": tel, "texto": "Quero falar com uma pessoa"})
    assert r.json()["status"] == "humano"
    assert r.json()["telefone"] == "(27) 91234-0002"

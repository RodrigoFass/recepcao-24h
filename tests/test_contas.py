"""Contas: cada hotel entra com o próprio usuário e só enxerga os próprios dados."""
from app.models import Alerta, Conversa, Hotel, Reserva


def _hotel(db, slug):
    return db.query(Hotel).filter_by(slug=slug).one()


def test_telas_da_equipe_exigem_login(anonimo):
    for caminho in ("/equipe", "/painel", "/admin", "/hoteis/novo", "/reservas/1"):
        r = anonimo.get(caminho, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/entrar", caminho
    assert anonimo.get("/api/equipe/pendencias").status_code == 401


def test_senha_errada_nao_entra(anonimo):
    r = anonimo.post("/entrar", data={"login": "marealta", "senha": "errada"}, follow_redirects=False)
    assert r.status_code == 401 and "incorretos" in r.text
    assert anonimo.get("/equipe", follow_redirects=False).status_code == 303


def test_atendimento_do_hospede_e_publico(anonimo):
    assert anonimo.get("/chat?hotel=mare-alta").status_code == 200
    r = anonimo.post("/api/mensagem", json={"hotel": "mare-alta", "telefone": "(27) 95555-0001", "texto": "Aceita pet?"})
    assert "10 kg" in r.json()["mensagens"][-1]["texto"]


def test_hotel_ve_so_o_proprio_hotel(cliente_mare, db):
    serra = _hotel(db, "serra-verde")
    pagina = cliente_mare.get("/equipe").text
    assert "Pousada Maré Alta" in pagina and serra.nome not in pagina
    # pedir outro hotel pelo endereço não funciona
    assert cliente_mare.get("/equipe?hotel=serra-verde").status_code == 404
    assert cliente_mare.get("/painel?hotel=serra-verde").status_code == 404
    reserva_serra = db.query(Reserva).filter_by(hotel_id=serra.id).first()
    assert cliente_mare.get(f"/reservas/{reserva_serra.id}").status_code == 404
    alerta_serra = db.query(Alerta).filter_by(hotel_id=serra.id).first()
    if alerta_serra:
        r = cliente_mare.post(f"/equipe/alertas/{alerta_serra.id}/resolver", data={})
        assert r.status_code == 404
    conv_serra = db.query(Conversa).filter_by(hotel_id=serra.id).first()
    r = cliente_mare.post(f"/equipe/conversas/{conv_serra.id}/responder", data={"texto": "oi"})
    assert r.status_code == 404


def test_so_a_administracao_cadastra_hotel(cliente_mare, client):
    assert cliente_mare.get("/hoteis/novo").status_code == 403
    assert cliente_mare.get("/admin").status_code == 403
    pagina = client.get("/admin").text
    assert "Pousada Maré Alta" in pagina and "Chalés Serra Verde" in pagina


def test_entrar_leva_cada_conta_para_a_sua_tela(anonimo):
    r = anonimo.post("/entrar", data={"login": "marealta", "senha": "mare1234"}, follow_redirects=False)
    assert r.headers["location"] == "/equipe"
    anonimo.post("/sair")
    r = anonimo.post("/entrar", data={"login": "admin", "senha": "admin1234"}, follow_redirects=False)
    assert r.headers["location"] == "/admin"


def test_cookie_adulterado_nao_vale(anonimo):
    anonimo.cookies.set("sessao_r24h", "1.assinatura-falsa")
    assert anonimo.get("/equipe", follow_redirects=False).status_code == 303

"""Etapa 4: cadastro M0 com a validação da Portaria MTur 28/2025."""
from app.formatacao import normalizar
from app.models import Canal, Hotel, ItemBaseConhecimento, TipoAcomodacao, Unidade
from app.servicos.cadastro import expandir_unidades, validar_intervalo


def formulario(**troca):
    dados = {
        "nome": "Hostel Teste Centro",
        "cidade": "Vitória (ES)",
        "endereco": "Rua Fictícia, 10",
        "telefone": "(27) 3000-9999",
        "checkin_hora": "15:00",
        "checkout_hora": "12:00",
        "modo_chegada": "recepcao_horario",
        "recepcao_inicio": "07:00",
        "recepcao_fim": "23:00",
        "early_checkin_permite": "1",
        "early_checkin_a_partir": "12:00",
        "early_checkin_preco": "35",
        "wifi_rede": "HostelTeste",
        "wifi_senha": "teste123",
        "aceita_pet": "",
        "tipo_nome_0": "Quarto Duplo",
        "tipo_capacidade_0": "2",
        "tipo_tarifa_0": "180",
        "tipo_unidades_0": "D1-D4",
        "tipo_nome_1": "Dormitório",
        "tipo_capacidade_1": "6",
        "tipo_tarifa_1": "90,50",
        "tipo_unidades_1": "Dorm A, Dorm B",
        "canal_booking": "1",
        "comissao_booking": "15",
        "canal_whatsapp": "1",
        "comissao_whatsapp": "0",
        "kb_cafe": "O café da manhã custa R$ 20 e é servido das 7h às 9h30.",
        "kb_cancelamento": "Cancelamento grátis até 3 dias antes.",
    }
    dados.update(troca)
    return dados


def test_validar_intervalo():
    erro = validar_intervalo("11:00", "15:00")
    assert erro and "Portaria MTur" in erro and "4h" in erro
    assert validar_intervalo("12:00", "15:00") is None
    assert validar_intervalo("12:00", "14:30") is None
    assert validar_intervalo("14:00", "12:00") is not None  # check-in antes do check-out


def test_expandir_unidades():
    assert expandir_unidades("101-104, 201") == ["101", "102", "103", "104", "201"]
    assert expandir_unidades("C1-C3") == ["C1", "C2", "C3"]
    assert expandir_unidades("Dorm A, Dorm B") == ["Dorm A", "Dorm B"]


def test_cadastro_recusa_intervalo_maior_que_3h(client, db):
    r = client.post("/hoteis/novo", data=formulario(checkout_hora="11:00", checkin_hora="15:00"))
    assert r.status_code == 400
    assert "Portaria MTur" in r.text
    assert 'value="Hostel Teste Centro"' in r.text  # o formulário volta preenchido
    assert db.query(Hotel).filter_by(nome="Hostel Teste Centro").count() == 0


def test_cadastro_aceita_e_hotel_funciona_no_chat(client, db):
    r = client.post("/hoteis/novo", data=formulario(), follow_redirects=False)
    assert r.status_code == 303, r.text
    assert r.headers["location"].startswith("/chat?hotel=hostel-teste-centro")

    hotel = db.query(Hotel).filter_by(slug="hostel-teste-centro").one()
    assert hotel.checkin_hora == "15:00" and hotel.checkout_hora == "12:00"
    tipos = {t.nome: t for t in db.query(TipoAcomodacao).filter_by(hotel_id=hotel.id)}
    assert tipos["Dormitório"].tarifa_base == 90.5
    unidades = {u.identificacao for u in db.query(Unidade).filter_by(hotel_id=hotel.id)}
    assert unidades == {"D1", "D2", "D3", "D4", "Dorm A", "Dorm B"}
    assert {c.tipo for c in db.query(Canal).filter_by(hotel_id=hotel.id)} == {"booking", "whatsapp"}
    categorias = {i.categoria for i in db.query(ItemBaseConhecimento).filter_by(hotel_id=hotel.id)}
    assert {"horarios", "early_checkin", "late_checkout", "wifi", "pet", "cafe", "cancelamento"} <= categorias

    def pergunta(texto):
        resp = client.post("/api/mensagem", json={"hotel": hotel.slug, "telefone": "(27) 97777-0001", "texto": texto})
        return resp.json()

    assert "15h" in pergunta("Qual o horário do check-in?")["mensagens"][-1]["texto"]
    assert "R$ 20" in pergunta("Tem café da manhã?")["mensagens"][-1]["texto"]
    assert "nao aceita" in normalizar(pergunta("Aceita pet?")["mensagens"][-1]["texto"])
    assert "nao oferece" in normalizar(pergunta("Posso fazer late checkout?")["mensagens"][-1]["texto"])
    assert "teste123" in pergunta("senha do wifi?")["mensagens"][-1]["texto"]
    # pergunta sem resposta na base vai para a equipe
    assert pergunta("Tem piscina?")["status"] == "humano"


def test_cadastro_recusa_slug_e_dados_faltando(client, db):
    r = client.post("/hoteis/novo", data=formulario(nome="", tipo_nome_0="", tipo_nome_1=""))
    assert r.status_code == 400
    assert "Informe o nome do hotel" in r.text
    assert "pelo menos um tipo de acomodação" in r.text


def test_tela_de_cadastro_abre(client):
    r = client.get("/hoteis/novo")
    assert r.status_code == 200
    assert "Portaria MTur" in r.text

"""Perguntas-modelo que geram a base de conhecimento de cada hotel (M0).

O hotel só responde às perguntas. As palavras-chave são as mesmas para todos
os hotéis e servem para a busca do modo demo. Algumas respostas são geradas
automaticamente a partir dos campos do cadastro (horários, early/late, wifi),
para não haver informação desencontrada.

Palavras-chave: separadas por vírgula. Uma palavra-chave com várias palavras
casa quando todas aparecem na mensagem (em qualquer ordem). Palavras com 4+
letras também casam como prefixo ("cachorr" casa "cachorro", "cachorrinho").
"""
from app.formatacao import hora_br, moeda_curta
from app.models import ItemBaseConhecimento

PERGUNTAS_MODELO = [
    {
        "categoria": "horarios",
        "pergunta": "Qual o horário de check-in e de check-out?",
        "palavras_chave": "checkin, checkout, horario checkin, horario checkout, hora checkin, hora checkout, "
        "horario entrada, horario saida, horas entrar, horas sair, horas cheg, horas libera, entrar, sair, desocupar",
        "automatica": True,
    },
    {
        "categoria": "early_checkin",
        "pergunta": "Posso fazer early check-in (entrar mais cedo)?",
        "palavras_chave": "early, early checkin, checkin antecipado, antecipad, cedo, entrar antes, cheg antes, "
        "cheg cedo, entrar cedo, cheg manha, entrar manha",
        "automatica": True,
    },
    {
        "categoria": "late_checkout",
        "pergunta": "Posso fazer late check-out (sair mais tarde)?",
        "palavras_chave": "late, late checkout, checkout tarde, sair tarde, sair depois, ficar mais tempo, "
        "checkout estendido, estender",
        "automatica": True,
    },
    {
        "categoria": "pet",
        "pergunta": "Vocês aceitam pet?",
        "palavras_chave": "pet, pets, cachorr, cao, caes, gato, gata, gatinh, animal, animais, bicho, estimacao, "
        "cadela, dog",
        "ajuda": "Aceita? Porte máximo, quantos por quarto, taxa.",
    },
    {
        "categoria": "cafe",
        "pergunta": "O café da manhã está incluso? Qual o horário?",
        "palavras_chave": "cafe, cafe manha, desjejum, breakfast, cesta cafe, horario cafe",
        "ajuda": "Incluso? Horário e onde é servido.",
    },
    {
        "categoria": "estacionamento",
        "pergunta": "Tem estacionamento?",
        "palavras_chave": "estacionamento, estacion, garagem, vaga carro, carro, moto, parar carro",
        "ajuda": "Tem? É pago? Quantas vagas? Precisa reservar?",
    },
    {
        "categoria": "wifi",
        "pergunta": "Tem wifi? Qual a senha?",
        "palavras_chave": "wifi, senha wifi, internet, rede wifi, sinal internet, sinal celular, celular",
        "automatica": True,
    },
    {
        "categoria": "como_chegar",
        "pergunta": "Qual o endereço e como chegar?",
        "palavras_chave": "endereco, como cheg, localizacao, onde fica, mapa, gps, estrada, rota, "
        "chegar carro, acesso, localiza",
        "ajuda": "Endereço, referência para o GPS, condições do acesso.",
    },
    {
        "categoria": "chegada_fora_horario",
        "pergunta": "Posso chegar à noite ou fora do horário da recepção?",
        "palavras_chave": "cheg tarde, cheg noite, madrugada, fora horario, cofre, chave, cheg depois, "
        "entrada funciona, pegar chave, pego chave, receb cheg, "
        "recepcao, fechadura, senha porta, senha fechadura, autoatendimento, 24h, 24 horas",
        "ajuda": "Até que horas tem gente para receber? Depois disso, como o hóspede entra?",
    },
    {
        "categoria": "criancas",
        "pergunta": "Aceitam crianças? Tem berço?",
        "palavras_chave": "crianca, criancas, bebe, berco, filho, filha, filhos, infantil, menor, idade",
        "ajuda": "Idade gratuita, berço, restrições por tipo de acomodação.",
    },
    {
        "categoria": "cancelamento",
        "pergunta": "Qual a política de cancelamento?",
        "palavras_chave": "cancel, reembolso, desist, desist reserva, perco reserva, multa, remarcar, devolucao, "
        "estorno",
        "ajuda": "Até quando é grátis e o que acontece depois.",
    },
    {
        "categoria": "pagamento",
        "pergunta": "Quais as formas de pagamento?",
        "palavras_chave": "pagamento, pagar, pix, cartao, credito, debito, dinheiro, sinal, parcel, boleto",
        "ajuda": "Formas aceitas, sinal para reserva direta, parcelamento.",
    },
    {
        "categoria": "lazer",
        "pergunta": "Tem piscina, lareira ou área de lazer?",
        "palavras_chave": "piscina, lareira, lenha, lazer, churrasqueira, jogos, sauna, hidromassagem, "
        "banheira, redario, playground",
        "ajuda": "Estrutura de lazer e horários.",
    },
    {
        "categoria": "silencio",
        "pergunta": "Tem horário de silêncio?",
        "palavras_chave": "silencio, barulho, som alto, festa, musica, lei silencio",
        "ajuda": "A partir de que horas.",
    },
    {
        "categoria": "roupa_cama",
        "pergunta": "Tem roupa de cama e toalhas?",
        "palavras_chave": "toalha, roupa cama, lencol, lencois, cobertor, edredom, travesseiro, enxoval",
        "ajuda": "Está incluso? Toalha de piscina/praia?",
    },
    {
        "categoria": "turismo",
        "pergunta": "O que tem para fazer perto? Quais os pontos turísticos?",
        "palavras_chave": "turistic, passeio, passeios, fazer perto, visitar, atracao, atracoes, restaurante, "
        "praia, cachoeira, trilha, regiao, conhecer, programa",
        "ajuda": "Praias, trilhas, restaurantes e distâncias.",
    },
]

CATEGORIAS = [p["categoria"] for p in PERGUNTAS_MODELO]
MODELO_POR_CATEGORIA = {p["categoria"]: p for p in PERGUNTAS_MODELO}


def respostas_automaticas(hotel) -> dict[str, str]:
    """Respostas derivadas dos campos estruturados do cadastro."""
    r = {}
    r["horarios"] = (
        f"O check-in é a partir das {hora_br(hotel.checkin_hora)} e o check-out é até as "
        f"{hora_br(hotel.checkout_hora)}."
    )

    if hotel.early_checkin_permite:
        a_partir = hotel.politica("early_checkin_a_partir")
        texto = "Sim, fazemos early check-in"
        if a_partir:
            texto += f" a partir das {hora_br(a_partir)}"
        if hotel.early_checkin_preco:
            texto += f" por {moeda_curta(hotel.early_checkin_preco)}"
        r["early_checkin"] = texto + ", sujeito a disponibilidade. É só avisar antes da chegada."
    else:
        r["early_checkin"] = f"Não oferecemos early check-in: a entrada é a partir das {hora_br(hotel.checkin_hora)}."

    if hotel.late_checkout_permite:
        ate = hotel.politica("late_checkout_ate")
        texto = "Sim, fazemos late check-out"
        if ate:
            texto += f" até as {hora_br(ate)}"
        if hotel.late_checkout_preco:
            texto += f" por {moeda_curta(hotel.late_checkout_preco)}"
        r["late_checkout"] = texto + ", sujeito a disponibilidade. Peça na recepção até a véspera."
    else:
        r["late_checkout"] = f"Não oferecemos late check-out: a saída é até as {hora_br(hotel.checkout_hora)}."

    rede, senha = hotel.politica("wifi_rede"), hotel.politica("wifi_senha")
    if rede:
        texto = f"Temos wifi gratuito. A rede é {rede}"
        texto += f" e a senha é {senha}." if senha else " (sem senha)."
        obs = hotel.politica("wifi_obs")
        if obs:
            texto += f" {obs}"
        r["wifi"] = texto
    return r


def gerar_base(db, hotel, respostas: dict[str, str], momento) -> list[ItemBaseConhecimento]:
    """Cria (ou recria) os itens da base do hotel a partir das respostas."""
    db.query(ItemBaseConhecimento).filter_by(hotel_id=hotel.id).delete()
    todas = {**respostas, **respostas_automaticas(hotel)}
    itens = []
    for modelo in PERGUNTAS_MODELO:
        resposta = (todas.get(modelo["categoria"]) or "").strip()
        if not resposta:
            continue  # sem resposta: o bot escala perguntas sobre o assunto
        item = ItemBaseConhecimento(
            hotel_id=hotel.id,
            categoria=modelo["categoria"],
            pergunta=modelo["pergunta"],
            palavras_chave=modelo["palavras_chave"],
            resposta=resposta,
            atualizado_em=momento,
        )
        db.add(item)
        itens.append(item)
    db.flush()
    return itens


def item_por_categoria(db, hotel_id: int, categoria: str):
    return db.query(ItemBaseConhecimento).filter_by(hotel_id=hotel_id, categoria=categoria).first()

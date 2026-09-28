"""Frases padrão do bot, iguais nos dois modos (demo e IA)."""
from app.formatacao import com_preposicao, hora_br

MARCA_RECUSA = "Desculpe, só posso ajudar com assuntos"


def recusa(hotel) -> str:
    return (
        f"{MARCA_RECUSA} {com_preposicao(hotel.nome, 'de')}: sua estadia, reservas, estrutura e dicas da região. "
        "Posso ajudar com algo sobre a hospedagem?"
    )


def apresentacao(hotel) -> str:
    return f"Olá! Sou o assistente virtual {com_preposicao(hotel.nome, 'de')}."


def horario_atendimento(hotel) -> str:
    if hotel.modo_chegada == "recepcao_24h":
        return "A recepção atende 24 horas."
    if hotel.recepcao_inicio and hotel.recepcao_fim:
        quem = "A recepção" if hotel.modo_chegada == "recepcao_horario" else "A equipe"
        return f"{quem} atende das {hora_br(hotel.recepcao_inicio)} às {hora_br(hotel.recepcao_fim)}."
    return ""


def escalonamento(hotel) -> str:
    texto = "Vou passar sua mensagem para a equipe, que vai te responder por aqui."
    atendimento = horario_atendimento(hotel)
    if atendimento:
        texto += f" {atendimento}"
    return texto


def identidade(hotel) -> str:
    return (
        f"Sou o assistente virtual {com_preposicao(hotel.nome, 'de')}, não uma pessoa. "
        "Posso responder dúvidas sobre a hospedagem a qualquer hora. Quer que eu chame alguém da equipe?"
    )

"""Pós-estadia (M4): nota de 1 a 5 e convite para avaliar.

- Nota de 1 a 3 gera um Alerta "nota_baixa" para a equipe entrar em contato.
- O convite para avaliar (canal de origem + Google) vai para TODOS,
  independentemente da nota e sem oferecer vantagem (o Google proíbe pedir
  avaliação só a quem gostou).
"""
import re
from urllib.parse import quote_plus

from app import relogio
from app.formatacao import normalizar
from app.models import Alerta, Avaliacao, Hospede, MensagemAgendada, Reserva

NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5}
RE_NOTA = re.compile(r"^(?:nota\s+|dou\s+(?:nota\s+)?)?([1-5]|um|uma|dois|duas|tres|quatro|cinco)\b(.*)$")


def reserva_aguardando_nota(db, hotel_id: int, telefone: str) -> Reserva | None:
    """Reserva cuja pesquisa já foi enviada a este telefone e ainda não tem nota."""
    msg = (
        db.query(MensagemAgendada)
        .join(Reserva)
        .join(Hospede, Reserva.hospede_id == Hospede.id)
        .filter(
            Reserva.hotel_id == hotel_id,
            Hospede.telefone == telefone,
            MensagemAgendada.etapa == "pesquisa",
            MensagemAgendada.status == "enviada",
        )
        .order_by(MensagemAgendada.enviar_em.desc())
        .first()
    )
    if msg is None or msg.reserva.avaliacao is not None:
        return None
    return msg.reserva


def ler_nota(texto: str) -> tuple[int, str] | None:
    achou = RE_NOTA.match(normalizar(texto))
    if not achou:
        return None
    valor = achou.group(1)
    nota = int(valor) if valor.isdigit() else NUMEROS[valor]
    # comentário = o que vier depois da nota, no texto original (com acentos)
    resto = re.match(r"^\s*(?:nota\s+|dou\s+(?:nota\s+)?)?(?:[1-5]|[^\W\d_]+)[\s,.;:!-]*(.*)$", texto.strip(),
                     re.I | re.S)
    comentario = resto.group(1).strip() if resto else ""
    if normalizar(comentario) in ("", "estrela", "estrelas", "de 5", "/5"):
        comentario = ""
    return nota, comentario


def link_google(hotel) -> str:
    return hotel.politica("google_avaliacao") or (
        "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{hotel.nome} {hotel.cidade}")
    )


def texto_convite(hotel, reserva: Reserva) -> str:
    canal = reserva.canal.tipo
    if canal == "airbnb":
        onde = "no Airbnb (em Viagens, no app) e no Google"
    elif canal == "booking":
        onde = "no Booking.com (pelo e-mail de avaliação que eles enviam) e no Google"
    else:
        onde = "no Google"
    return f"Se puder, conte como foi {onde}: {link_google(hotel)}"


def registrar_avaliacao(db, hotel, reserva: Reserva, nota: int, comentario: str = "") -> str:
    """Grava a nota, alerta a equipe se for baixa e devolve a resposta ao hóspede (com o convite)."""
    baixa = nota <= 3
    db.add(
        Avaliacao(
            reserva_id=reserva.id,
            nota=nota,
            comentario=comentario or None,
            alerta_enviado=baixa,
            convite_enviado=True,
        )
    )
    if baixa:
        nome = reserva.hospede.nome if reserva.hospede else "Hóspede"
        db.add(
            Alerta(
                hotel_id=hotel.id,
                tipo="nota_baixa",
                referencia=f"reserva:{reserva.id}",
                texto=(
                    f"Nota {nota} de {nome} (unidade {reserva.unidade.identificacao}, saída em "
                    f"{reserva.check_out:%d/%m})" + (f": \"{comentario}\"" if comentario else "")
                    + ". Entrar em contato com o hóspede."
                ),
                resolvido=False,
                criado_em=relogio.agora(db),
            )
        )
        abertura = (
            "Obrigado pela sinceridade. Sentimos muito que a estadia não foi como você esperava: "
            "alguém da equipe vai falar com você."
        )
    else:
        abertura = f"Que bom! Obrigado pela nota {nota}."
    db.flush()
    return f"{abertura} {texto_convite(hotel, reserva)}"


def tratar_resposta_pesquisa(db, hotel, conversa, texto: str) -> str | None:
    """Se o hóspede está respondendo à pesquisa com uma nota, registra e responde. Senão, None."""
    reserva = reserva_aguardando_nota(db, hotel.id, conversa.telefone)
    if reserva is None:
        return None
    lido = ler_nota(texto)
    if lido is None:
        return None
    nota, comentario = lido
    return registrar_avaliacao(db, hotel, reserva, nota, comentario)

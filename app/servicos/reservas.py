"""Criação e manutenção de reservas (M3), com as regras de sobreposição e de valor pendente."""
from datetime import date, datetime, timedelta

from app import relogio
from app.formatacao import formatar_telefone
from app.models import Alerta, Canal, Hospede, Reserva, Unidade
from app.servicos.disponibilidade import reservas_sobrepostas, unidades_livres


class ErroReserva(ValueError):
    pass


def valor_sugerido(tarifa: float, check_in: date, check_out: date) -> float:
    """Tarifa base por noite, com +20% nas noites de sexta e sábado."""
    total, d = 0.0, check_in
    while d < check_out:
        total += tarifa * (1.2 if d.weekday() in (4, 5) else 1.0)
        d += timedelta(days=1)
    return round(total, 2)


def criar_hospede(db, hotel, nome: str, telefone: str | None, email: str | None = None,
                  consentimento: bool = False, momento: datetime | None = None) -> Hospede:
    telefone = formatar_telefone(telefone) if telefone and telefone.strip() else None
    hosp = Hospede(
        hotel_id=hotel.id,
        nome=nome.strip() or "Hóspede",
        telefone=telefone,
        email=(email or "").strip() or None,
        consentimento_whatsapp_em=(momento or relogio.agora(db)) if (consentimento and telefone) else None,
        idioma="pt",
    )
    db.add(hosp)
    db.flush()
    return hosp


def _alerta(db, hotel_id: int, tipo: str, referencia: str, texto: str):
    db.add(Alerta(hotel_id=hotel_id, tipo=tipo, referencia=referencia, texto=texto, resolvido=False,
                  criado_em=relogio.agora(db)))


def criar_reserva(
    db,
    hotel,
    *,
    unidade_id: int,
    canal_id: int,
    check_in: date,
    check_out: date,
    hospede: Hospede | None = None,
    num_hospedes: int = 2,
    valor_total: float | None = None,
    origem: str = "manual",
    codigo_externo: str | None = None,
    aceitar_conflito: bool = False,
    validar_passado: bool = True,
) -> Reserva:
    """Cria a reserva e a jornada de mensagens.

    Criação manual sobreposta é recusada (ErroReserva). Importações passam
    aceitar_conflito=True: a reserva é gravada e gera um Alerta de conflito.
    """
    unidade = db.get(Unidade, unidade_id)
    canal = db.get(Canal, canal_id)
    if unidade is None or unidade.hotel_id != hotel.id:
        raise ErroReserva("Unidade não encontrada neste hotel.")
    if canal is None or canal.hotel_id != hotel.id:
        raise ErroReserva("Canal não encontrado neste hotel.")
    if check_out <= check_in:
        raise ErroReserva("A data de saída precisa ser depois da data de entrada.")
    hoje = relogio.hoje(db)
    if validar_passado and check_in < hoje:
        raise ErroReserva("A data de entrada não pode estar no passado.")
    if num_hospedes > unidade.tipo.capacidade:
        raise ErroReserva(
            f"A unidade {unidade.identificacao} ({unidade.tipo.nome}) acomoda até {unidade.tipo.capacidade} pessoas."
        )

    conflitos = reservas_sobrepostas(db, unidade.id, check_in, check_out)
    if conflitos and not aceitar_conflito:
        c = conflitos[0]
        raise ErroReserva(
            f"A unidade {unidade.identificacao} já está reservada de {c.check_in:%d/%m} a {c.check_out:%d/%m} "
            f"({c.canal.nome}). Escolha outra unidade ou outras datas."
        )

    reserva = Reserva(
        hotel_id=hotel.id,
        unidade_id=unidade.id,
        hospede_id=hospede.id if hospede else None,
        canal_id=canal.id,
        check_in=check_in,
        check_out=check_out,
        num_hospedes=num_hospedes,
        valor_total=valor_total,
        status="concluida" if check_out < hoje else "confirmada",
        origem=origem,
        codigo_externo=codigo_externo,
        criada_em=relogio.agora(db),
    )
    db.add(reserva)
    db.flush()

    for c in conflitos:
        _alerta(
            db, hotel.id, "conflito", f"reserva:{reserva.id}",
            f"Conflito na unidade {unidade.identificacao}: {canal.nome} de {check_in:%d/%m} a {check_out:%d/%m} "
            f"sobrepõe a reserva #{c.id} ({c.canal.nome}, {c.check_in:%d/%m} a {c.check_out:%d/%m}).",
        )
    if valor_total is None and canal.comissao_pct > 0:
        _alerta(
            db, hotel.id, "valor_pendente", f"reserva:{reserva.id}",
            f"Reserva {canal.nome} de {check_in:%d/%m} a {check_out:%d/%m} (unidade {unidade.identificacao}) "
            "sem valor. Complete pelo CSV ou digitando.",
        )

    from app.servicos import jornada

    jornada.gerar_jornada(db, reserva)
    return reserva


def escolher_unidade(db, hotel, tipo_id: int, check_in: date, check_out: date) -> Unidade:
    livres = unidades_livres(db, hotel.id, check_in, check_out, tipo_id)
    if not livres:
        raise ErroReserva("Não há unidade livre desse tipo nessas datas.")
    return livres[0]


def completar_valor(db, reserva: Reserva, valor: float):
    if valor <= 0:
        raise ErroReserva("Informe um valor maior que zero.")
    reserva.valor_total = round(valor, 2)
    for a in db.query(Alerta).filter_by(
        hotel_id=reserva.hotel_id, tipo="valor_pendente", referencia=f"reserva:{reserva.id}", resolvido=False
    ):
        a.resolvido = True
    db.commit()


def cancelar_reserva(db, reserva: Reserva):
    reserva.status = "cancelada"
    for m in reserva.mensagens_agendadas:
        if m.status == "pendente":
            m.status = "cancelada"
    db.commit()

"""Disponibilidade e sobreposição de reservas (M3)."""
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Reserva, TipoAcomodacao, Unidade

STATUS_ATIVOS = ("confirmada", "concluida")


def proxima_sexta(hoje: date) -> date:
    """Primeira sexta-feira depois de hoje (o "próximo fim de semana")."""
    dias = (4 - hoje.weekday()) % 7 or 7
    return hoje + timedelta(days=dias)


def reservas_sobrepostas(db, unidade_id: int, check_in: date, check_out: date, excluir_id: int | None = None):
    """Reservas não canceladas da unidade que dividem pelo menos uma noite com o intervalo."""
    q = db.query(Reserva).filter(
        Reserva.unidade_id == unidade_id,
        Reserva.status != "cancelada",
        Reserva.check_in < check_out,
        Reserva.check_out > check_in,
    )
    if excluir_id:
        q = q.filter(Reserva.id != excluir_id)
    return q.all()


def unidades_livres(db, hotel_id: int, check_in: date, check_out: date, tipo_id: int | None = None) -> list[Unidade]:
    ocupadas = select(Reserva.unidade_id).where(
        Reserva.hotel_id == hotel_id,
        Reserva.status != "cancelada",
        Reserva.check_in < check_out,
        Reserva.check_out > check_in,
    )
    q = db.query(Unidade).filter(Unidade.hotel_id == hotel_id, Unidade.ativa.is_(True), Unidade.id.not_in(ocupadas))
    if tipo_id:
        q = q.filter(Unidade.tipo_id == tipo_id)
    return q.order_by(Unidade.id).all()


def consultar(db, hotel_id: int, check_in: date, check_out: date, tipo_id: int | None = None, pessoas: int | None = None,
              hoje: date | None = None) -> dict:
    """Tipos com unidade livre no período, com tarifa base × noites.

    Nunca aplica desconto nem confirma reserva.
    """
    if check_out <= check_in:
        return {"erro": "A data de saída precisa ser depois da data de entrada."}
    if hoje and check_in < hoje:
        return {"erro": "A data de entrada já passou."}
    noites = (check_out - check_in).days
    if noites > 30:
        return {"erro": "Consigo consultar estadias de até 30 noites."}

    livres = unidades_livres(db, hotel_id, check_in, check_out, tipo_id)
    tipos: dict[int, dict] = {}
    for un in livres:
        t = un.tipo
        if pessoas and t.capacidade < pessoas:
            continue
        info = tipos.setdefault(
            t.id,
            {
                "tipo": t.nome,
                "capacidade": t.capacidade,
                "tarifa_base": t.tarifa_base,
                "total": round(t.tarifa_base * noites, 2),
                "livres": 0,
            },
        )
        info["livres"] += 1
    tipo_nome = db.get(TipoAcomodacao, tipo_id).nome if tipo_id else None
    return {
        "check_in": check_in,
        "check_out": check_out,
        "noites": noites,
        "tipo_pedido": tipo_nome,
        "pessoas": pessoas,
        "disponivel": bool(tipos),
        "tipos": sorted(tipos.values(), key=lambda x: x["tarifa_base"]),
    }

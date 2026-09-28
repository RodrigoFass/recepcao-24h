"""Indicadores do painel (M5).

Considera só reservas confirmadas ou concluídas e conta as noites dentro do
período [inicio, fim] (inclusive). Receita de reserva que atravessa o limite do
período entra proporcional às noites dentro dele.

- Ocupação = noites vendidas ÷ (unidades ativas × dias)
- ADR      = receita ÷ noites vendidas (só reservas com valor_total)
- RevPAR   = receita ÷ (unidades ativas × dias)
- Receita líquida por canal = receita do canal × (1 − comissão/100)
- % reservas diretas = reservas de canais sem comissão ÷ total de reservas
- Resolução do bot = conversas encerradas sem escalonamento ÷ total de conversas
"""
from datetime import date, datetime, timedelta

from app.formatacao import DIAS_SEMANA
from app.models import Avaliacao, Canal, Conversa, Mensagem, Reserva, Unidade

STATUS_CONTADOS = ("confirmada", "concluida")


def _dias(inicio: date, fim: date) -> list[date]:
    return [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]


def calcular(db, hotel_id: int, inicio: date, fim: date) -> dict:
    dias = _dias(inicio, fim)
    unidades = db.query(Unidade).filter_by(hotel_id=hotel_id, ativa=True).count()
    capacidade = unidades * len(dias)

    reservas = (
        db.query(Reserva)
        .filter(
            Reserva.hotel_id == hotel_id,
            Reserva.status.in_(STATUS_CONTADOS),
            Reserva.check_in <= fim,
            Reserva.check_out > inicio,
        )
        .all()
    )
    ocupadas_por_dia = {d: 0 for d in dias}
    canais = {
        c.id: {"nome": c.nome, "tipo": c.tipo, "comissao_pct": c.comissao_pct, "reservas": 0, "noites": 0,
               "bruta": 0.0, "liquida": 0.0}
        for c in db.query(Canal).filter_by(hotel_id=hotel_id).order_by(Canal.id)
    }
    noites_vendidas = noites_com_valor = diretas = 0
    receita = 0.0
    for r in reservas:
        noites = [d for d in dias if r.check_in <= d < r.check_out]
        if not noites:
            continue
        n = len(noites)
        noites_vendidas += n
        for d in noites:
            ocupadas_por_dia[d] += 1
        canal = canais[r.canal_id]
        canal["reservas"] += 1
        canal["noites"] += n
        if canal["comissao_pct"] == 0:
            diretas += 1
        if r.valor_total is not None:
            parte = r.valor_total * n / r.noites
            receita += parte
            noites_com_valor += n
            canal["bruta"] += parte
            canal["liquida"] += parte * (1 - canal["comissao_pct"] / 100)
    total_reservas = sum(c["reservas"] for c in canais.values())

    # ocupação por dia da semana (seg..dom)
    semana = []
    for wd in range(7):
        dias_wd = [d for d in dias if d.weekday() == wd]
        vagas = unidades * len(dias_wd)
        semana.append(sum(ocupadas_por_dia[d] for d in dias_wd) / vagas if vagas else None)

    # bot: conversas iniciadas no período em que o hóspede escreveu
    ini_dt, fim_dt = datetime.combine(inicio, datetime.min.time()), datetime.combine(fim + timedelta(days=1), datetime.min.time())
    conversas = [
        c for c in db.query(Conversa).filter(
            Conversa.hotel_id == hotel_id, Conversa.criada_em >= ini_dt, Conversa.criada_em < fim_dt
        )
        if db.query(Mensagem).filter_by(conversa_id=c.id, autor="hospede").first()
    ]
    resolvidas = [c for c in conversas if c.status == "encerrada" and not c.motivo_escalonamento]
    escaladas = [c for c in conversas if c.motivo_escalonamento]

    # nota média das estadias que terminaram no período
    notas = [
        a.nota
        for a in db.query(Avaliacao).join(Reserva).filter(
            Reserva.hotel_id == hotel_id, Reserva.check_out >= inicio, Reserva.check_out <= fim
        )
    ]

    receita_liquida = sum(c["liquida"] for c in canais.values())
    return {
        "inicio": inicio,
        "fim": fim,
        "dias": len(dias),
        "unidades": unidades,
        "noites_vendidas": noites_vendidas,
        "noites_com_valor": noites_com_valor,
        "reservas": total_reservas,
        "ocupacao": noites_vendidas / capacidade if capacidade else None,
        "adr": receita / noites_com_valor if noites_com_valor else None,
        "revpar": receita / capacidade if capacidade else None,
        "receita_bruta": receita,
        "receita_liquida": receita_liquida,
        "pct_diretas": diretas / total_reservas if total_reservas else None,
        "conversas": len(conversas),
        "conversas_resolvidas": len(resolvidas),
        "conversas_escaladas": len(escaladas),
        "resolucao_bot": len(resolvidas) / len(conversas) if conversas else None,
        "nota_media": sum(notas) / len(notas) if notas else None,
        "avaliacoes": len(notas),
        "ocupacao_diaria": [(d, ocupadas_por_dia[d] / unidades if unidades else 0) for d in dias],
        "ocupacao_semana": list(zip(DIAS_SEMANA, semana)),
        "canais": [c for c in canais.values() if c["reservas"]],
    }

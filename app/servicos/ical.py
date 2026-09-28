"""Leitura e escrita de arquivos iCal (.ics), sem biblioteca externa.

O iCal das OTAs só traz as datas ocupadas: cada VEVENT vira uma reserva sem
valor e sem hóspede.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass
class EventoIcal:
    uid: str
    inicio: date
    fim: date
    resumo: str = "Reservado"


def gerar_ics(nome: str, eventos: list[EventoIcal], carimbo: datetime) -> str:
    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Recepcao 24h//Prototipo//PT-BR",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{nome}",
    ]
    stamp = carimbo.strftime("%Y%m%dT%H%M%S")
    for ev in eventos:
        linhas += [
            "BEGIN:VEVENT",
            f"UID:{ev.uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{ev.inicio.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{ev.fim.strftime('%Y%m%d')}",
            f"SUMMARY:{ev.resumo}",
            "END:VEVENT",
        ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"


SUFIXO_UID = "@recepcao24h"


def exportar(db, hotel, unidade) -> str:
    """iCal de saída da unidade: bloqueia as datas de todas as reservas ativas, de qualquer canal.

    Não leva nome nem telefone do hóspede (só "Reservado")."""
    from app import relogio
    from app.models import Reserva

    hoje = relogio.hoje(db)
    reservas = (
        db.query(Reserva)
        .filter(Reserva.unidade_id == unidade.id, Reserva.status != "cancelada",
                Reserva.check_out >= hoje - timedelta(days=30))
        .order_by(Reserva.check_in)
        .all()
    )
    eventos = [EventoIcal(uid=f"reserva-{r.id}{SUFIXO_UID}", inicio=r.check_in, fim=r.check_out,
                          resumo="Reservado") for r in reservas]
    return gerar_ics(f"{hotel.nome} - {unidade.identificacao}", eventos, relogio.agora(db))


def importar(db, hotel, unidade, canal, conteudo: str, origem: str = "arquivo") -> dict:
    """Grava cada VEVENT como reserva sem valor e sem hóspede (origem "ical").

    - Evento que já foi importado (mesmo UID na mesma unidade) não duplica.
    - Evento que já terminou é ignorado; evento exportado por nós mesmos também.
    - Sobreposição com outra reserva: grava assim mesmo e cria Alerta de conflito.
    """
    from app import relogio
    from app.models import Alerta, CalendarioExterno, Reserva
    from app.servicos.reservas import criar_reserva

    hoje = relogio.hoje(db)
    resumo = {"importadas": 0, "ja_existiam": 0, "ignoradas": 0, "conflitos": 0}
    for ev in ler_ics(conteudo):
        if ev.fim <= hoje or ev.uid.endswith(SUFIXO_UID) or ev.fim <= ev.inicio:
            resumo["ignoradas"] += 1
            continue
        existente = (
            db.query(Reserva)
            .filter_by(unidade_id=unidade.id, codigo_externo=ev.uid)
            .filter(Reserva.status != "cancelada")
            .first()
        )
        if existente:
            resumo["ja_existiam"] += 1
            continue
        antes = db.query(Alerta).filter_by(hotel_id=hotel.id, tipo="conflito").count()
        criar_reserva(
            db, hotel,
            unidade_id=unidade.id, canal_id=canal.id, check_in=ev.inicio, check_out=ev.fim,
            hospede=None, num_hospedes=min(2, unidade.tipo.capacidade), valor_total=None,
            origem="ical", codigo_externo=ev.uid, aceitar_conflito=True, validar_passado=False,
        )
        db.flush()
        resumo["importadas"] += 1
        if db.query(Alerta).filter_by(hotel_id=hotel.id, tipo="conflito").count() > antes:
            resumo["conflitos"] += 1

    cal = db.query(CalendarioExterno).filter_by(hotel_id=hotel.id, unidade_id=unidade.id, canal_id=canal.id).first()
    if cal is None:
        cal = CalendarioExterno(hotel_id=hotel.id, unidade_id=unidade.id, canal_id=canal.id, ical_url=origem)
        db.add(cal)
    cal.ical_url = origem
    cal.ultima_sincronizacao = relogio.agora(db)
    db.commit()
    return resumo


def _data(valor: str) -> date:
    valor = valor.strip()
    if "T" in valor:
        return datetime.strptime(valor[:15], "%Y%m%dT%H%M%S").date()
    return datetime.strptime(valor[:8], "%Y%m%d").date()


def ler_ics(conteudo: str) -> list[EventoIcal]:
    """Extrai os VEVENTs (UID, DTSTART, DTEND, SUMMARY)."""
    # desdobra linhas continuadas (RFC 5545: linha que começa com espaço/tab)
    brutas = conteudo.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    linhas: list[str] = []
    for linha in brutas:
        if linha[:1] in (" ", "\t") and linhas:
            linhas[-1] += linha[1:]
        else:
            linhas.append(linha)

    eventos, atual = [], None
    for linha in linhas:
        if linha == "BEGIN:VEVENT":
            atual = {}
        elif linha == "END:VEVENT" and atual is not None:
            if "DTSTART" in atual:
                inicio = _data(atual["DTSTART"])
                fim = _data(atual["DTEND"]) if "DTEND" in atual else inicio + timedelta(days=1)
                eventos.append(
                    EventoIcal(
                        uid=atual.get("UID", f"sem-uid-{inicio.isoformat()}"),
                        inicio=inicio,
                        fim=fim,
                        resumo=atual.get("SUMMARY", "Reservado"),
                    )
                )
            atual = None
        elif atual is not None and ":" in linha:
            chave, valor = linha.split(":", 1)
            chave = chave.split(";", 1)[0].upper()
            atual[chave] = valor
    return eventos

"""Jornada de chegada (M2): mensagens agendadas por reserva.

| Etapa              | Quando                                        |
|--------------------|-----------------------------------------------|
| confirmacao        | na criação da reserva                         |
| boas_vindas        | check-in − 3 dias, 10h                        |
| hora_chegada       | check-in − 1 dia, 10h                         |
| instrucoes_entrada | dia do check-in, 3h antes do checkin_hora     |
| chegada            | dia do check-in, no checkin_hora              |
| pesquisa           | dia do check-out, 2h depois do checkout_hora  |

Com telefone e consentimento, as mensagens são "enviadas" pelo relógio
simulado (entram como mensagens do bot no chat daquele telefone). Sem isso,
ficam com meio = ota_manual: texto pronto para a equipe copiar no chat da OTA.
"""
from datetime import datetime, time, timedelta

from app import relogio
from app.formatacao import DIAS_SEMANA_LONGO, com_preposicao, hora_br, moeda
from app.models import Alerta, Conversa, Hotel, MensagemAgendada, Reserva
from app.servicos import conversas
from app.servicos.base_conhecimento import item_por_categoria

ETAPAS = ["confirmacao", "boas_vindas", "hora_chegada", "instrucoes_entrada", "chegada", "pesquisa"]
HORAS_SEM_RESPOSTA = 6
HORAS_CONVERSA_PARADA = 24


# --------------------------------------------------------------------- horários

def _hora(hhmm: str) -> time:
    h, m = hhmm.split(":")[:2]
    return time(int(h), int(m))


def horario_etapa(hotel: Hotel, reserva: Reserva, etapa: str, criada_em: datetime) -> datetime:
    ci, co = reserva.check_in, reserva.check_out
    if etapa == "confirmacao":
        return criada_em
    if etapa == "boas_vindas":
        return datetime.combine(ci - timedelta(days=3), time(10, 0))
    if etapa == "hora_chegada":
        return datetime.combine(ci - timedelta(days=1), time(10, 0))
    if etapa == "instrucoes_entrada":
        return datetime.combine(ci, _hora(hotel.checkin_hora)) - timedelta(hours=3)
    if etapa == "chegada":
        return datetime.combine(ci, _hora(hotel.checkin_hora))
    if etapa == "pesquisa":
        return datetime.combine(co, _hora(hotel.checkout_hora)) + timedelta(hours=2)
    raise ValueError(etapa)


def tem_whatsapp(reserva: Reserva) -> bool:
    h = reserva.hospede
    return bool(h and h.telefone and h.consentimento_whatsapp_em)


def codigo_acesso(reserva: Reserva) -> str:
    """Código fictício do cofre ou da fechadura, fixo por reserva."""
    return f"{(reserva.id * 7919 + 1234) % 10000:04d}"


# ----------------------------------------------------------------------- textos

def _primeiro_nome(reserva: Reserva) -> str:
    return reserva.hospede.nome.split()[0] if reserva.hospede else "tudo bem"


def _politica_early_late(hotel: Hotel) -> str:
    partes = []
    if hotel.early_checkin_permite:
        t = "early check-in"
        if hotel.politica("early_checkin_a_partir"):
            t += f" a partir das {hora_br(hotel.politica('early_checkin_a_partir'))}"
        if hotel.early_checkin_preco:
            t += f" por {moeda(hotel.early_checkin_preco)}"
        partes.append(t)
    if hotel.late_checkout_permite:
        t = "late check-out"
        if hotel.politica("late_checkout_ate"):
            t += f" até as {hora_br(hotel.politica('late_checkout_ate'))}"
        if hotel.late_checkout_preco:
            t += f" por {moeda(hotel.late_checkout_preco)}"
        partes.append(t)
    if not partes:
        return "Não oferecemos early check-in nem late check-out."
    texto = " e ".join(partes)
    texto = texto[0].upper() + texto[1:]
    if not hotel.early_checkin_permite:
        texto += " (não oferecemos early check-in)"
    if not hotel.late_checkout_permite:
        texto += " (não oferecemos late check-out)"
    return texto + ", sujeito a disponibilidade."


def _kb(db, hotel: Hotel, categoria: str) -> str | None:
    item = item_por_categoria(db, hotel.id, categoria)
    return item.resposta if item else None


def _texto_instrucoes(hotel: Hotel, reserva: Reserva) -> str:
    base = (hotel.politica("instrucoes_chegada") or "").strip()
    codigo = codigo_acesso(reserva)
    if hotel.modo_chegada == "autoatendimento":
        extra = f"Senha da fechadura da unidade {reserva.unidade.identificacao}: {codigo}."
    elif hotel.modo_chegada == "recepcao_horario" and hotel.recepcao_fim:
        extra = f"Código do cofre (para chegada depois das {hora_br(hotel.recepcao_fim)}): {codigo}."
    else:
        extra = ""
    return " ".join(p for p in (base, extra) if p)


def texto_etapa(db, hotel: Hotel, reserva: Reserva, etapa: str) -> str:
    nome = _primeiro_nome(reserva)
    ci, co = reserva.check_in, reserva.check_out
    n = reserva.noites
    if etapa == "confirmacao":
        linhas = [
            f"Olá, {nome}! Aqui é o assistente virtual {com_preposicao(hotel.nome, 'de')}. Sua reserva está confirmada:",
            f"• {reserva.unidade.tipo.nome} {reserva.unidade.identificacao}, de {ci:%d/%m} "
            f"({DIAS_SEMANA_LONGO[ci.weekday()]}) a {co:%d/%m} ({n} noite{'s' if n > 1 else ''}), "
            f"{reserva.num_hospedes} hóspede(s)"
            + (f", total {moeda(reserva.valor_total)}." if reserva.valor_total else "."),
            f"• Check-in a partir das {hora_br(hotel.checkin_hora)} e check-out até as {hora_br(hotel.checkout_hora)}.",
            f"• {_politica_early_late(hotel)}",
        ]
        cancelamento = _kb(db, hotel, "cancelamento")
        if cancelamento:
            linhas.append(f"• Cancelamento: {cancelamento}")
        linhas.append("Qualquer dúvida, é só responder esta mensagem.")
        return "\n".join(linhas)

    if etapa == "boas_vindas":
        linhas = [f"Oi, {nome}! Faltam 3 dias para a sua chegada {com_preposicao(hotel.nome, 'a')}.",
                  f"Endereço: {hotel.endereco}."]
        estacionamento = _kb(db, hotel, "estacionamento")
        if estacionamento:
            linhas.append(f"Estacionamento: {estacionamento}")
        if hotel.link_fnrh:
            linhas.append(
                "Para agilizar o check-in, faça o pré-check-in na FNRH Digital (a ficha oficial do Ministério "
                f"do Turismo): {hotel.link_fnrh}"
            )
        return "\n".join(linhas)

    if etapa == "hora_chegada":
        return (
            f"Oi, {nome}! Sua chegada é amanhã, {ci:%d/%m}. Qual o seu horário previsto de chegada? "
            f"(ex.: \"chego às 16h\"). O check-in é a partir das {hora_br(hotel.checkin_hora)}."
        )

    if etapa == "instrucoes_entrada":
        linhas = [f"Hoje é o dia, {nome}! Instruções para a sua chegada:", _texto_instrucoes(hotel, reserva)]
        if reserva.hora_prevista_chegada:
            linhas.append(f"Anotamos sua chegada prevista para as {hora_br(reserva.hora_prevista_chegada)}.")
        return "\n".join(l for l in linhas if l)

    if etapa == "chegada":
        linhas = [f"Seja bem-vindo(a) {com_preposicao(hotel.nome, 'a')}, {nome}!"]
        if hotel.politica("wifi_rede"):
            linhas.append(f"Wifi: rede {hotel.politica('wifi_rede')}, senha {hotel.politica('wifi_senha') or '(sem senha)'}.")
        cafe = _kb(db, hotel, "cafe")
        if cafe:
            linhas.append(f"Café da manhã: {cafe}")
        contato = hotel.politica("contato_emergencia") or hotel.whatsapp or hotel.telefone
        if contato:
            linhas.append(f"Emergência ou qualquer ajuda: {contato}.")
        linhas.append("Boa estadia! Se tiver dúvidas, é só mandar mensagem aqui.")
        return "\n".join(linhas)

    if etapa == "pesquisa":
        return (
            f"Obrigado pela estadia, {nome}! De 1 a 5, que nota você dá para a sua experiência "
            f"{com_preposicao(hotel.nome, 'em')}? "
            "Responda só com o número."
        )
    raise ValueError(etapa)


def texto_reenvio(reserva: Reserva) -> str:
    return (
        f"Oi, {_primeiro_nome(reserva)}! Só confirmando: qual o horário previsto da sua chegada em "
        f"{reserva.check_in:%d/%m}? Assim deixamos tudo pronto para te receber."
    )


# -------------------------------------------------------------------- geração

def gerar_jornada(db, reserva: Reserva, momento: datetime | None = None, entregar: bool = True):
    """Cria as 6 mensagens da reserva.

    Reserva criada com menos de 3 dias de antecedência: as etapas já vencidas
    (exceto a pesquisa) são enviadas logo depois da confirmação, em ordem.
    """
    hotel = db.get(Hotel, reserva.hotel_id)
    momento = momento or reserva.criada_em
    meio = "whatsapp" if tem_whatsapp(reserva) else "ota_manual"
    msgs = []
    for i, etapa in enumerate(ETAPAS):
        quando = horario_etapa(hotel, reserva, etapa, momento)
        if etapa != "pesquisa" and quando < momento:
            quando = momento + timedelta(seconds=i)  # atrasada: vai junto, logo depois da confirmação
        m = MensagemAgendada(
            reserva=reserva, etapa=etapa, enviar_em=quando, status="pendente",
            texto=texto_etapa(db, hotel, reserva, etapa), meio=meio,
        )
        db.add(m)
        msgs.append(m)
    db.flush()
    if entregar and meio == "whatsapp":
        for m in msgs:
            if m.enviar_em <= momento + timedelta(seconds=len(ETAPAS)):
                _entregar(db, hotel, m, m.enviar_em)
    return msgs


def _entregar(db, hotel: Hotel, msg: MensagemAgendada, quando: datetime, texto: str | None = None):
    """Coloca a mensagem no chat do telefone do hóspede, como mensagem do bot."""
    reserva = msg.reserva
    if texto is None:
        msg.texto = texto_etapa(db, hotel, reserva, msg.etapa)  # atualiza (ex.: hora prevista já informada)
        texto = msg.texto
    conv = conversas.conversa_ativa(db, hotel.id, reserva.hospede.telefone, criar=True, momento=quando)
    if conv.hospede_id is None:
        conv.hospede_id = reserva.hospede_id
    conversas.registrar(db, conv, "bot", texto, quando)
    msg.status = "enviada"


# ------------------------------------------------------------------ processamento

def _pendentes(db, ate: datetime):
    return (
        db.query(MensagemAgendada)
        .join(Reserva)
        .filter(
            MensagemAgendada.status == "pendente",
            MensagemAgendada.meio == "whatsapp",
            MensagemAgendada.enviar_em <= ate,
            Reserva.status != "cancelada",
        )
        .order_by(MensagemAgendada.enviar_em, MensagemAgendada.id)
        .all()
    )


def _aguardando_hora(db, status: str):
    return (
        db.query(MensagemAgendada)
        .join(Reserva)
        .filter(
            MensagemAgendada.etapa == "hora_chegada",
            MensagemAgendada.status == status,
            MensagemAgendada.meio == "whatsapp",
            Reserva.hora_prevista_chegada.is_(None),
            Reserva.status == "confirmada",
        )
        .all()
    )


def processar_ate(db, momento: datetime) -> dict:
    """Entrega o que venceu até `momento` (em ordem) e aplica os prazos de resposta."""
    resumo = {"enviadas": 0, "reenviadas": 0, "sem_resposta": 0}
    for m in _pendentes(db, momento):
        _entregar(db, db.get(Hotel, m.reserva.hotel_id), m, m.enviar_em)
        resumo["enviadas"] += 1
    db.flush()

    prazo = timedelta(hours=HORAS_SEM_RESPOSTA)
    for m in _aguardando_hora(db, "enviada"):
        if m.enviar_em + prazo <= momento:
            hotel = db.get(Hotel, m.reserva.hotel_id)
            _entregar(db, hotel, m, m.enviar_em + prazo, texto=texto_reenvio(m.reserva))
            m.status = "reenviada"
            resumo["reenviadas"] += 1
    db.flush()
    for m in _aguardando_hora(db, "reenviada"):
        if m.enviar_em + 2 * prazo <= momento:
            m.status = "sem_resposta"
            r = m.reserva
            db.add(
                Alerta(
                    hotel_id=r.hotel_id,
                    tipo="sem_resposta",
                    referencia=f"reserva:{r.id}",
                    texto=(
                        f"{r.hospede.nome} (unidade {r.unidade.identificacao}, chegada {r.check_in:%d/%m}) não "
                        f"informou o horário de chegada, nem depois do reenvio. Ligar para {r.hospede.telefone}."
                    ),
                    resolvido=False,
                    criado_em=m.enviar_em + 2 * prazo,
                )
            )
            resumo["sem_resposta"] += 1

    # reservas que já saíram viram "concluida"
    for r in db.query(Reserva).filter(Reserva.status == "confirmada", Reserva.check_out < momento.date()):
        r.status = "concluida"
    # conversas paradas há 24h com o bot são encerradas
    limite = momento - timedelta(hours=HORAS_CONVERSA_PARADA)
    for c in db.query(Conversa).filter(Conversa.status == "bot", Conversa.atualizada_em < limite):
        c.status = "encerrada"
    db.commit()
    return resumo


def proximo_evento(db, hotel_id: int | None = None, reserva_id: int | None = None) -> datetime | None:
    """Próximo instante em que algo acontece (envio, reenvio ou prazo de resposta)."""
    agora = relogio.agora(db)
    q = (
        db.query(MensagemAgendada)
        .join(Reserva)
        .filter(MensagemAgendada.meio == "whatsapp", Reserva.status != "cancelada")
    )
    if hotel_id:
        q = q.filter(Reserva.hotel_id == hotel_id)
    if reserva_id:
        q = q.filter(Reserva.id == reserva_id)
    candidatos = []
    prazo = timedelta(hours=HORAS_SEM_RESPOSTA)
    for m in q.filter(MensagemAgendada.status.in_(["pendente", "enviada", "reenviada"])):
        if m.status == "pendente":
            candidatos.append(m.enviar_em)
        elif m.etapa == "hora_chegada" and m.reserva.hora_prevista_chegada is None and m.reserva.status == "confirmada":
            candidatos.append(m.enviar_em + (prazo if m.status == "enviada" else 2 * prazo))
    futuros = [c for c in candidatos if c > agora]
    return min(futuros) if futuros else None

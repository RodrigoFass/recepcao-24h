"""Prompt de sistema do modo IA, montado por hotel.

Leva só os dados e a base de conhecimento do hotel da conversa: o modelo não
recebe nada de outro hotel.
"""
from app import relogio
from app.bot import textos
from app.bot.ferramentas import reserva_ativa_do_telefone
from app.formatacao import DIAS_SEMANA_LONGO, com_preposicao, hora_br, moeda_curta
from app.models import ItemBaseConhecimento, TipoAcomodacao

NOMES_MODO_CHEGADA = {
    "recepcao_24h": "recepção 24 horas",
    "recepcao_horario": "recepção com horário",
    "autoatendimento": "autoatendimento (senha na fechadura)",
}


def _dados_hotel(db, hotel) -> str:
    linhas = [
        f"- Nome: {hotel.nome} ({hotel.cidade})",
        f"- Endereço: {hotel.endereco}",
        f"- Check-in a partir das {hora_br(hotel.checkin_hora)}; check-out até as {hora_br(hotel.checkout_hora)}.",
    ]
    if hotel.early_checkin_permite:
        linhas.append(
            f"- Early check-in: sim, a partir das {hora_br(hotel.politica('early_checkin_a_partir'))} por "
            f"{moeda_curta(hotel.early_checkin_preco)}, sujeito a disponibilidade."
        )
    else:
        linhas.append("- Early check-in: não oferece.")
    if hotel.late_checkout_permite:
        linhas.append(
            f"- Late check-out: sim, até as {hora_br(hotel.politica('late_checkout_ate'))} por "
            f"{moeda_curta(hotel.late_checkout_preco)}, sujeito a disponibilidade."
        )
    else:
        linhas.append("- Late check-out: não oferece.")
    linhas.append(f"- Chegada: {NOMES_MODO_CHEGADA.get(hotel.modo_chegada, hotel.modo_chegada)}. "
                  f"{textos.horario_atendimento(hotel)}")
    if hotel.politica("instrucoes_chegada"):
        linhas.append(f"- Instruções de entrada: {hotel.politica('instrucoes_chegada')} "
                      "(o código/senha é enviado por mensagem no dia; nunca invente um código).")
    if hotel.politica("wifi_rede"):
        linhas.append(f"- Wifi: rede {hotel.politica('wifi_rede')}, senha {hotel.politica('wifi_senha') or '(sem senha)'}.")
    if hotel.link_fnrh:
        linhas.append(f"- Pré-check-in oficial (FNRH Digital): {hotel.link_fnrh}")
    tipos = db.query(TipoAcomodacao).filter_by(hotel_id=hotel.id).order_by(TipoAcomodacao.tarifa_base).all()
    for t in tipos:
        linhas.append(f"- Acomodação \"{t.nome}\": até {t.capacidade} pessoas, tarifa base {moeda_curta(t.tarifa_base)} por noite.")
    return "\n".join(linhas)


def _base(db, hotel) -> str:
    itens = db.query(ItemBaseConhecimento).filter_by(hotel_id=hotel.id).order_by(ItemBaseConhecimento.id).all()
    return "\n".join(f"P: {i.pergunta}\nR: {i.resposta}" for i in itens) or "(vazia)"


def montar_prompt(db, hotel, conversa, ja_se_apresentou: bool) -> str:
    agora = relogio.agora(db)
    reserva = reserva_ativa_do_telefone(db, hotel.id, conversa.telefone)
    if reserva:
        contexto_reserva = (
            f"Este telefone tem reserva confirmada: {reserva.unidade.tipo.nome} {reserva.unidade.identificacao}, "
            f"de {reserva.check_in:%d/%m/%Y} a {reserva.check_out:%d/%m/%Y}"
            + (f", chegada prevista às {hora_br(reserva.hora_prevista_chegada)}." if reserva.hora_prevista_chegada else ".")
        )
    else:
        contexto_reserva = "Este telefone não tem reserva ativa neste hotel."

    do_hotel = com_preposicao(hotel.nome, "de")
    return f"""Você é o assistente virtual {do_hotel}. Você atende hóspedes pelo WhatsApp, em português do Brasil.

REGRAS
1. Use SOMENTE os dados do hotel, a base de conhecimento abaixo e o resultado das ferramentas. Não invente nada e não use conhecimento geral sobre hotéis, cidades ou outros estabelecimentos. Nunca mencione outro hotel.
2. Escopo: o hotel, a estadia, a reserva e a região (conforme a base). Para qualquer outro assunto, responda exatamente com a frase: "{textos.recusa(hotel)}" e não chame ferramenta nenhuma.
3. {"Você já se apresentou nesta conversa; não se apresente de novo." if ja_se_apresentou else f'Esta é a primeira resposta da conversa: comece se apresentando como "assistente virtual {do_hotel}".'}
4. Se perguntarem se você é humano, diga que é um assistente virtual e ofereça chamar alguém da equipe (não escale só por isso).
5. Chame escalar_para_humano quando: o hóspede pedir desconto ou quiser negociar preço; fizer uma reclamação; pedir atendente, pessoa ou gerente; fizer uma pergunta sobre o hotel que os dados e a base não respondem; ou aceitar sua oferta de chamar a equipe ou de confirmar uma reserva. Depois de escalar, avise que a equipe vai responder por aqui e informe: "{textos.horario_atendimento(hotel) or 'a equipe responde assim que possível.'}"
6. Disponibilidade: chame consultar_disponibilidade com datas no formato AAAA-MM-DD (data sem ano = a próxima ocorrência a partir de hoje). Informe os tipos livres com a tarifa base e o total (tarifa base × noites). Nunca dê desconto e nunca confirme uma reserva: ofereça passar para a equipe confirmar.
7. Se o hóspede informar o horário de chegada (ex.: "chego às 23h"), chame registrar_hora_chegada com a hora no formato HH:MM.
8. Responda em no máximo 4 frases, numa mensagem só, em texto simples (sem markdown, sem listas).

DADOS DO HOTEL
{_dados_hotel(db, hotel)}

BASE DE CONHECIMENTO
{_base(db, hotel)}

CONTEXTO
Agora: {DIAS_SEMANA_LONGO[agora.weekday()]}, {agora:%d/%m/%Y} às {agora:%H:%M}.
Telefone do hóspede: {conversa.telefone}. {contexto_reserva}"""

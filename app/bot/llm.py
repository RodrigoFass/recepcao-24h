"""Modo IA: Claude com tool use.

- Prompt de sistema montado por hotel (dados + base + regras), em bot/prompt.py.
- Histórico: as últimas 10 mensagens da conversa.
- Ferramentas: consultar_disponibilidade, escalar_para_humano e
  registrar_hora_chegada. O hotel_id vem da conversa e não é parâmetro exposto.

Qualquer falha da API vira ErroIA; quem chama responde pelo modo demo.
"""
import json
import os
from datetime import date

import anthropic

from app.bot import ferramentas
from app.bot.prompt import montar_prompt

MODELO_PADRAO = "claude-haiku-4-5-20251001"
MAX_RODADAS = 5
HISTORICO = 10

FERRAMENTAS = [
    {
        "name": "consultar_disponibilidade",
        "description": (
            "Consulta quais tipos de acomodação deste hotel têm unidade livre no período e a tarifa base. "
            "Use quando o hóspede perguntar por vaga, disponibilidade ou preço para datas específicas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "check_in": {"type": "string", "description": "Data de entrada no formato AAAA-MM-DD."},
                "check_out": {"type": "string", "description": "Data de saída no formato AAAA-MM-DD."},
                "tipo": {"type": "string", "description": "Nome do tipo de acomodação, se o hóspede pediu um."},
            },
            "required": ["check_in", "check_out"],
        },
    },
    {
        "name": "escalar_para_humano",
        "description": (
            "Passa a conversa para a equipe do hotel; depois disso o assistente para de responder nela. "
            "Use para desconto/negociação, reclamação, pedido de atendente, pergunta sobre o hotel sem resposta "
            "na base, ou quando o hóspede aceitar falar com a equipe ou confirmar uma reserva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"motivo": {"type": "string", "description": "Motivo curto, ex.: 'Pedido de desconto'."}},
            "required": ["motivo"],
        },
    },
    {
        "name": "registrar_hora_chegada",
        "description": "Registra o horário previsto de chegada na reserva ativa do telefone desta conversa.",
        "input_schema": {
            "type": "object",
            "properties": {"hora": {"type": "string", "description": "Horário no formato HH:MM (24h)."}},
            "required": ["hora"],
        },
    },
]


class ErroIA(Exception):
    pass


def modelo() -> str:
    return os.environ.get("MODEL") or MODELO_PADRAO


def _historico(conversa) -> list[dict]:
    """Últimas mensagens como turnos user/assistant (a primeira precisa ser do hóspede)."""
    msgs = [m for m in conversa.mensagens if m.autor != "sistema"][-HISTORICO:]
    while msgs and msgs[0].autor != "hospede":
        msgs = msgs[1:]
    turnos: list[dict] = []
    for m in msgs:
        papel = "user" if m.autor == "hospede" else "assistant"
        texto = f"[Resposta da equipe do hotel] {m.texto}" if m.autor == "equipe" else m.texto
        if turnos and turnos[-1]["role"] == papel:
            turnos[-1]["content"] += "\n\n" + texto
        else:
            turnos.append({"role": papel, "content": texto})
    return turnos


def _serializar(valor):
    if isinstance(valor, date):
        return valor.isoformat()
    raise TypeError(type(valor))


def _executar(db, conversa, nome: str, entrada: dict) -> tuple[str, bool]:
    """Roda a ferramenta. Devolve (conteúdo JSON, é_erro)."""
    try:
        if nome == "consultar_disponibilidade":
            resultado = ferramentas.consultar_disponibilidade(
                db,
                conversa,
                date.fromisoformat(entrada["check_in"]),
                date.fromisoformat(entrada["check_out"]),
                entrada.get("tipo") or None,
            )
            if "erro" not in resultado:
                resultado["observacao"] = "Valores da tarifa base. Não ofereça desconto nem confirme a reserva."
        elif nome == "escalar_para_humano":
            resultado = ferramentas.escalar_para_humano(db, conversa, entrada.get("motivo") or "Pedido do hóspede")
        elif nome == "registrar_hora_chegada":
            resultado = ferramentas.registrar_hora_chegada(db, conversa, entrada["hora"])
        else:
            return json.dumps({"erro": f"Ferramenta desconhecida: {nome}"}), True
    except (KeyError, ValueError) as erro:
        return json.dumps({"erro": f"Parâmetro inválido: {erro}"}, ensure_ascii=False), True
    erro = "erro" in resultado or resultado.get("ok") is False
    return json.dumps(resultado, ensure_ascii=False, default=_serializar), erro


def responder(db, hotel, conversa, texto: str) -> str:
    """Resposta do Claude para a mensagem do hóspede (já gravada na conversa)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErroIA("ANTHROPIC_API_KEY não definida")
    cliente = anthropic.Anthropic(timeout=30.0, max_retries=1)
    ja_se_apresentou = any(m.autor == "bot" for m in conversa.mensagens[:-1])
    sistema = montar_prompt(db, hotel, conversa, ja_se_apresentou)
    mensagens = _historico(conversa)
    if not mensagens:
        mensagens = [{"role": "user", "content": texto}]

    try:
        for _ in range(MAX_RODADAS):
            resposta = cliente.messages.create(
                model=modelo(),
                max_tokens=2048,
                system=sistema,
                tools=FERRAMENTAS,
                messages=mensagens,
            )
            if resposta.stop_reason == "tool_use":
                mensagens.append({"role": "assistant", "content": resposta.content})
                resultados = []
                for bloco in resposta.content:
                    if bloco.type == "tool_use":
                        conteudo, erro = _executar(db, conversa, bloco.name, bloco.input)
                        resultados.append(
                            {"type": "tool_result", "tool_use_id": bloco.id, "content": conteudo, "is_error": erro}
                        )
                mensagens.append({"role": "user", "content": resultados})
                continue
            if resposta.stop_reason == "refusal":
                raise ErroIA("o modelo recusou a mensagem")
            final = " ".join(b.text for b in resposta.content if b.type == "text").strip()
            if not final:
                raise ErroIA("resposta vazia")
            return final
    except anthropic.APIConnectionError as erro:
        raise ErroIA(f"sem conexão com a API: {erro}") from erro
    except anthropic.APIStatusError as erro:
        raise ErroIA(f"erro da API ({erro.status_code}): {erro.message}") from erro
    raise ErroIA("o modelo não terminou em poucas rodadas")

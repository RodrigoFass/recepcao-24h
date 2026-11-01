"""Modo IA com o Gemini (Google), no plano gratuito da API.

Mesmo prompt, mesmo histórico e mesmas três ferramentas do modo IA com o
Claude (bot/llm.py); só muda o cliente. Chave em GEMINI_API_KEY (gratuita no
Google AI Studio); modelo em GEMINI_MODEL.

Qualquer falha da API vira ErroIA; quem chama responde pelas regras.
"""
import json
import os

import httpx
from google import genai
from google.genai import errors, types

from app.bot import llm
from app.bot.llm import ErroIA
from app.bot.prompt import montar_prompt

MODELO_PADRAO = "gemini-3.5-flash-lite"


def modelo() -> str:
    return os.environ.get("GEMINI_MODEL") or MODELO_PADRAO


FERRAMENTAS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=f["name"], description=f["description"],
                                      parameters_json_schema=f["input_schema"])
            for f in llm.FERRAMENTAS
        ]
    )
]


def _historico(conversa) -> list[types.Content]:
    """Os mesmos turnos do modo Claude, no formato do Gemini (assistant → model)."""
    return [
        types.Content(role="user" if t["role"] == "user" else "model", parts=[types.Part(text=t["content"])])
        for t in llm._historico(conversa)
    ]


def responder(db, hotel, conversa, texto: str) -> str:
    """Resposta do Gemini para a mensagem do hóspede (já gravada na conversa)."""
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise ErroIA("GEMINI_API_KEY não definida")
    cliente = genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=30_000))
    ja_se_apresentou = any(m.autor == "bot" for m in conversa.mensagens[:-1])
    config = types.GenerateContentConfig(
        system_instruction=montar_prompt(db, hotel, conversa, ja_se_apresentou),
        tools=FERRAMENTAS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    conteudos = _historico(conversa) or [types.Content(role="user", parts=[types.Part(text=texto)])]

    try:
        for _ in range(llm.MAX_RODADAS):
            resposta = cliente.models.generate_content(model=modelo(), contents=conteudos, config=config)
            chamadas = resposta.function_calls or []
            if chamadas:
                # devolve o turno do modelo inteiro (mantém as assinaturas de raciocínio do Gemini)
                conteudos.append(resposta.candidates[0].content)
                partes = []
                for chamada in chamadas:
                    conteudo, erro = llm._executar(db, conversa, chamada.name, dict(chamada.args or {}))
                    partes.append(types.Part.from_function_response(
                        name=chamada.name, response={"erro" if erro else "resultado": json.loads(conteudo)}))
                conteudos.append(types.Content(role="user", parts=partes))
                continue
            final = (resposta.text or "").strip()
            if not final:
                raise ErroIA("resposta vazia")
            return final
    except errors.APIError as erro:
        raise ErroIA(f"erro da API do Gemini ({erro.code}): {erro.message}") from erro
    except httpx.HTTPError as erro:
        raise ErroIA(f"sem conexão com a API do Gemini: {erro}") from erro
    raise ErroIA("o modelo não terminou em poucas rodadas")

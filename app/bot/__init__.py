"""Escolha do modo do bot.

Modo demo: ativo sem ANTHROPIC_API_KEY ou com DEMO_MODE=1.
Modo IA: com a chave (e sem DEMO_MODE). Se a chamada à API falhar (ex.:
sem internet), a mensagem é respondida pelo modo demo.
"""
import logging
import os

log = logging.getLogger("recepcao24h.bot")

# modo que de fato respondeu a última mensagem ("demo" ou "ia"); a bancada usa
ultimo_modo = "demo"


def modo() -> str:
    forcado = os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "sim", "yes")
    if forcado or not os.environ.get("ANTHROPIC_API_KEY"):
        return "demo"
    return "ia"


def responder(db, hotel, conversa, texto: str, forcar_modo: str | None = None) -> str:
    global ultimo_modo
    from app.bot import demo

    if (forcar_modo or modo()) == "ia":
        from app.bot import llm

        try:
            resposta = llm.responder(db, hotel, conversa, texto)
            ultimo_modo = "ia"
            return resposta
        except llm.ErroIA as erro:
            log.warning("Falha no modo IA (%s); respondendo pelo modo demo.", erro)
            db.rollback()
    ultimo_modo = "demo"
    return demo.responder(db, hotel, conversa, texto)

"""Escolha do modo do bot.

Modo IA: com GEMINI_API_KEY (Gemini, plano gratuito) ou ANTHROPIC_API_KEY
(Claude); se as duas existirem, usa o Gemini. Sem chave (ou com DEMO_MODE=1),
modo demo: regras + busca na base. Se a chamada à IA falhar (ex.: sem
internet), a mensagem é respondida pelas regras, sem aviso ao hóspede.
"""
import logging
import os

log = logging.getLogger("recepcao24h.bot")

# modo que de fato respondeu a última mensagem ("demo" ou "ia"); a bancada usa
ultimo_modo = "demo"


def provedor() -> str | None:
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def modo() -> str:
    forcado = os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "sim", "yes")
    if forcado or provedor() is None:
        return "demo"
    return "ia"


def responder(db, hotel, conversa, texto: str, forcar_modo: str | None = None) -> str:
    global ultimo_modo
    from app.bot import demo

    if (forcar_modo or modo()) == "ia":
        from app.bot import llm

        try:
            if provedor() == "gemini":
                from app.bot import gemini

                resposta = gemini.responder(db, hotel, conversa, texto)
            else:
                resposta = llm.responder(db, hotel, conversa, texto)
            ultimo_modo = "ia"
            return resposta
        except llm.ErroIA as erro:
            log.warning("Falha no modo IA (%s); respondendo pelo modo demo.", erro)
            db.rollback()
    ultimo_modo = "demo"
    return demo.responder(db, hotel, conversa, texto)

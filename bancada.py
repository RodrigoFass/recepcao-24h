"""Teste de bancada do bot.

Uso:  python bancada.py [--modo demo|ia] [--entrada data/perguntas_teste.csv] [--saida resultados_bancada.csv]

Lê as perguntas (colunas hotel;pergunta;esperado), faz cada uma numa conversa
nova e grava as respostas com o acerto automático:
  - texto esperado  -> o trecho aparece na resposta (sem diferenciar maiúsculas e acentos);
  - ESCALAR         -> a conversa foi passada para a equipe;
  - FORA_ESCOPO     -> o bot recusou com a frase padrão, sem escalar.
Também confere se alguma resposta trouxe dado de outro hotel.

A bancada roda numa CÓPIA do banco (data/recepcao24h.db): as conversas de teste
não aparecem no painel. Sem banco, ela roda o seed numa cópia temporária.
"""
import argparse
import csv
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ENTRADA_PADRAO = RAIZ / "data" / "perguntas_teste.csv"
SAIDA_PADRAO = RAIZ / "resultados_bancada.csv"
BANCO = RAIZ / "data" / "recepcao24h.db"


def ler_perguntas(caminho: Path) -> list[dict]:
    texto = caminho.read_text(encoding="utf-8-sig")
    dialeto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=";,")
    linhas = list(csv.DictReader(texto.splitlines(), dialect=dialeto))
    faltando = {"hotel", "pergunta", "esperado"} - set(linhas[0].keys() if linhas else [])
    if faltando:
        raise SystemExit(f"O CSV precisa das colunas hotel, pergunta e esperado (faltou: {', '.join(sorted(faltando))}).")
    return [{k: (v or "").strip() for k, v in linha.items()} for linha in linhas if (linha.get("pergunta") or "").strip()]


def dados_de_outros_hoteis(db, hotel_id: int) -> list[str]:
    """Trechos que só existem em outros hotéis (nome, senha do wifi e respostas da base)."""
    from app.models import Hotel, ItemBaseConhecimento

    trechos = []
    for h in db.query(Hotel).filter(Hotel.id != hotel_id):
        trechos.append(h.nome)
        if h.politica("wifi_senha"):
            trechos.append(h.politica("wifi_senha"))
        trechos += [i.resposta for i in db.query(ItemBaseConhecimento).filter_by(hotel_id=h.id)]
    return trechos


def avaliar(esperado: str, resposta: str | None, status: str) -> bool:
    from app.bot.textos import MARCA_RECUSA
    from app.formatacao import normalizar

    if esperado.upper() == "ESCALAR":
        return status == "humano"
    if esperado.upper() == "FORA_ESCOPO":
        return status == "bot" and resposta is not None and normalizar(MARCA_RECUSA) in normalizar(resposta)
    return resposta is not None and normalizar(esperado) in normalizar(resposta)


def rodar(perguntas: list[dict], modo: str) -> list[dict]:
    """Roda as perguntas no banco já configurado e devolve uma linha de resultado por pergunta."""
    from app import bot
    from app import db as banco
    from app.models import Hotel
    from app.servicos.conversas import receber_mensagem_hospede

    resultados = []
    with banco.sessao() as db:
        hoteis = {h.slug: h for h in db.query(Hotel)}
        for i, p in enumerate(perguntas, start=1):
            hotel = hoteis.get(p["hotel"])
            if hotel is None:
                print(f"  aviso: hotel \"{p['hotel']}\" não existe; linha {i} ignorada.")
                continue
            conv, resposta = receber_mensagem_hospede(db, hotel, f"(00) 90000-{i:04d}", p["pergunta"], modo=modo)
            vazou = resposta is not None and any(t in resposta for t in dados_de_outros_hoteis(db, hotel.id))
            resultados.append(
                {
                    "hotel": p["hotel"],
                    "pergunta": p["pergunta"],
                    "esperado": p["esperado"],
                    "resposta": resposta or "",
                    "status_bot": conv.status,
                    "acerto": "sim" if avaliar(p["esperado"], resposta, conv.status) and not vazou else "não",
                    "dado_de_outro_hotel": "sim" if vazou else "não",
                    "modo_resposta": bot.ultimo_modo,
                }
            )
    return resultados


def resumo(resultados: list[dict]) -> str:
    por_hotel = defaultdict(lambda: [0, 0])
    for r in resultados:
        por_hotel[r["hotel"]][1] += 1
        por_hotel[r["hotel"]][0] += r["acerto"] == "sim"
    linhas = []
    for hotel, (ok, total) in por_hotel.items():
        linhas.append(f"  {hotel:<22} {ok:>3}/{total:<3} acertos  ({ok / total:.0%})")
    ok = sum(1 for r in resultados if r["acerto"] == "sim")
    linhas.append(f"  {'TOTAL':<22} {ok:>3}/{len(resultados):<3} acertos  ({ok / len(resultados):.0%})")
    vazamentos = sum(1 for r in resultados if r["dado_de_outro_hotel"] == "sim")
    linhas.append(f"  Respostas com dado de outro hotel: {vazamentos}")
    return "\n".join(linhas)


def preparar_banco() -> Path:
    from app import db as banco

    pasta = Path(tempfile.mkdtemp(prefix="bancada_"))
    copia = pasta / "bancada.db"
    if BANCO.exists():
        shutil.copyfile(BANCO, copia)
        banco.configurar(f"sqlite:///{copia.as_posix()}")
    else:
        import seed

        print("Banco não encontrado: rodando o seed numa cópia temporária.")
        banco.configurar(f"sqlite:///{copia.as_posix()}")
        seed.gerar(arquivo_ics=None, silencioso=True)
    return pasta


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Teste de bancada do bot da Recepção 24h")
    parser.add_argument("--modo", choices=["demo", "ia"], default="demo")
    parser.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()

    if args.modo == "ia" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("O modo IA precisa da variável ANTHROPIC_API_KEY.")
    os.environ["DEMO_MODE"] = "1" if args.modo == "demo" else "0"

    perguntas = ler_perguntas(args.entrada)
    pasta = preparar_banco()
    try:
        print(f"Bancada: {len(perguntas)} perguntas, modo {args.modo}")
        resultados = rodar(perguntas, args.modo)
    finally:
        from app import db as banco

        banco.engine.dispose()
        shutil.rmtree(pasta, ignore_errors=True)

    campos = ["hotel", "pergunta", "esperado", "resposta", "status_bot", "acerto", "dado_de_outro_hotel", "modo_resposta"]
    with args.saida.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        escritor.writerows(resultados)

    erros = [r for r in resultados if r["acerto"] != "sim"]
    if erros:
        print("\nErros:")
        for r in erros:
            print(f"  [{r['hotel']}] {r['pergunta']}\n      esperado: {r['esperado']} | status: {r['status_bot']}"
                  f"\n      resposta: {r['resposta'][:160]}")
    if args.modo == "ia" and any(r["modo_resposta"] != "ia" for r in resultados):
        print("\nAtenção: algumas respostas vieram do modo demo porque a API falhou.")
    print("\nAcerto por hotel:")
    print(resumo(resultados))
    print(f"\nResultados gravados em {args.saida}")


if __name__ == "__main__":
    main()

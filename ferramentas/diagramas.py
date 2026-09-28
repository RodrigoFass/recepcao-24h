"""Gera os diagramas da Entrega 3 em SVG (docs/e3/): arquitetura de produção e modelo de dados.

Uso:  python ferramentas/diagramas.py
"""
import math
from pathlib import Path
from xml.sax.saxutils import escape

SAIDA = Path(__file__).resolve().parent.parent / "docs" / "e3"
FONTE = "Segoe UI, system-ui, Arial, sans-serif"
COR = {"texto": "#1d2733", "suave": "#52606d", "linha": "#6b7a89", "fundo": "#ffffff", "primaria": "#0e6b6b",
       "clara": "#e3f1f1", "externo": "#f3f4f6", "externo_borda": "#b8c0c8", "destaque": "#fff4d6",
       "destaque_borda": "#e0b85a"}


class Caixa:
    def __init__(self, x, y, w, titulo, linhas=(), estilo="interno"):
        self.x, self.y, self.w, self.titulo, self.linhas, self.estilo = x, y, w, titulo, list(linhas), estilo
        self.h = 30 + 17 * len(self.linhas) + (8 if self.linhas else 0)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def borda_para(self, px, py):
        """Ponto na borda da caixa na direção de (px, py)."""
        dx, dy = px - self.cx, py - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        escala = min((self.w / 2) / abs(dx) if dx else math.inf, (self.h / 2) / abs(dy) if dy else math.inf)
        return self.cx + dx * escala, self.cy + dy * escala

    def svg(self):
        fundo, borda, cab = {
            "interno": (COR["fundo"], COR["primaria"], COR["primaria"]),
            "externo": (COR["externo"], COR["externo_borda"], "#4b5563"),
            "destaque": (COR["destaque"], COR["destaque_borda"], "#8a5a00"),
            "pessoa": (COR["clara"], COR["primaria"], COR["primaria"]),
        }[self.estilo]
        partes = [
            f'<rect x="{self.x}" y="{self.y}" width="{self.w}" height="{self.h}" rx="8" fill="{fundo}" '
            f'stroke="{borda}" stroke-width="1.5"/>',
            f'<text x="{self.x + 10}" y="{self.y + 20}" font-size="13.5" font-weight="700" fill="{cab}">'
            f"{escape(self.titulo)}</text>",
        ]
        if self.linhas:
            partes.append(f'<line x1="{self.x}" y1="{self.y + 29}" x2="{self.x + self.w}" y2="{self.y + 29}" '
                          f'stroke="{borda}" stroke-width="1"/>')
        for i, linha in enumerate(self.linhas):
            peso = ' font-weight="600"' if linha.startswith("*") else ""
            partes.append(f'<text x="{self.x + 10}" y="{self.y + 46 + 17 * i}" font-size="11.5" '
                          f'fill="{COR["texto"]}"{peso}>{escape(linha.lstrip("*"))}</text>')
        return "\n".join(partes)


def seta(a: Caixa, b: Caixa, rotulo="", dupla=False, rot_a="", rot_b="", deslocar=0.0):
    """Devolve (linha, rótulos). Os rótulos são desenhados depois das caixas, para ficarem por cima."""
    x1, y1 = a.borda_para(b.cx, b.cy + deslocar)
    x2, y2 = b.borda_para(a.cx, a.cy - deslocar)
    marcas = ' marker-end="url(#ponta)"' + (' marker-start="url(#ponta)"' if dupla else "")
    linha = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{COR["linha"]}" '
             f'stroke-width="1.6"{marcas}/>')
    rotulos = []
    comprimento = math.hypot(x2 - x1, y2 - y1) or 1
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    if rotulo:
        largura = 6.3 * len(rotulo) + 12
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if comprimento < largura + 24:  # seta curta: rótulo acima da linha
            nx, ny = -uy, ux
            if ny > 0:
                nx, ny = -nx, -ny
            mx, my = mx + nx * 17, my + ny * 17
        rotulos.append(f'<rect x="{mx - largura / 2:.1f}" y="{my - 10:.1f}" width="{largura:.1f}" height="18" '
                       f'rx="4" fill="#ffffff" opacity="0.95"/>')
        rotulos.append(f'<text x="{mx:.1f}" y="{my + 3.5:.1f}" font-size="11" text-anchor="middle" '
                       f'fill="{COR["suave"]}">{escape(rotulo)}</text>')
    for texto, (px, py), sinal in ((rot_a, (x1, y1), 1), (rot_b, (x2, y2), -1)):
        if texto:
            passo = min(26, comprimento * 0.22)  # em seta curta, "1" e "N" não se encostam
            tx, ty = px + ux * passo * sinal, py + uy * passo * sinal
            ox, oy = -uy * 11, ux * 11  # ao lado da linha, sem encostar nela
            rotulos.append(f'<text x="{tx + ox:.1f}" y="{ty + oy + 4:.1f}" font-size="11.5" font-weight="700" '
                           f'text-anchor="middle" fill="{COR["primaria"]}">{texto}</text>')
    return linha, "\n".join(rotulos)


def montar(setas, caixas, extras=()):
    """Ordem de desenho: linhas, caixas e, por cima, os rótulos."""
    return "\n".join([linha for linha, _ in setas] + [c.svg() for c in caixas]
                     + [r for _, r in setas if r] + list(extras))


def documento(largura, altura, conteudo, titulo):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" font-family="{FONTE}">
<title>{escape(titulo)}</title>
<defs><marker id="ponta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{COR["linha"]}"/></marker></defs>
<rect width="{largura}" height="{altura}" fill="#ffffff"/>
{conteudo}
</svg>
"""


def arquitetura():
    hospede = Caixa(20, 62, 150, "Hóspede", ["WhatsApp no celular"], "pessoa")
    meta = Caixa(230, 52, 180, "WhatsApp Cloud API", ["Meta · número do hotel", "cobra direto do hotel"], "externo")
    n8n = Caixa(480, 30, 250, "n8n (VPS, auto-hospedado)", [
        "*1. Atendimento 24h", "   webhook → IA → resposta", "*2. Jornada de chegada", "   agendador das 6 mensagens",
        "*3. Calendário único", "   iCal a cada 2h + CSV", "*4. Pós-estadia", "   nota 1–5 + convite",
        "*5. Alertas para a equipe"])
    ia = Caixa(830, 30, 210, "API da Anthropic", ["Claude Haiku 4.5 + ferramentas:", "consultar_disponibilidade",
                                                   "escalar_para_humano", "registrar_hora_chegada"], "externo")
    banco = Caixa(830, 185, 210, "Supabase (Postgres)", ["região São Paulo (sa-east-1)", "hotel_id em toda tabela",
                                                         "Row Level Security"], "destaque")
    otas = Caixa(830, 360, 210, "Airbnb · Booking.com", ["iCal de entrada e de saída", "CSV de reservas (valor)"],
                 "externo")
    equipe = Caixa(230, 250, 180, "Equipe do hotel", ["conversas escaladas", "alertas (WhatsApp/e-mail)"], "pessoa")
    painel = Caixa(480, 395, 250, "Painel web", ["ocupação · ADR · RevPAR", "receita líquida por canal"])
    dono = Caixa(230, 405, 180, "Dono / gestor", ["decide preço e promoção"], "pessoa")
    caixas = [hospede, meta, n8n, ia, banco, otas, equipe, painel, dono]
    setas = [
        seta(hospede, meta, dupla=True),
        seta(meta, n8n, "webhook", dupla=True),
        seta(n8n, ia, "prompt do hotel", dupla=True, deslocar=-25),
        seta(n8n, banco, "dados", dupla=True),
        seta(otas, n8n, "iCal", dupla=True),
        seta(n8n, equipe, "escala / avisa"),
        seta(banco, painel, "consulta"),
        seta(painel, dono),
    ]
    rodape = (f'<text x="20" y="505" font-size="11.5" fill="{COR["suave"]}">Protótipo: FastAPI + SQLite simulam o '
              f"WhatsApp, o n8n e as OTAs com o mesmo modelo de dados. Produção: componentes acima, um número de "
              f"WhatsApp por hotel.</text>")
    return documento(1060, 520, montar(setas, caixas, [rodape]), "Arquitetura de produção da Recepção 24h")


def modelo_dados():
    w = 215
    c1, c2, c3, c4 = 20, 295, 570, 845
    hotel = Caixa(c2, 20, w, "Hotel", ["*id, slug, nome, cidade", "checkin_hora, checkout_hora",
                                       "early/late: permite + preço", "modo_chegada, recepção", "link_fnrh",
                                       "politicas (json)", "fuso"])
    tipo = Caixa(c1, 20, w, "TipoAcomodacao", ["*hotel_id", "nome, capacidade", "tarifa_base"])
    unidade = Caixa(c1, 175, w, "Unidade", ["*hotel_id, tipo_id", "identificacao", "ativa"])
    cal = Caixa(c1, 330, w, "CalendarioExterno", ["*hotel_id, unidade_id, canal_id", "ical_url",
                                                  "ultima_sincronizacao"])
    alerta = Caixa(c1, 505, w, "Alerta", ["*hotel_id", "tipo, referencia, texto", "resolvido, criado_em"], "destaque")
    item = Caixa(c3, 20, w, "ItemBaseConhecimento", ["*hotel_id", "categoria, pergunta", "palavras_chave, resposta",
                                                    "atualizado_em"])
    canal = Caixa(c3, 175, w, "Canal", ["*hotel_id", "tipo, comissao_pct", "anuncio_por"])
    reserva = Caixa(c2, 300, w, "Reserva", ["*hotel_id, unidade_id", "*hospede_id, canal_id", "check_in, check_out",
                                            "num_hospedes, valor_total", "status, hora_prevista_chegada",
                                            "origem, codigo_externo"])
    msg_ag = Caixa(c2, 505, w, "MensagemAgendada", ["*reserva_id", "etapa, enviar_em", "status, meio, texto"])
    hospede = Caixa(c3, 345, w, "Hospede", ["*hotel_id", "nome, telefone, email", "consentimento_whatsapp_em",
                                            "(sem documento: FNRH)"])
    aval = Caixa(c3, 505, w, "Avaliacao", ["*reserva_id", "nota, comentario", "alerta_enviado, convite_enviado"])
    usuario = Caixa(c4, 20, w, "UsuarioEquipe", ["*hotel_id", "nome, papel", "contato_alerta"])
    conversa = Caixa(c4, 175, w, "Conversa", ["*hotel_id, hospede_id", "telefone, status", "motivo_escalonamento"])
    mensagem = Caixa(c4, 345, w, "Mensagem", ["*conversa_id", "autor, texto, criada_em"])
    caixas = [hotel, tipo, unidade, cal, alerta, item, canal, reserva, msg_ag, hospede, aval, usuario, conversa,
              mensagem]
    rel = [
        seta(hotel, tipo, rot_a="1", rot_b="N"),
        seta(hotel, item, rot_a="1", rot_b="N"),
        seta(hotel, canal, rot_a="1", rot_b="N"),
        seta(tipo, unidade, rot_a="1", rot_b="N"),
        seta(unidade, cal, rot_a="1", rot_b="N"),
        seta(unidade, reserva, rot_a="1", rot_b="N"),
        seta(canal, reserva, rot_a="1", rot_b="N"),
        seta(hospede, reserva, rot_a="1", rot_b="N"),
        seta(reserva, msg_ag, rot_a="1", rot_b="6"),
        seta(reserva, aval, rot_a="1", rot_b="0..1"),
        seta(hospede, conversa, rot_a="1", rot_b="N"),
        seta(conversa, mensagem, rot_a="1", rot_b="N"),
    ]
    nota = (f'<text x="{c4}" y="470" font-size="11.5" fill="{COR["suave"]}">'
            f'<tspan x="{c4}" dy="0">Toda tabela ligada a um hotel tem</tspan>'
            f'<tspan x="{c4}" dy="16">hotel_id, e toda consulta filtra por ele</tspan>'
            f'<tspan x="{c4}" dy="16">(na produção: Row Level Security).</tspan>'
            f'<tspan x="{c4}" dy="22">Alerta.referencia aponta para uma</tspan>'
            f'<tspan x="{c4}" dy="16">reserva ou uma conversa.</tspan></text>')
    return documento(1080, 615, montar(rel, caixas, [nota]), "Modelo de dados da Recepção 24h")


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "arquitetura.svg").write_text(arquitetura(), encoding="utf-8")
    (SAIDA / "modelo_dados.svg").write_text(modelo_dados(), encoding="utf-8")
    print("ok:", SAIDA / "arquitetura.svg", SAIDA / "modelo_dados.svg")

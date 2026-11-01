"""Grava o vídeo do funcionamento completo em docs/video/demo_recepcao24h.mp4.

Uso:  python ferramentas/gravar_demo.py

Precisa do Google Chrome instalado, de:  pip install -r requirements-dev.txt
e de uma chave de IA (GEMINI_API_KEY ou ANTHROPIC_API_KEY, no .env): as
respostas do vídeo vêm da IA de verdade.
O script faz tudo sozinho: cria um banco temporário com o seed do dia, sobe o
servidor numa porta livre, executa o roteiro, converte para MP4 e desliga o
servidor. Não mexe no data/recepcao24h.db.

O vídeo é montado num "palco" (página 1920×1080 servida pelo próprio script):
o app roda dentro de uma janela de navegador sobre o fundo da marca, com cursor,
efeito de clique, zoom, legendas, cartões de capítulo e a barra das etapas.
"""
import base64
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import app  # noqa: E402,F401  (carrega o .env)
from app import bot  # noqa: E402

SAIDA = RAIZ / "docs" / "video" / "demo_recepcao24h.mp4"
TAMANHO = {"width": 1920, "height": 1080}
JANELA = (240, 92)  # canto da janela do app no palco (o iframe começa 44 px abaixo, depois da barra)
ETAPAS = ["Atendimento", "Vagas", "Equipe", "Chegada", "Calendário", "Painel", "Novo hotel"]

PALCO = """<!doctype html><html><head><meta charset="utf-8"><title>Recepção 24h</title><style>
*{box-sizing:border-box}
body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:"Segoe UI",system-ui,sans-serif;color:#fff;
  background:radial-gradient(circle at 18% 8%,#16867f 0%,#0e5e5c 45%,#083a39 100%)}
#marca{position:absolute;left:64px;top:24px;font-size:32px;font-weight:600;letter-spacing:-.01em}
#marca b{color:#9fe0d6}
#etapas{position:absolute;right:64px;top:28px;display:flex;gap:10px}
.etapa{font-size:18px;padding:7px 15px;border-radius:999px;background:rgba(255,255,255,.09);color:#cfe7e3;
  transition:all .5s}
.etapa.feita{background:rgba(159,224,214,.22);color:#e6f5f2}
.etapa.ativa{background:#9fe0d6;color:#0b3d3c;font-weight:700;transform:scale(1.06)}
#janela{position:absolute;left:240px;top:92px;width:1440px;height:854px;border-radius:14px;overflow:hidden;
  background:#fff;box-shadow:0 30px 90px rgba(0,0,0,.38),0 0 0 1px rgba(255,255,255,.08);
  transition:transform 1s cubic-bezier(.2,.7,.2,1);transform-origin:50% 50%}
#barra{height:44px;background:#eef1f3;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid #dde2e6}
.bola{width:13px;height:13px;border-radius:50%}
#url{margin-left:18px;flex:1;height:28px;border-radius:8px;background:#fff;color:#55606b;font-size:15px;
  display:flex;align-items:center;padding:0 14px;transition:opacity .3s}
iframe{width:1440px;height:810px;border:0;display:block;background:#f3f4f6}
#legenda{position:absolute;left:50%;bottom:30px;transform:translate(-50%,18px);opacity:0;max-width:1560px;
  background:rgba(6,30,29,.93);padding:14px 32px;border-radius:16px;font-size:28px;font-weight:600;text-align:center;
  line-height:1.3;box-shadow:0 12px 34px rgba(0,0,0,.32);transition:opacity .45s,transform .45s;z-index:40}
#legenda.mostrar{opacity:1;transform:translate(-50%,0)}
#cursor{position:absolute;left:1500px;top:1100px;width:34px;height:34px;z-index:50;pointer-events:none;
  filter:drop-shadow(0 2px 3px rgba(0,0,0,.35));
  transition:left .75s cubic-bezier(.3,.7,.2,1),top .75s cubic-bezier(.3,.7,.2,1),opacity .3s}
.onda{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;border:4px solid #9fe0d6;
  z-index:49;pointer-events:none;animation:onda .65s ease-out forwards}
@keyframes onda{from{transform:scale(.4);opacity:1}to{transform:scale(3.2);opacity:0}}
#capa{position:absolute;inset:0;z-index:60;display:flex;flex-direction:column;justify-content:center;padding:0 170px;
  background:radial-gradient(circle at 22% 18%,#16867f 0%,#0e5e5c 50%,#083a39 100%);opacity:0;transition:opacity .7s;
  pointer-events:none}
#capa.mostrar{opacity:1}
#capa>*{transform:translateY(30px);opacity:0;transition:transform .9s cubic-bezier(.2,.7,.2,1),opacity .9s}
#capa.mostrar>*{transform:none;opacity:1}
#capa.mostrar>:nth-child(2){transition-delay:.12s}
#capa.mostrar>:nth-child(3){transition-delay:.24s}
#capa.mostrar>:nth-child(4){transition-delay:.36s}
.rot{font-size:26px;letter-spacing:.14em;text-transform:uppercase;color:#9fe0d6;margin:0 0 20px}
.num{font-size:170px;font-weight:800;color:rgba(159,224,214,.4);margin:0;line-height:1}
.tit{font-size:100px;font-weight:700;margin:0 0 20px;line-height:1.05}
.tit b{color:#9fe0d6}
.sub{font-size:38px;color:#dcebe8;margin:0;max-width:1400px;line-height:1.35}
</style></head><body>
<div id="marca">Recepção <b>24h</b></div>
<div id="etapas"></div>
<div id="janela">
  <div id="barra"><span class="bola" style="background:#ff5f57"></span><span class="bola" style="background:#febc2e"></span>
    <span class="bola" style="background:#28c840"></span><div id="url">Recepção 24h</div></div>
  <iframe id="app" name="app" src="about:blank"></iframe>
</div>
<div id="legenda"></div>
<svg id="cursor" viewBox="0 0 24 24"><path d="M4 2 L4 20 L9 15.5 L12.5 22 L15.6 20.5 L12.2 14 L19 14 Z"
  fill="#14211f" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>
<div id="capa" class="mostrar"></div>
<script>
const NOMES = __ETAPAS__;
const etapas = document.getElementById('etapas');
NOMES.forEach((n, i) => { const e = document.createElement('div'); e.className = 'etapa'; e.textContent = (i + 1) + ' ' + n; etapas.appendChild(e); });
function etapa(i) { [...etapas.children].forEach((e, k) => { e.className = 'etapa' + (k + 1 < i ? ' feita' : k + 1 === i ? ' ativa' : ''); }); }
let legendaTimer;
function legenda(t) {
  const el = document.getElementById('legenda');
  el.classList.remove('mostrar');
  clearTimeout(legendaTimer);
  legendaTimer = setTimeout(() => { el.innerHTML = t; if (t) el.classList.add('mostrar'); }, t ? 280 : 0);
}
const cur = document.getElementById('cursor');
function cursor(x, y) { cur.style.left = (x - 6) + 'px'; cur.style.top = (y - 3) + 'px'; }
function mostrarCursor(v) { cur.style.opacity = v ? 1 : 0; }
function clique(x, y) { const o = document.createElement('div'); o.className = 'onda'; o.style.left = x + 'px'; o.style.top = y + 'px'; document.body.appendChild(o); setTimeout(() => o.remove(), 700); }
const jan = document.getElementById('janela');
function zoom(x, y, s) { jan.style.transformOrigin = (x - __JX__) + 'px ' + (y - __JY__) + 'px'; jan.style.transform = s === 1 ? 'none' : 'scale(' + s + ')'; }
function capa(html) { const k = document.getElementById('capa'); if (!html) { k.classList.remove('mostrar'); return; } k.classList.remove('mostrar'); k.innerHTML = html; void k.offsetWidth; k.classList.add('mostrar'); }
function url(t) { document.getElementById('url').textContent = t; }
</script></body></html>"""

# hotel novo do capítulo 7 (fictício)
EXEMPLO_HOTEL = {
    "nome": "Pousada Recanto do Sol", "cidade": "Anchieta (ES)", "telefone": "(27) 3000-0303",
    "whatsapp": "(27) 99000-0303", "endereco": "Rua dos Coqueiros, 45 – Anchieta/ES",
    "checkin_hora": "13:00", "checkout_hora": "11:00",
    "early_checkin_permite": True, "early_checkin_a_partir": "10:00", "early_checkin_preco": "40",
    "late_checkout_permite": True, "late_checkout_ate": "13:00", "late_checkout_preco": "40",
    "modo_chegada": "recepcao_24h", "recepcao_inicio": "", "recepcao_fim": "",
    "instrucoes_chegada": "A recepção fica aberta 24 horas: é só se apresentar com um documento com foto.",
    "contato_emergencia": "(27) 99000-0399", "link_fnrh": "https://fnrh-digital.exemplo/pre-checkin/recanto-do-sol",
    "wifi_rede": "RecantoDoSol", "wifi_senha": "sol2026", "aceita_pet": True,
    "tipo_nome_0": "Quarto Standard", "tipo_capacidade_0": "2", "tipo_tarifa_0": "230", "tipo_unidades_0": "1-6",
    "tipo_nome_1": "Quarto Triplo", "tipo_capacidade_1": "3", "tipo_tarifa_1": "300", "tipo_unidades_1": "7-9",
    "canal_airbnb": False, "canal_booking": True, "comissao_booking": "15", "canal_whatsapp": True,
    "comissao_whatsapp": "0", "canal_telefone": True, "comissao_telefone": "0",
    "responsavel_nome": "Marta Silva", "responsavel_contato": "(27) 99000-0399",
    "login": "recantodosol", "senha": "sol12345",
    "kb_pet": "Sim! Aceitamos pets de até 15 kg, sem taxa. Pedimos que não subam nas camas.",
    "kb_cafe": "O café da manhã está incluso e é servido das 7h às 10h no salão.",
    "kb_estacionamento": "Temos estacionamento gratuito e coberto, com 8 vagas.",
    "kb_como_chegar": "Ficamos na Rua dos Coqueiros, 45, em Anchieta (ES), a duas quadras da praia central.",
    "kb_chegada_fora_horario": "A recepção funciona 24 horas, então você pode chegar a qualquer hora.",
    "kb_criancas": "Crianças até 6 anos não pagam. Temos berço sem custo.",
    "kb_cancelamento": "Cancelamento grátis até 5 dias antes da chegada. Depois disso, cobramos a primeira diária.",
    "kb_pagamento": "Aceitamos Pix, cartão de crédito (até 3x) e dinheiro.",
    "kb_lazer": "Temos piscina aberta das 8h às 21h e um redário no jardim.",
    "kb_silencio": "Silêncio a partir das 23h.",
    "kb_roupa_cama": "Roupa de cama e toalhas de banho estão incluídas; toalha de piscina na recepção.",
    "kb_turismo": "Perto daqui: praia central (2 quadras), Santuário de Anchieta (5 min de carro) e passeio de escuna.",
}

PREENCHER = """(dados) => {
  const form = document.getElementById('form-hotel');
  for (const [nome, valor] of Object.entries(dados)) {
    const campo = form.elements[nome];
    if (!campo) continue;
    if (campo.type === 'checkbox') campo.checked = !!valor; else campo.value = valor;
    campo.dispatchEvent(new Event('change', {bubbles: true}));
  }
}"""


class Roteiro:
    def __init__(self, pagina, base: str, ics: Path):
        self.pg = pagina
        self.base = base
        self.ics = ics
        self.app = pagina.frame(name="app")

    # ---- palco
    def pausa(self, segundos):
        self.pg.wait_for_timeout(int(segundos * 1000))  # processa os quadros enquanto espera

    def js(self, codigo, arg=None):
        return self.pg.evaluate(codigo, arg)

    def legenda(self, texto, segundos=0.6):
        self.js("t => legenda(t)", texto)
        self.pausa(segundos)

    def capa(self, html, segundos):
        self.js("h => capa(h)", html)
        self.pausa(segundos)

    def capitulo(self, i, titulo, sub):
        self.legenda("", 0.2)
        self.js("i => etapa(i)", i)
        self.capa(f'<p class="num">{i}</p><p class="tit">{titulo}</p><p class="sub">{sub}</p>', 2.8)
        self.js("() => capa('')")
        self.pausa(0.8)

    # ---- o app dentro da janela
    def abrir(self, caminho):
        self.app.goto(self.base + caminho)
        self.app.wait_for_load_state("networkidle")
        self.js("t => url(t)", self.app.title())

    def mover(self, seletor):
        loc = self.app.locator(seletor).first
        loc.scroll_into_view_if_needed()
        self.pausa(0.25)
        caixa = loc.bounding_box()
        x, y = caixa["x"] + min(caixa["width"] / 2, 60), caixa["y"] + caixa["height"] / 2
        self.js("([x, y]) => cursor(x, y)", [x, y])
        self.pausa(0.85)
        return loc, x, y

    def clicar(self, seletor, navega=False):
        loc, x, y = self.mover(seletor)
        self.js("([x, y]) => clique(x, y)", [x, y])
        if navega:
            with self.app.expect_navigation():
                loc.click()
            self.app.wait_for_load_state("networkidle")
            self.js("t => url(t)", self.app.title())
        else:
            loc.click()
        self.pausa(0.35)

    def digitar(self, seletor, texto, atraso=40):
        self.clicar(seletor)
        self.pg.keyboard.type(texto, delay=atraso)
        self.pausa(0.3)

    def preencher(self, seletor, valor):
        """Campo de data ou de seleção: o cursor vai até ele e o valor aparece."""
        loc, x, y = self.mover(seletor)
        self.js("([x, y]) => clique(x, y)", [x, y])
        loc.fill(valor)
        self.pausa(0.5)

    def rolar(self, seletor, segundos=1.4):
        self.app.evaluate(f"document.querySelector({seletor!r}).scrollIntoView({{behavior: 'smooth', block: 'start'}})")
        self.pausa(segundos)

    def zoom(self, seletor, escala=1.35, segundos=3.8, ultimo=True):
        loc = self.app.locator(seletor)
        loc = loc.last if ultimo else loc.first
        caixa = loc.bounding_box()
        x, y = caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2
        self.js("() => mostrarCursor(false)")
        self.js("([x, y, s]) => zoom(x, y, s)", [x, y, escala])
        self.pausa(segundos)
        self.js("() => zoom(0, 0, 1)")
        self.pausa(1.1)
        self.js("() => mostrarCursor(true)")

    def enviar_chat(self, texto):
        """Digita como o hóspede e espera a resposta aparecer."""
        antes = self.app.locator(".bolha").count()
        self.digitar("#texto", texto, atraso=36)
        self.pg.keyboard.press("Enter")
        self.app.wait_for_function(f"document.querySelectorAll('.bolha').length >= {antes + 2}", timeout=60000)
        self.pausa(0.8)

    def entrar(self, login, senha):
        self.digitar("input[name=login]", login, atraso=60)
        self.digitar("input[name=senha]", senha, atraso=60)
        self.clicar("form[action='/entrar'] button", navega=True)

    # ---- roteiro
    def executar(self):
        self.capa("""<p class="rot">Gestão de Micro e Pequenas Empresas · UVV</p>
            <p class="tit">Recepção <b>24h</b></p>
            <p class="sub">Atendimento 24 horas com IA para pousadas e hotéis pequenos — o sistema funcionando,
            do hóspede ao dono.</p>""", 5)

        # 1. atendimento com IA
        self.abrir("/chat?hotel=mare-alta")
        self.capitulo(1, "Atendimento 24h com IA", "O hóspede escreve como no WhatsApp e recebe a resposta na hora.")
        self.legenda("Um hóspede escreve para a Pousada Maré Alta")
        self.enviar_chat("boa noite! vou com minha esposa e meu filho de 3 anos, ele paga? "
                         "e posso levar meu cachorro de 6kg?")
        self.legenda("A IA entende a pergunta e responde com as regras deste hotel")
        self.zoom(".bolha.autor-bot", 1.4, 4.5)
        self.abrir("/chat?hotel=serra-verde")
        self.legenda("Outro hotel cliente, a mesma pergunta")
        self.enviar_chat("vocês aceitam pet?")
        self.legenda("Resposta diferente: cada hotel tem as suas regras e os seus dados")
        self.zoom(".bolha.autor-bot", 1.4, 3.8)

        # 2. vagas e limites
        sexta = date.today() + timedelta(days=(4 - date.today().weekday()) % 7 + 7)
        self.abrir("/chat?hotel=mare-alta")
        self.capitulo(2, "Vagas e limites", "Consulta o calendário real e não sai do assunto do hotel.")
        self.legenda("O hóspede pergunta por vaga")
        self.enviar_chat(f"tem vaga de {sexta:%d/%m} a {sexta + timedelta(days=2):%d/%m} pra 3 pessoas?")
        self.legenda("Confere a disponibilidade e calcula o total — sem dar desconto e sem fechar a reserva sozinha")
        self.zoom(".bolha.autor-bot", 1.4, 4.5)
        self.legenda("E se o assunto não for o hotel?")
        self.enviar_chat("quem ganhou o jogo do flamengo ontem?")
        self.legenda("Recusa educada, sem incomodar a equipe")
        self.zoom(".bolha.autor-bot", 1.4, 3.2)

        # 3. a equipe entra quando precisa
        self.capitulo(3, "A equipe entra quando precisa", "Desconto, reclamação ou pedido de atendente vão para uma pessoa.")
        self.legenda("O hóspede pede desconto")
        self.enviar_chat("consegue um desconto?")
        self.legenda("O assistente avisa o hóspede e passa a conversa para a equipe")
        self.zoom(".celular-topo", 1.3, 3.0, ultimo=False)
        self.abrir("/entrar")
        self.legenda("A equipe da Maré Alta entra com o próprio acesso")
        self.entrar("marealta", "mare1234")
        self.legenda("Tela da equipe: só o que precisa de uma pessoa — e só deste hotel")
        self.pausa(2.5)
        self.digitar(".conversa-escalada input[name=texto]",
                     "Oi! Aqui é a Carla, da recepção. No Pix conseguimos 5% para 2 noites ou mais.", atraso=22)
        self.clicar(".conversa-escalada button:has-text('Enviar')", navega=True)
        self.legenda("A equipe responde e devolve a conversa ao assistente")
        self.pausa(1.5)
        self.clicar(".conversa-escalada button:has-text('Devolver ao bot')", navega=True)
        self.pausa(1.5)

        # 4. chegada sem improviso
        amanha = date.today() + timedelta(days=1)
        tel = "(27) 98888-5005"
        self.capitulo(4, "Chegada sem improviso", "Cada reserva agenda as mensagens da chegada, sozinha.")
        self.legenda("A equipe lança uma reserva feita pelo WhatsApp, para amanhã")
        self.digitar("#nova-reserva input[name=nome]", "Beatriz Almeida")
        self.digitar("#nova-reserva input[name=telefone]", tel)
        self.clicar("#nova-reserva input[name=consentimento]")
        self.preencher("#nova-reserva input[name=check_in]", amanha.isoformat())
        self.preencher("#nova-reserva input[name=check_out]", (amanha + timedelta(days=3)).isoformat())
        self.clicar("#nova-reserva button:has-text('Criar reserva')", navega=True)
        self.legenda("Seis mensagens agendadas — as que já venceram saem na hora")
        self.rolar(".linha-tempo")
        self.zoom(".linha-tempo", 1.25, 3.5, ultimo=False)
        self.abrir(f"/chat?hotel=mare-alta&telefone={quote(tel)}")
        self.legenda("No celular da hóspede: confirmação, boas-vindas com a FNRH Digital e a pergunta do horário")
        self.pausa(3.5)
        self.enviar_chat("Chego às 23h")
        self.legenda("O horário fica registrado na reserva — e ela já sabe como entrar depois das 22h")
        self.zoom(".bolha.autor-bot", 1.4, 4.2)

        # 5. calendário único
        self.abrir("/equipe")
        self.capitulo(5, "Calendário único", "Airbnb, Booking e reservas diretas no mesmo calendário.")
        self.rolar("#ical")
        self.legenda("O calendário do Airbnb de cada quarto entra no sistema")
        self.mover("#ical select[name=unidade_id]")
        self.app.locator("#ical select[name=unidade_id]").select_option(label="101 · Suíte Casal")
        self.pausa(0.6)
        self.mover("#ical input[name=arquivo]")
        self.app.locator("#ical input[name=arquivo]").set_input_files(str(self.ics))
        self.pausa(0.8)
        self.clicar("#ical button:has-text('Importar iCal')", navega=True)
        self.legenda("Uma reserva do Airbnb caiu em cima de outra: a equipe recebe um alerta de conflito")
        self.rolar("#alertas", 1.0)
        self.zoom("#alertas", 1.25, 4.2, ultimo=False)

        # 6. painel
        self.capitulo(6, "Painel do dono", "Os números para decidir preço e promoção.")
        self.clicar("nav.menu a:has-text('Painel')", navega=True)
        self.legenda("Ocupação, diária média, RevPAR, reservas diretas e nota média")
        self.pausa(1.5)
        self.zoom(".cartoes-kpi", 1.2, 3.8, ultimo=False)
        self.rolar("#g-semana", 1.6)
        self.legenda("Quais dias ficam vazios e quanto sobra de cada canal depois da comissão")
        self.pausa(4.5)

        # 7. um sistema, vários hotéis
        self.capitulo(7, "Um sistema, vários hotéis", "Um cadastro e o hotel novo já é atendido.")
        self.clicar("form[action='/sair'] button", navega=True)
        self.clicar("a.botao:has-text('Entrar')", navega=True)
        self.legenda("A administração da Recepção 24h cadastra um hotel cliente novo")
        self.entrar("admin", "admin1234")
        self.pausa(1.5)
        self.clicar("a:has-text('Cadastrar hotel')", navega=True)
        self.app.evaluate(PREENCHER, EXEMPLO_HOTEL)
        self.legenda("Horários validados pela Portaria MTur nº 28/2025, quartos, canais e perguntas frequentes")
        self.pausa(1.5)
        self.app.evaluate("window.scrollTo({top: document.body.scrollHeight * 0.45, behavior: 'smooth'})")
        self.pausa(2.2)
        self.app.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        self.pausa(2.2)
        self.clicar("#form-hotel button:has-text('Salvar hotel')", navega=True)
        self.legenda("Hotel cadastrado, com o acesso da equipe dele")
        self.pausa(2.5)
        self.clicar("article:has-text('Recanto do Sol') a:has-text('Atendimento do hóspede')", navega=True)
        self.enviar_chat("oi! qual o horário do check-in e do check-out?")
        self.legenda("O assistente já responde com os dados que acabaram de ser cadastrados")
        self.zoom(".bolha.autor-bot", 1.4, 4.2)

        self.legenda("", 0.2)
        self.capa("""<p class="tit">Recepção <b>24h</b></p>
            <p class="sub">O hóspede é atendido na hora. A equipe entra quando precisa.
            O dono vê como o negócio está indo.</p>""", 5)


def gravar(base: str, pasta: Path, ics: Path) -> Path:
    """Executa o roteiro capturando os quadros da tela (screencast do Chrome). Devolve a lista para o ffmpeg."""
    quadros = []  # (instante, arquivo)
    palco = PALCO.replace("__ETAPAS__", repr(ETAPAS)).replace("__JX__", str(JANELA[0])).replace("__JY__", str(JANELA[1]))
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        contexto = navegador.new_context(viewport=TAMANHO, locale="pt-BR")
        pagina = contexto.new_page()
        # o palco é "servido" na mesma origem do app, para o login do iframe funcionar
        pagina.route(base + "/__palco", lambda rota: rota.fulfill(body=palco, content_type="text/html; charset=utf-8"))
        pagina.goto(base + "/__palco")
        cdp = contexto.new_cdp_session(pagina)

        def quadro(evento):
            arquivo = pasta / f"q{len(quadros):05d}.jpg"
            arquivo.write_bytes(base64.b64decode(evento["data"]))
            quadros.append((evento["metadata"]["timestamp"], arquivo))
            cdp.send("Page.screencastFrameAck", {"sessionId": evento["sessionId"]})

        cdp.on("Page.screencastFrame", quadro)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": TAMANHO["width"],
                                          "maxHeight": TAMANHO["height"], "everyNthFrame": 1})
        Roteiro(pagina, base, ics).executar()
        cdp.send("Page.stopScreencast")
        contexto.close()
        navegador.close()

    # cada quadro fica na tela até o próximo
    linhas = []
    for (t, arquivo), (t_seguinte, _) in zip(quadros, quadros[1:] + [(quadros[-1][0] + 1.5, None)]):
        linhas += [f"file '{arquivo.as_posix()}'", f"duration {max(t_seguinte - t, 0.001):.4f}"]
    linhas.append(f"file '{quadros[-1][1].as_posix()}'")
    lista = pasta / "quadros.txt"
    lista.write_text("\n".join(linhas), encoding="utf-8")
    return lista


def converter(lista: Path, saida: Path) -> str:
    saida.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
         "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
         "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-an", str(saida)],
        check=True,
    )
    info = subprocess.run([ffmpeg, "-i", str(saida)], capture_output=True, text=True).stderr
    return next((linha.split(",")[0].strip() for linha in info.splitlines() if "Duration" in linha), "?")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.environ["DEMO_MODE"] = "0"
    if bot.modo() != "ia":
        raise SystemExit("Sem chave de IA: coloque GEMINI_API_KEY no arquivo .env (veja o README).")
    pasta = Path(tempfile.mkdtemp(prefix="demo_video_"))
    ics = pasta / "exemplo.ics"
    ambiente = {**os.environ, "DATABASE_URL": f"sqlite:///{(pasta / 'demo.db').as_posix()}"}
    print("1/4 banco temporário com o seed de hoje")
    subprocess.run([sys.executable, "-c", f"import seed; seed.gerar(arquivo_ics=__import__('pathlib').Path({str(ics)!r}),"
                    " silencioso=True)"], cwd=RAIZ, env=ambiente, check=True)
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    print(f"2/4 servidor em {base} (IA: {bot.provedor()})")
    log_servidor = pasta / "servidor.log"
    with open(log_servidor, "w", encoding="utf-8") as saida_log:
        servidor = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(porta),
                                     "--log-level", "warning"], cwd=RAIZ, env=ambiente, stderr=saida_log)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("O servidor não subiu.")
        print("3/4 gravando o roteiro (cerca de 4 min)")
        (pasta / "quadros").mkdir()
        lista = gravar(base, pasta / "quadros", ics)
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)
    falhas = [linha for linha in log_servidor.read_text(encoding="utf-8").splitlines() if "Falha no modo IA" in linha]
    if falhas:
        print(f"Atenção: {len(falhas)} resposta(s) vieram das regras porque a IA falhou:")
        print("\n".join(falhas))
    print("4/4 convertendo para MP4")
    duracao = converter(lista, SAIDA)
    print(f"Vídeo: {SAIDA} ({SAIDA.stat().st_size / 1e6:.1f} MB, {duracao})")
    shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    main()

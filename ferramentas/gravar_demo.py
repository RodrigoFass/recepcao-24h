"""Grava o vídeo do funcionamento completo em docs/video/demo_recepcao24h.mp4.

Uso:  python ferramentas/gravar_demo.py

Precisa do Google Chrome instalado, de:  pip install -r requirements-dev.txt
e de uma chave de IA (GEMINI_API_KEY ou ANTHROPIC_API_KEY, no .env): as
respostas do vídeo vêm da IA de verdade.
O script faz tudo sozinho: cria um banco temporário com o seed do dia, sobe o
servidor numa porta livre, executa o roteiro com legendas na tela, converte
para MP4 e desliga o servidor. Não mexe no data/recepcao24h.db.
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
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import app  # noqa: E402,F401  (carrega o .env)
from app import bot  # noqa: E402

SAIDA = RAIZ / "docs" / "video" / "demo_recepcao24h.mp4"
TAMANHO = {"width": 1280, "height": 720}

LEGENDA = """([passo, texto]) => {
  let el = document.getElementById('legenda-demo');
  if (!el) {
    el = document.createElement('div');
    el.id = 'legenda-demo';
    Object.assign(el.style, {position: 'fixed', left: '50%', bottom: '22px', transform: 'translateX(-50%)',
      background: 'rgba(17,24,39,.9)', color: '#fff', padding: '12px 22px', borderRadius: '12px',
      font: '600 19px "Segoe UI", system-ui, sans-serif', zIndex: 99999, maxWidth: '86%', textAlign: 'center',
      boxShadow: '0 6px 22px rgba(0,0,0,.28)', lineHeight: '1.35'});
    document.body.appendChild(el);
  }
  el.innerHTML = passo ? `<span style="color:#9fe0d6">${passo}</span> · ${texto}` : texto;
}"""

CARTAO = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;
padding:0 90px;box-sizing:border-box;background:#0e6b6b;color:#fff;font-family:"Segoe UI",system-ui,sans-serif}
.s{font-size:18px;letter-spacing:.08em;text-transform:uppercase;opacity:.8;margin:0 0 18px}
h1{font-size:72px;margin:0 0 14px}h1 b{color:#9fe0d6}p{font-size:26px;margin:0 0 10px;max-width:1000px;opacity:.95}
.m{font-size:18px;opacity:.8;margin-top:28px}</style></head><body>{corpo}</body></html>"""


class Roteiro:
    def __init__(self, pagina, base: str, ics: Path):
        self.pg = pagina
        self.base = base
        self.ics = ics

    # ---- auxiliares
    def pausa(self, segundos):
        self.pg.wait_for_timeout(int(segundos * 1000))  # processa os quadros enquanto espera

    def legenda(self, passo, texto):
        self.pg.evaluate(LEGENDA, [passo, texto])

    def cartao(self, corpo, segundos):
        self.pg.set_content(CARTAO.replace("{corpo}", corpo))
        self.pausa(segundos)

    def navegar(self, acao):
        """Executa uma ação que troca de página e espera a nova página carregar."""
        with self.pg.expect_navigation():
            acao()
        self.pg.wait_for_load_state("networkidle")

    def enviar(self, texto, espera=2.2):
        """Digita como o hóspede e espera a resposta do bot aparecer."""
        antes = self.pg.locator(".bolha").count()
        self.pg.click("#texto")
        self.pg.keyboard.type(texto, delay=45)
        self.pg.keyboard.press("Enter")
        # a IA leva alguns segundos para responder
        self.pg.wait_for_function(f"document.querySelectorAll('.bolha').length >= {antes + 2}", timeout=60000)
        self.pausa(espera)

    def rolar_ate(self, seletor):
        self.pg.evaluate(f"window.scrollTo({{top: document.querySelector({seletor!r}).getBoundingClientRect().top"
                         " + scrollY - 90, behavior: 'smooth'})")
        self.pausa(1)

    # ---- roteiro completo (passos 1 a 5 = roteiro de 2 minutos do README)
    def executar(self):
        pg = self.pg
        self.cartao("""<p class="s">Gestão de Micro e Pequenas Empresas · Sistemas de Informação · UVV</p>
            <h1>Recepção <b>24h</b></h1>
            <p>Atendimento automático 24h com IA, jornada de chegada, calendário único e painel de gestão
            para hotéis e pousadas pequenos.</p>
            <p class="m">Funcionamento completo do protótipo · respostas geradas por IA · hotéis fictícios</p>""", 4.5)

        # 1. atendimento com IA, dois hotéis
        pg.goto(self.base + "/chat?hotel=mare-alta")
        pg.wait_for_load_state("networkidle")
        self.legenda("1/7", "Chat do hóspede da Pousada Maré Alta (na produção, a conversa chega pelo WhatsApp)")
        self.pausa(2)
        self.enviar("boa tarde! vou com minha esposa e meu filho de 3 anos, ele paga? "
                    "e posso levar meu cachorro de 6kg?", espera=1)
        self.legenda("1/7", "O assistente entende a pergunta e responde com as regras deste hotel")
        self.pausa(4)
        self.navegar(lambda: pg.select_option("select.seletor-hotel", "serra-verde"))
        self.legenda("1/7", "Mesmo sistema, outro hotel cliente: Chalés Serra Verde")
        self.pausa(1.5)
        self.enviar("Aceita pet?", espera=1)
        self.legenda("1/7", "Mesma pergunta, resposta diferente: os dados dos hotéis são separados")
        self.pausa(3)

        # 2. disponibilidade e limite do assunto
        self.navegar(lambda: pg.select_option("select.seletor-hotel", "mare-alta"))
        pergunta_vaga = pg.locator(".chip", has_text="Tem vaga de").inner_text()
        self.legenda("2/7", "Consulta de vagas: o assistente confere a disponibilidade real do hotel")
        self.enviar(pergunta_vaga.replace("?", " pra 3 pessoas?"), espera=1)
        self.legenda("2/7", "Tipos livres e tarifa base × noites — sem desconto e sem fechar a reserva sozinha")
        self.pausa(4)
        self.legenda("2/7", "Assunto fora do hotel")
        self.enviar("quem ganhou o jogo do flamengo ontem?", espera=1)
        self.legenda("2/7", "Recusa educada, sem chamar a equipe")
        self.pausa(3)

        # 3. escalonamento
        self.legenda("3/7", "Pedido de desconto: o assistente passa para a equipe")
        self.enviar("Consegue um desconto?", espera=1)
        self.legenda("3/7", "A conversa fica com a equipe e o assistente para de responder nela")
        self.pausa(3)
        self.navegar(lambda: pg.click("nav.menu >> text=Equipe"))
        self.legenda("3/7", "Tela da equipe: só o que exige uma pessoa")
        self.pausa(2.5)
        pg.click(".conversa-escalada input[name=texto]")
        pg.keyboard.type("Olá! Aqui é a Carla, da recepção. No Pix conseguimos 5% para 3 noites.", delay=25)
        self.pausa(0.5)
        self.navegar(lambda: pg.click(".conversa-escalada button:has-text('Enviar')"))
        self.legenda("3/7", "A equipe responde e devolve a conversa ao assistente")
        self.pausa(1.5)
        self.navegar(lambda: pg.click(".conversa-escalada button:has-text('Devolver ao bot')"))
        self.legenda("3/7", "Conversa devolvida: o assistente volta a atender")
        self.pausa(1.5)

        # 4. reserva direta -> jornada
        pg.locator("#nova-reserva").scroll_into_view_if_needed()
        self.legenda("4/7", "Reserva direta pelo WhatsApp, com consentimento do hóspede")
        pg.click("#nova-reserva input[name=nome]")
        pg.keyboard.type("Beatriz Almeida", delay=40)
        pg.click("#nova-reserva input[name=telefone]")
        pg.keyboard.type("(27) 98888-5005", delay=40)
        pg.check("#nova-reserva input[name=consentimento]")
        self.pausa(0.8)
        self.navegar(lambda: pg.click("#nova-reserva button:has-text('Criar reserva')"))
        self.legenda("4/7", "A reserva gera 6 mensagens agendadas: a linha do tempo da jornada")
        self.pausa(3.5)
        for texto in ("Relógio adiantado: saem as boas-vindas com o link da FNRH Digital",
                      "Relógio adiantado: sai a pergunta do horário de chegada"):
            self.legenda("4/7", "O relógio adianta o tempo: “Até a próxima mensagem”")
            self.navegar(lambda: pg.click("button:has-text('Até a próxima mensagem')"))
            self.legenda("4/7", texto)
            self.pausa(2)
        self.legenda("4/7", "Boas-vindas com a FNRH Digital e a pergunta do horário de chegada já enviadas")
        self.pausa(2.5)
        self.navegar(lambda: pg.click("a:has-text('Abrir a conversa no chat')"))
        self.legenda("4/7", "As mensagens chegaram na conversa da hóspede")
        self.pausa(3)
        self.enviar("Chego às 23h", espera=1)
        self.legenda("4/7", "Horário registrado na reserva — e o assistente explica a chegada depois das 22h")
        self.pausa(4)

        # 5. calendário único e alertas
        self.navegar(lambda: pg.click("nav.menu >> text=Equipe"))
        self.rolar_ate("#ical")
        self.legenda("5/7", "Calendário único: as reservas do Airbnb e do Booking entram no mesmo calendário")
        pg.select_option("#ical select[name=unidade_id]", label="101 · Suíte Casal")
        pg.set_input_files("#ical input[name=arquivo]", str(self.ics))
        self.pausa(2)
        self.navegar(lambda: pg.click("#ical button:has-text('Importar iCal')"))
        self.legenda("5/7", "Uma reserva do Airbnb cai em cima de outra: a equipe recebe um alerta de conflito")
        self.rolar_ate("#alertas")
        self.pausa(3.5)
        self.legenda("5/7", "Alertas também para nota baixa na pesquisa pós-estadia e reservas sem valor informado")
        self.pausa(3.5)

        # 6. painel
        self.navegar(lambda: pg.click("nav.menu >> text=Painel"))
        self.legenda("6/7", "Painel do dono: ocupação, diária média (ADR), RevPAR, % de reservas diretas e nota média")
        self.pausa(4)
        self.rolar_ate("#g-semana")
        self.legenda("6/7", "Ocupação por dia da semana e quanto sobra de cada canal depois da comissão do Airbnb e do Booking")
        self.pausa(5)

        # 7. cadastro de um hotel novo
        self.navegar(lambda: pg.click("nav.menu >> text=Novo hotel"))
        self.legenda("7/7", "Cadastro de um hotel novo: horários, políticas, acomodações, canais e perguntas frequentes")
        self.pausa(2.5)
        pg.click("#preencher-exemplo")
        self.pausa(1)
        pg.evaluate("window.scrollTo({top: document.body.scrollHeight / 2, behavior: 'smooth'})")
        self.legenda("7/7", "O horário de check-in/check-out é validado pela Portaria MTur nº 28/2025")
        self.pausa(3)
        self.navegar(lambda: pg.click("#form-hotel button:has-text('Salvar hotel')"))
        self.legenda("7/7", "Hotel salvo: o assistente já atende por ele")
        self.pausa(2.5)
        self.enviar("oi! qual o horário do check-in e do check-out?", espera=1)
        self.legenda("7/7", "Resposta com os dados que acabaram de ser cadastrados")
        self.pausa(4)

        self.cartao("""<h1>Recepção <b>24h</b></h1>
            <p>O hóspede é atendido na hora; a equipe só entra quando precisa de uma pessoa;
            o dono vê como o negócio está indo.</p>
            <p class="m">R$ 249/mês por hotel · atendimento 24h sem aumentar a equipe</p>""", 4)


def gravar(base: str, pasta: Path, ics: Path) -> Path:
    """Executa o roteiro capturando os quadros da tela (screencast do Chrome). Devolve a lista para o ffmpeg."""
    quadros = []  # (instante, arquivo)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        contexto = navegador.new_context(viewport=TAMANHO, locale="pt-BR")
        pagina = contexto.new_page()
        cdp = contexto.new_cdp_session(pagina)

        def quadro(evento):
            arquivo = pasta / f"q{len(quadros):05d}.jpg"
            arquivo.write_bytes(base64.b64decode(evento["data"]))
            quadros.append((evento["metadata"]["timestamp"], arquivo))
            cdp.send("Page.screencastFrameAck", {"sessionId": evento["sessionId"]})

        cdp.on("Page.screencastFrame", quadro)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 90, "maxWidth": TAMANHO["width"],
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
         "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
         "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
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
        print("3/4 gravando o roteiro (cerca de 3 min)")
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

"""Grava o vídeo do roteiro de 2 minutos da demo em docs/video/demo_recepcao24h.mp4.

Uso:  python ferramentas/gravar_demo.py

Precisa do Google Chrome instalado e de:  pip install -r requirements-dev.txt
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
    def __init__(self, pagina, base: str):
        self.pg = pagina
        self.base = base

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
        self.pg.wait_for_function(f"document.querySelectorAll('.bolha').length >= {antes + 2}", timeout=15000)
        self.pausa(espera)

    # ---- roteiro de 2 minutos (o mesmo do README)
    def executar(self):
        pg = self.pg
        self.cartao("""<p class="s">Gestão de Micro e Pequenas Empresas · Sistemas de Informação · UVV</p>
            <h1>Recepção <b>24h</b></h1>
            <p>Atendimento automático 24h, jornada de chegada, calendário único e painel de gestão
            para hotéis e pousadas pequenos.</p>
            <p class="m">Demonstração do protótipo em modo demo · hotéis fictícios</p>""", 4)

        # 1. mesma pergunta, dois hotéis
        pg.goto(self.base + "/chat?hotel=mare-alta")
        pg.wait_for_load_state("networkidle")
        self.legenda("1/5", "Chat do hóspede (simula o WhatsApp) na Pousada Maré Alta")
        self.pausa(1.5)
        self.enviar("Aceita pet?")
        self.legenda("1/5", "Resposta só com a base de conhecimento DESTE hotel")
        self.pausa(1.5)
        self.navegar(lambda: pg.select_option("select.seletor-hotel", "serra-verde"))
        self.legenda("1/5", "Mesma plataforma, outro hotel: Chalés Serra Verde")
        self.pausa(1.2)
        self.enviar("Aceita pet?")
        self.legenda("1/5", "Mesma pergunta, resposta diferente: os dados dos hotéis são separados")
        self.pausa(2)

        # 2. disponibilidade
        self.navegar(lambda: pg.select_option("select.seletor-hotel", "mare-alta"))
        pergunta_vaga = pg.locator(".chip", has_text="Tem vaga de").inner_text()
        self.legenda("2/5", "Consulta de disponibilidade com datas")
        self.enviar(pergunta_vaga, espera=1)
        self.legenda("2/5", "Tipos livres e tarifa base × noites — sem desconto e sem fechar a reserva sozinho")
        self.pausa(3)

        # 3. escalonamento
        self.legenda("3/5", "Pedido de desconto: o assistente passa para a equipe")
        self.enviar("Consegue um desconto?", espera=1)
        self.legenda("3/5", "A conversa fica com a equipe e o assistente pausa (selo no topo)")
        self.pausa(2.5)
        self.navegar(lambda: pg.click("nav.menu >> text=Equipe"))
        self.legenda("3/5", "Tela da equipe: só o que exige uma pessoa")
        self.pausa(2)
        pg.click(".conversa-escalada input[name=texto]")
        pg.keyboard.type("Olá! Aqui é a Carla, da recepção. No Pix conseguimos 5% para 3 noites.", delay=25)
        self.pausa(0.5)
        self.navegar(lambda: pg.click(".conversa-escalada button:has-text('Enviar')"))
        self.legenda("3/5", "A equipe responde e devolve a conversa ao assistente")
        self.pausa(1.2)
        self.navegar(lambda: pg.click(".conversa-escalada button:has-text('Devolver ao bot')"))
        self.legenda("3/5", "Conversa devolvida: o assistente volta a atender")
        self.pausa(1.2)

        # 4. reserva direta -> jornada
        pg.locator("#nova-reserva").scroll_into_view_if_needed()
        self.legenda("4/5", "Reserva direta pelo WhatsApp, com consentimento do hóspede")
        pg.click("#nova-reserva input[name=nome]")
        pg.keyboard.type("Beatriz Almeida", delay=40)
        pg.click("#nova-reserva input[name=telefone]")
        pg.keyboard.type("(27) 98888-5005", delay=40)
        pg.check("#nova-reserva input[name=consentimento]")
        self.pausa(0.8)
        self.navegar(lambda: pg.click("#nova-reserva button:has-text('Criar reserva')"))
        self.legenda("4/5", "A reserva gera 6 mensagens agendadas: a linha do tempo da jornada")
        self.pausa(3)
        for texto in ("Relógio adiantado: saem as boas-vindas com o link da FNRH Digital",
                      "Relógio adiantado: sai a pergunta do horário de chegada"):
            self.legenda("4/5", "Relógio simulado: “Até a próxima mensagem”")
            self.navegar(lambda: pg.click("button:has-text('Até a próxima mensagem')"))
            self.legenda("4/5", texto)
            self.pausa(1.8)
        self.legenda("4/5", "Boas-vindas com a FNRH Digital e a pergunta do horário de chegada já enviadas")
        self.pausa(2.2)
        self.navegar(lambda: pg.click("a:has-text('Abrir a conversa no chat')"))
        self.legenda("4/5", "As mensagens chegaram no WhatsApp (simulado) da hóspede")
        self.pausa(2.5)
        self.enviar("Chego às 23h", espera=1)
        self.legenda("4/5", "Horário registrado na reserva — e o assistente explica a chegada depois das 22h")
        self.pausa(3.2)

        # 5. painel
        self.navegar(lambda: pg.click("nav.menu >> text=Painel"))
        self.legenda("5/5", "Painel: ocupação, ADR, RevPAR, % diretas e resolução do bot")
        self.pausa(3.5)
        pg.evaluate("window.scrollTo({top: document.querySelector('#g-semana').getBoundingClientRect().top"
                    " + scrollY - 120, behavior: 'smooth'})")
        self.legenda("5/5", "Ocupação por dia da semana e receita líquida por canal (comissão das OTAs em laranja)")
        self.pausa(5)

        self.cartao("""<h1>Recepção <b>24h</b></h1>
            <p>O hóspede é atendido na hora; a equipe só entra quando precisa de uma pessoa;
            o dono vê como o negócio está indo.</p>
            <p class="m">github.com/RodrigoFass/recepcao-24h</p>""", 3.5)


def gravar(base: str, pasta: Path) -> Path:
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
        Roteiro(pagina, base).executar()
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
    pasta = Path(tempfile.mkdtemp(prefix="demo_video_"))
    ambiente = {**os.environ, "DATABASE_URL": f"sqlite:///{(pasta / 'demo.db').as_posix()}", "DEMO_MODE": "1"}
    print("1/4 banco temporário com o seed de hoje")
    subprocess.run([sys.executable, "-c", "import seed; seed.gerar(arquivo_ics=None, silencioso=True)"],
                   cwd=RAIZ, env=ambiente, check=True)
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    print(f"2/4 servidor em {base}")
    servidor = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(porta),
                                 "--log-level", "warning"], cwd=RAIZ, env=ambiente)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("O servidor não subiu.")
        print("3/4 gravando o roteiro (cerca de 70 s)")
        (pasta / "quadros").mkdir()
        lista = gravar(base, pasta / "quadros")
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)
    print("4/4 convertendo para MP4")
    duracao = converter(lista, SAIDA)
    print(f"Vídeo: {SAIDA} ({SAIDA.stat().st_size / 1e6:.1f} MB, {duracao})")
    shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    main()

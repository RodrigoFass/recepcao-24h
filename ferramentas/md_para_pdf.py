"""Converte um Markdown de docs/ em PDF A4 (retrato) usando o Google Chrome.

Uso:  python ferramentas/md_para_pdf.py docs/E3_arquitetura.md
Gera o PDF ao lado do .md (mesmo nome). Imagens com caminho relativo funcionam.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

CHROMES = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
           Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
           Path("/usr/bin/google-chrome"), Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", system-ui, Arial, sans-serif; color: #1d2733; font-size: 9.6pt; line-height: 1.45;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 21pt; color: #0e6b6b; margin: 0 0 1mm; letter-spacing: -.01em; }
h1 + p { color: #52606d; margin-top: 0; }
h2 { font-size: 13.5pt; color: #0a5252; margin: 7mm 0 2.5mm; padding-bottom: 1mm; border-bottom: .3mm solid #d6dae0;
     break-after: avoid; }
h3 { font-size: 11pt; margin: 5mm 0 2mm; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
ul { padding-left: 5mm; }
li { margin-bottom: 1.2mm; }
hr { border: 0; border-top: .3mm solid #d6dae0; margin: 4mm 0; }
img { display: block; max-width: 100%; margin: 2mm auto 3mm; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 8.4pt; margin: 2mm 0 3mm; break-inside: auto; }
tr { break-inside: avoid; }
th { text-align: left; background: #e3f1f1; color: #0a5252; font-weight: 700; padding: 1.5mm 2mm;
     border-bottom: .3mm solid #b9d8d8; }
td { padding: 1.4mm 2mm; border-bottom: .2mm solid #e3e6ea; vertical-align: top; }
code { font-family: Consolas, monospace; font-size: 8.4pt; background: #eef0f3; padding: .2mm 1mm; border-radius: 1mm; }
a { color: #0e6b6b; word-break: break-all; }
strong { color: #10232f; }
em { color: #52606d; }
"""


def converter(md: Path) -> Path:
    md = md.resolve()
    corpo = markdown.markdown(md.read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
    titulo = md.stem.replace("_", " ")
    html = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>'
            f"<style>{CSS}</style></head><body>{corpo}</body></html>")
    temporario = md.with_suffix(".tmp.html")  # ao lado do .md, para as imagens relativas funcionarem
    temporario.write_text(html, encoding="utf-8")
    pdf = md.with_suffix(".pdf")
    chrome = next((c for c in CHROMES if c.exists()), None)
    if chrome is None:
        raise SystemExit("Google Chrome não encontrado.")
    try:
        subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tempfile.gettempdir()) / 'recepcao24h-md-pdf'}",
                        "--allow-file-access-from-files", f"--print-to-pdf={pdf}", temporario.resolve().as_uri()],
                       check=True, capture_output=True, timeout=120)
    finally:
        temporario.unlink(missing_ok=True)
    return pdf


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for arg in sys.argv[1:] or ["docs/E3_arquitetura.md"]:
        saida = converter(Path(arg))
        print(f"{saida} ({saida.stat().st_size // 1024} KB)")

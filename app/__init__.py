"""Lê o arquivo .env da raiz do projeto (se existir) para as variáveis de ambiente.

Formato: uma linha NOME=valor por variável; linhas vazias e com # são ignoradas.
Uma variável já definida no ambiente vale mais que a do arquivo.
"""
import os
from pathlib import Path

_ENV = Path(__file__).resolve().parent.parent / ".env"

if _ENV.exists():
    for _linha in _ENV.read_text(encoding="utf-8-sig").splitlines():
        _linha = _linha.strip()
        if _linha and not _linha.startswith("#") and "=" in _linha:
            _nome, _valor = _linha.split("=", 1)
            if _valor.strip():
                os.environ.setdefault(_nome.strip(), _valor.strip().strip('"').strip("'"))

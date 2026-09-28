"""Fixtures comuns.

O seed roda uma vez por sessão num banco-modelo temporário; cada teste recebe
uma cópia desse arquivo, então um teste nunca interfere no outro. Os testes
rodam em modo demo, exceto os marcados com @pytest.mark.llm.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

PASTA_TMP = Path(tempfile.mkdtemp(prefix="recepcao24h_testes_"))
MODELO = PASTA_TMP / "modelo.db"
ICS_TESTE = PASTA_TMP / "exemplo.ics"
os.environ["DATABASE_URL"] = f"sqlite:///{MODELO.as_posix()}"
os.environ["DEMO_MODE"] = "1"

from app import db as banco  # noqa: E402
import seed  # noqa: E402


@pytest.fixture(scope="session")
def banco_modelo():
    banco.configurar(f"sqlite:///{MODELO.as_posix()}")
    resumo = seed.gerar(arquivo_ics=ICS_TESTE, silencioso=True)
    banco.engine.dispose()
    return resumo


@pytest.fixture
def db(banco_modelo, tmp_path):
    arquivo = tmp_path / "teste.db"
    shutil.copyfile(MODELO, arquivo)
    banco.configurar(f"sqlite:///{arquivo.as_posix()}")
    sessao = banco.SessionLocal()
    yield sessao
    sessao.close()
    banco.engine.dispose()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def ics_exemplo(banco_modelo):
    return ICS_TESTE


def pytest_collection_modifyitems(config, items):
    """Testes @pytest.mark.llm só rodam com ANTHROPIC_API_KEY."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    pular = pytest.mark.skip(reason="sem ANTHROPIC_API_KEY (modo IA não testado)")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(pular)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(PASTA_TMP, ignore_errors=True)

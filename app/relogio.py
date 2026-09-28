"""Relógio simulado global.

O "agora" do sistema é o horário real de America/Sao_Paulo mais um
deslocamento guardado no banco (tabela configuracao). Avançar o relógio só
aumenta o deslocamento e depois processa o que venceu (mensagens da jornada,
reenvios, conversas paradas).

Todas as datas-hora do sistema são "ingênuas" (sem fuso) e representam o
horário local de America/Sao_Paulo.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import db as banco
from app.models import Configuracao

FUSO = ZoneInfo("America/Sao_Paulo")
CHAVE = "relogio_deslocamento_s"


def agora_real() -> datetime:
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


def _ler_deslocamento(db) -> float:
    item = db.get(Configuracao, CHAVE)
    return float(item.valor) if item else 0.0


def _gravar_deslocamento(db, segundos: float):
    item = db.get(Configuracao, CHAVE)
    if item is None:
        db.add(Configuracao(chave=CHAVE, valor=str(segundos)))
    else:
        item.valor = str(segundos)
    db.commit()


def agora(db=None) -> datetime:
    if db is None:
        with banco.sessao() as s:
            return agora_real() + timedelta(seconds=_ler_deslocamento(s))
    return agora_real() + timedelta(seconds=_ler_deslocamento(db))


def hoje(db=None) -> date:
    return agora(db).date()


def zerar(db):
    """Volta o relógio para o horário real."""
    _gravar_deslocamento(db, 0.0)


def definir(db, momento: datetime, processar: bool = False):
    """Coloca o relógio num instante exato (usado nos testes)."""
    _gravar_deslocamento(db, (momento - agora_real()).total_seconds())
    if processar:
        from app.servicos.jornada import processar_ate

        processar_ate(db, momento)


def avancar(db, delta: timedelta) -> datetime:
    """Avança o relógio e entrega o que venceu no intervalo."""
    destino = agora(db) + delta
    return avancar_ate(db, destino)


def avancar_ate(db, destino: datetime) -> datetime:
    from app.servicos.jornada import processar_ate

    atual = agora(db)
    if destino > atual:
        _gravar_deslocamento(db, _ler_deslocamento(db) + (destino - atual).total_seconds())
    processar_ate(db, destino)
    return destino

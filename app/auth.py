"""Login: cada hotel tem a sua conta e só enxerga os próprios dados.

A sessão é um cookie assinado com HMAC (id do usuário + assinatura). A chave
vem de SECRET_KEY ou é gerada uma vez e guardada no banco. Senhas com PBKDF2.
"""
import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, Request

from app.models import Configuracao, Hotel, UsuarioEquipe

COOKIE = "sessao_r24h"
ITERACOES = 200_000


class PrecisaLogin(Exception):
    """Página que exige login acessada sem sessão (vira redirecionamento para /entrar)."""


def hash_senha(senha: str) -> str:
    sal = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), ITERACOES).hex()
    return f"pbkdf2${sal}${h}"


def conferir_senha(senha: str, guardada: str | None) -> bool:
    try:
        _, sal, h = (guardada or "").split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), ITERACOES).hex()
    return hmac.compare_digest(calc, h)


def _chave(db) -> bytes:
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"].encode()
    item = db.get(Configuracao, "chave_sessao")
    if item is None:
        item = Configuracao(chave="chave_sessao", valor=secrets.token_hex(32))
        db.add(item)
        db.commit()
    return item.valor.encode()


def _assinar(db, usuario_id: int) -> str:
    assinatura = hmac.new(_chave(db), str(usuario_id).encode(), hashlib.sha256).hexdigest()
    return f"{usuario_id}.{assinatura}"


def autenticar(db, login: str, senha: str) -> UsuarioEquipe | None:
    usuario = db.query(UsuarioEquipe).filter_by(login=(login or "").strip().lower()).first()
    if usuario and conferir_senha(senha, usuario.senha_hash):
        return usuario
    return None


def iniciar_sessao(resposta, db, usuario: UsuarioEquipe):
    resposta.set_cookie(COOKIE, _assinar(db, usuario.id), httponly=True, samesite="lax", max_age=60 * 60 * 12)


def encerrar_sessao(resposta):
    resposta.delete_cookie(COOKIE)


def usuario_logado(request: Request, db) -> UsuarioEquipe | None:
    valor = request.cookies.get(COOKIE, "")
    ident, _, _ = valor.partition(".")
    if not ident.isdigit() or not hmac.compare_digest(valor, _assinar(db, int(ident))):
        return None
    return db.get(UsuarioEquipe, int(ident))


def exigir_usuario(request: Request, db) -> UsuarioEquipe:
    usuario = usuario_logado(request, db)
    if usuario is None:
        raise PrecisaLogin()
    return usuario


def exigir_admin(request: Request, db) -> UsuarioEquipe:
    usuario = exigir_usuario(request, db)
    if not usuario.admin:
        raise HTTPException(403, "Só a administração da Recepção 24h acessa esta página.")
    return usuario


def hotel_do_usuario(request: Request, db, slug: str | None = None) -> Hotel:
    """O hotel que a conta logada pode ver. Hotel: sempre o dela. Administrador: o do slug."""
    usuario = exigir_usuario(request, db)
    if usuario.admin:
        hotel = db.query(Hotel).filter_by(slug=slug).first() if slug else None
    else:
        hotel = usuario.hotel
        if slug and hotel and slug != hotel.slug:
            hotel = None
    if hotel is None:
        raise HTTPException(404, "Hotel não encontrado.")
    return hotel

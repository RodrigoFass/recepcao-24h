"""Entrar e sair, e a área da administração (lista de hotéis clientes)."""
from fastapi import APIRouter, Depends, Form, Request

from app import auth
from app.db import get_db
from app.models import Hotel, Reserva, Unidade, UsuarioEquipe
from app.web import redirecionar, render

router = APIRouter()


def destino_da_conta(usuario) -> str:
    return "/admin" if usuario.admin else "/equipe"


@router.get("/entrar")
def tela_entrar(request: Request, db=Depends(get_db)):
    usuario = auth.usuario_logado(request, db)
    if usuario:
        return redirecionar(destino_da_conta(usuario))
    return render(request, db, "entrar.html", pagina="entrar")


@router.post("/entrar")
def entrar(request: Request, login: str = Form(""), senha: str = Form(""), db=Depends(get_db)):
    usuario = auth.autenticar(db, login, senha)
    if usuario is None:
        resposta = render(request, db, "entrar.html", pagina="entrar", login=login,
                          erro_login="Usuário ou senha incorretos.")
        resposta.status_code = 401
        return resposta
    resposta = redirecionar(destino_da_conta(usuario))
    auth.iniciar_sessao(resposta, db, usuario)
    return resposta


@router.post("/sair")
def sair():
    resposta = redirecionar("/")
    auth.encerrar_sessao(resposta)
    return resposta


@router.get("/admin")
def tela_admin(request: Request, db=Depends(get_db)):
    auth.exigir_admin(request, db)
    hoteis = db.query(Hotel).order_by(Hotel.id).all()
    resumo = {
        h.id: {
            "unidades": db.query(Unidade).filter_by(hotel_id=h.id, ativa=True).count(),
            "reservas": db.query(Reserva).filter_by(hotel_id=h.id).count(),
            "logins": [u.login for u in db.query(UsuarioEquipe).filter_by(hotel_id=h.id) if u.login],
        }
        for h in hoteis
    }
    return render(request, db, "admin.html", pagina="admin", lista_hoteis=hoteis, resumo=resumo)

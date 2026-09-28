"""Cadastro M0: formulário de novo hotel."""
from fastapi import APIRouter, Depends, Request

from app.db import get_db
from app.formatacao import ler_moeda
from app.models import Hotel
from app.servicos.base_conhecimento import PERGUNTAS_MODELO
from app.servicos.cadastro import (
    MODOS_CHEGADA,
    TIPOS_CANAL,
    DadosCanal,
    DadosHotel,
    DadosTipo,
    ErroCadastro,
    cadastrar_hotel,
    expandir_unidades,
)
from app.web import redirecionar, render

router = APIRouter()

N_TIPOS = 4
PADRAO = {
    "checkin_hora": "14:00",
    "checkout_hora": "12:00",
    "modo_chegada": "recepcao_horario",
    "recepcao_inicio": "08:00",
    "recepcao_fim": "22:00",
    "canal_airbnb": "1", "comissao_airbnb": "16",
    "canal_booking": "1", "comissao_booking": "15",
    "canal_whatsapp": "1", "comissao_whatsapp": "0",
    "comissao_telefone": "0", "comissao_balcao": "0",
    "tipo_capacidade_0": "2",
}


def _contexto(valores: dict, erros: list[str] | None = None):
    return {
        "valores": valores,
        "erros": erros or [],
        "perguntas": [p for p in PERGUNTAS_MODELO if not p.get("automatica")],
        "automaticas": [p for p in PERGUNTAS_MODELO if p.get("automatica")],
        "tipos_canal": TIPOS_CANAL,
        "modos_chegada": MODOS_CHEGADA,
        "n_tipos": N_TIPOS,
    }


@router.get("/hoteis/novo")
def tela_cadastro(request: Request, db=Depends(get_db)):
    hotel = db.query(Hotel).order_by(Hotel.id).first()
    return render(request, db, "hotel_novo.html", hotel=hotel, pagina="cadastro", **_contexto(dict(PADRAO)))


def _ligado(form, chave) -> bool:
    return form.get(chave) in ("1", "on", "true", "sim")


def _numero(form, chave):
    try:
        return ler_moeda(form.get(chave))
    except ValueError:
        return None


def dados_do_formulario(form) -> DadosHotel:
    tipos = []
    for i in range(N_TIPOS):
        nome = (form.get(f"tipo_nome_{i}") or "").strip()
        if not nome:
            continue
        try:
            capacidade = int(form.get(f"tipo_capacidade_{i}") or 0)
        except ValueError:
            capacidade = 0
        tipos.append(
            DadosTipo(
                nome=nome,
                capacidade=capacidade,
                tarifa_base=_numero(form, f"tipo_tarifa_{i}") or 0,
                unidades=expandir_unidades(form.get(f"tipo_unidades_{i}", "")),
                descricao=(form.get(f"tipo_descricao_{i}") or "").strip(),
            )
        )
    canais = []
    for t in TIPOS_CANAL:
        if _ligado(form, f"canal_{t}"):
            canais.append(
                DadosCanal(tipo=t, comissao_pct=_numero(form, f"comissao_{t}") or 0,
                           anuncio_por=form.get(f"anuncio_{t}") or "unidade")
            )
    texto = lambda k: (form.get(k) or "").strip()  # noqa: E731
    return DadosHotel(
        nome=texto("nome"),
        cidade=texto("cidade"),
        endereco=texto("endereco"),
        telefone=texto("telefone"),
        whatsapp=texto("whatsapp"),
        checkin_hora=texto("checkin_hora"),
        checkout_hora=texto("checkout_hora"),
        early_checkin_permite=_ligado(form, "early_checkin_permite"),
        early_checkin_a_partir=texto("early_checkin_a_partir"),
        early_checkin_preco=_numero(form, "early_checkin_preco"),
        late_checkout_permite=_ligado(form, "late_checkout_permite"),
        late_checkout_ate=texto("late_checkout_ate"),
        late_checkout_preco=_numero(form, "late_checkout_preco"),
        modo_chegada=texto("modo_chegada"),
        recepcao_inicio=texto("recepcao_inicio"),
        recepcao_fim=texto("recepcao_fim"),
        link_fnrh=texto("link_fnrh"),
        aceita_pet=_ligado(form, "aceita_pet"),
        instrucoes_chegada=texto("instrucoes_chegada"),
        contato_emergencia=texto("contato_emergencia"),
        wifi_rede=texto("wifi_rede"),
        wifi_senha=texto("wifi_senha"),
        wifi_obs=texto("wifi_obs"),
        responsavel_nome=texto("responsavel_nome"),
        responsavel_contato=texto("responsavel_contato"),
        tipos=tipos,
        canais=canais,
        respostas={p["categoria"]: texto(f"kb_{p['categoria']}") for p in PERGUNTAS_MODELO},
    )


@router.post("/hoteis/novo")
async def salvar_cadastro(request: Request, db=Depends(get_db)):
    form = await request.form()
    dados = dados_do_formulario(form)
    try:
        hotel = cadastrar_hotel(db, dados)
    except ErroCadastro as erro:
        db.rollback()
        primeiro = db.query(Hotel).order_by(Hotel.id).first()
        resposta = render(request, db, "hotel_novo.html", hotel=primeiro, pagina="cadastro",
                          **_contexto(dict(form), erro.erros))
        resposta.status_code = 400
        return resposta
    return redirecionar(
        "/chat",
        hotel=hotel.slug,
        msg=f"{hotel.nome} cadastrado, com {len(dados.tipos)} tipo(s) de acomodação e a base de conhecimento. "
        "O assistente virtual já responde por ele.",
    )

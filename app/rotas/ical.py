"""Calendário (M3): exportação de um .ics por unidade e importação pela tela da equipe."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.db import get_db
from app.models import Canal, Unidade
from app.servicos import ical
from app.web import obter_hotel, redirecionar

router = APIRouter()


@router.get("/ical/{slug}/{arquivo}")
def exportar(slug: str, arquivo: str, db=Depends(get_db)):
    hotel = obter_hotel(db, slug)
    if not arquivo.endswith(".ics"):
        raise HTTPException(404, "Use /ical/<hotel>/<unidade>.ics")
    unidade = db.query(Unidade).filter_by(hotel_id=hotel.id, identificacao=arquivo[:-4]).first()
    if unidade is None:
        raise HTTPException(404, "Unidade não encontrada neste hotel.")
    return Response(
        ical.exportar(db, hotel, unidade),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="{hotel.slug}-{unidade.identificacao}.ics"'},
    )


@router.post("/equipe/ical/importar")
async def importar(
    hotel: str = Form(...),
    unidade_id: int = Form(...),
    canal_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db=Depends(get_db),
):
    h = obter_hotel(db, hotel)
    unidade = db.get(Unidade, unidade_id)
    canal = db.get(Canal, canal_id)
    if unidade is None or unidade.hotel_id != h.id or canal is None or canal.hotel_id != h.id:
        raise HTTPException(404, "Unidade ou canal não encontrado neste hotel.")
    conteudo = (await arquivo.read()).decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in conteudo:
        return redirecionar("/equipe", hotel=h.slug, erro="O arquivo enviado não é um calendário .ics.")
    r = ical.importar(db, h, unidade, canal, conteudo, origem=f"arquivo: {arquivo.filename}")
    partes = [f"{r['importadas']} reserva(s) importada(s) na unidade {unidade.identificacao} ({canal.nome})"]
    if r["ja_existiam"]:
        partes.append(f"{r['ja_existiam']} já existia(m)")
    if r["ignoradas"]:
        partes.append(f"{r['ignoradas']} ignorada(s) (passadas ou nossas)")
    if r["conflitos"]:
        partes.append(f"{r['conflitos']} CONFLITO(S) — veja os alertas")
    return redirecionar("/equipe", hotel=h.slug, msg="iCal: " + "; ".join(partes) + ".")

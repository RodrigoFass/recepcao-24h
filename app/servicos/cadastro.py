"""Cadastro de um novo hotel (M0).

Regra da Portaria MTur nº 28/2025: a diária é de 24 horas e o intervalo entre
o check-out e o check-in (limpeza e preparação) pode ser de no máximo 3 horas.
"""
import re
from dataclasses import dataclass, field

from app import relogio
from app.formatacao import formatar_telefone, hora_br, minutos, normalizar
from app.models import Canal, Hotel, TipoAcomodacao, Unidade, UsuarioEquipe
from app.servicos.base_conhecimento import gerar_base

INTERVALO_MAXIMO_MIN = 3 * 60
TIPOS_CANAL = ["airbnb", "booking", "whatsapp", "telefone", "balcao"]
MODOS_CHEGADA = ["recepcao_24h", "recepcao_horario", "autoatendimento"]


class ErroCadastro(ValueError):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


@dataclass
class DadosTipo:
    nome: str
    capacidade: int
    tarifa_base: float
    unidades: list[str]
    descricao: str = ""


@dataclass
class DadosCanal:
    tipo: str
    comissao_pct: float
    anuncio_por: str = "unidade"


@dataclass
class DadosHotel:
    nome: str
    cidade: str
    endereco: str
    checkin_hora: str
    checkout_hora: str
    modo_chegada: str
    slug: str = ""
    telefone: str = ""
    whatsapp: str = ""
    early_checkin_permite: bool = False
    early_checkin_a_partir: str = ""
    early_checkin_preco: float | None = None
    late_checkout_permite: bool = False
    late_checkout_ate: str = ""
    late_checkout_preco: float | None = None
    recepcao_inicio: str = ""
    recepcao_fim: str = ""
    link_fnrh: str = ""
    aceita_pet: bool = False
    instrucoes_chegada: str = ""
    contato_emergencia: str = ""
    wifi_rede: str = ""
    wifi_senha: str = ""
    wifi_obs: str = ""
    responsavel_nome: str = ""
    responsavel_contato: str = ""
    tipos: list[DadosTipo] = field(default_factory=list)
    canais: list[DadosCanal] = field(default_factory=list)
    respostas: dict[str, str] = field(default_factory=dict)


def validar_intervalo(checkout_hora: str, checkin_hora: str) -> str | None:
    """Erro (texto) se o intervalo entre check-out e check-in não respeitar a Portaria MTur 28/2025."""
    try:
        saida, entrada = minutos(checkout_hora), minutos(checkin_hora)
    except (ValueError, AttributeError):
        return "Informe os horários de check-in e de check-out no formato HH:MM."
    intervalo = entrada - saida
    if intervalo < 0:
        return (
            f"O check-in ({hora_br(checkin_hora)}) precisa ser depois do check-out ({hora_br(checkout_hora)}), "
            "para a diária de 24 horas."
        )
    if intervalo > INTERVALO_MAXIMO_MIN:
        horas = f"{intervalo // 60}h" + (f"{intervalo % 60:02d}" if intervalo % 60 else "")
        return (
            f"Pela Portaria MTur nº 28/2025, o intervalo entre o check-out e o check-in pode ser de no máximo "
            f"3 horas (limpeza e preparação). Com check-out às {hora_br(checkout_hora)} e check-in às "
            f"{hora_br(checkin_hora)}, o intervalo é de {horas}."
        )
    return None


def expandir_unidades(texto: str) -> list[str]:
    """'101-104, 201' -> ['101','102','103','104','201']; 'C1-C3' -> ['C1','C2','C3']."""
    resultado = []
    for parte in re.split(r"[,;\n]+", texto or ""):
        parte = parte.strip()
        if not parte:
            continue
        faixa = re.fullmatch(r"([A-Za-z]*)(\d+)\s*-\s*\1?(\d+)", parte)
        if faixa and int(faixa.group(3)) >= int(faixa.group(2)) and int(faixa.group(3)) - int(faixa.group(2)) < 100:
            prefixo, ini, fim = faixa.group(1), int(faixa.group(2)), int(faixa.group(3))
            largura = len(faixa.group(2)) if faixa.group(2).startswith("0") else 0
            resultado += [f"{prefixo}{str(n).zfill(largura)}" for n in range(ini, fim + 1)]
        else:
            resultado.append(parte)
    return resultado


def gerar_slug(db, nome: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", normalizar(nome)).strip("-") or "hotel"
    slug, n = base, 2
    while db.query(Hotel).filter_by(slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    return slug


def validar(db, d: DadosHotel) -> list[str]:
    erros = []
    if not d.nome.strip():
        erros.append("Informe o nome do hotel.")
    if not d.cidade.strip():
        erros.append("Informe a cidade.")
    if not d.endereco.strip():
        erros.append("Informe o endereço.")
    erro_horario = validar_intervalo(d.checkout_hora, d.checkin_hora)
    if erro_horario:
        erros.append(erro_horario)
    else:
        if d.early_checkin_permite and d.early_checkin_a_partir and minutos(d.early_checkin_a_partir) >= minutos(d.checkin_hora):
            erros.append("O early check-in precisa começar antes do horário normal de check-in.")
        if d.late_checkout_permite and d.late_checkout_ate and minutos(d.late_checkout_ate) <= minutos(d.checkout_hora):
            erros.append("O late check-out precisa terminar depois do horário normal de check-out.")
    if d.modo_chegada not in MODOS_CHEGADA:
        erros.append("Escolha o modo de chegada.")
    if d.modo_chegada == "recepcao_horario" and not (d.recepcao_inicio and d.recepcao_fim):
        erros.append("Informe o horário de funcionamento da recepção.")
    if d.slug and db.query(Hotel).filter_by(slug=d.slug).first():
        erros.append(f"Já existe um hotel com o identificador \"{d.slug}\".")
    if not d.tipos:
        erros.append("Cadastre pelo menos um tipo de acomodação, com suas unidades.")
    idents = [u for t in d.tipos for u in t.unidades]
    if len(idents) != len(set(idents)):
        erros.append("Há identificação de unidade repetida.")
    for t in d.tipos:
        if not t.unidades:
            erros.append(f"Informe as unidades do tipo \"{t.nome}\".")
        if t.capacidade < 1 or t.tarifa_base <= 0:
            erros.append(f"Capacidade e tarifa base do tipo \"{t.nome}\" precisam ser maiores que zero.")
    if not d.canais:
        erros.append("Marque pelo menos um canal de venda.")
    return erros


def cadastrar_hotel(db, d: DadosHotel) -> Hotel:
    erros = validar(db, d)
    if erros:
        raise ErroCadastro(erros)
    agora = relogio.agora(db)
    politicas = {
        "aceita_pet": d.aceita_pet,
        "instrucoes_chegada": d.instrucoes_chegada.strip(),
        "contato_emergencia": d.contato_emergencia.strip() or d.whatsapp.strip() or d.telefone.strip(),
        "wifi_rede": d.wifi_rede.strip(),
        "wifi_senha": d.wifi_senha.strip(),
        "wifi_obs": d.wifi_obs.strip(),
    }
    if d.early_checkin_permite and d.early_checkin_a_partir:
        politicas["early_checkin_a_partir"] = d.early_checkin_a_partir
    if d.late_checkout_permite and d.late_checkout_ate:
        politicas["late_checkout_ate"] = d.late_checkout_ate

    hotel = Hotel(
        nome=d.nome.strip(),
        slug=d.slug or gerar_slug(db, d.nome),
        cidade=d.cidade.strip(),
        endereco=d.endereco.strip(),
        telefone=formatar_telefone(d.telefone) if d.telefone.strip() else None,
        whatsapp=formatar_telefone(d.whatsapp) if d.whatsapp.strip() else None,
        checkin_hora=d.checkin_hora,
        checkout_hora=d.checkout_hora,
        early_checkin_permite=d.early_checkin_permite,
        early_checkin_preco=d.early_checkin_preco if d.early_checkin_permite else None,
        late_checkout_permite=d.late_checkout_permite,
        late_checkout_preco=d.late_checkout_preco if d.late_checkout_permite else None,
        modo_chegada=d.modo_chegada,
        recepcao_inicio=d.recepcao_inicio or None,
        recepcao_fim=d.recepcao_fim or None,
        link_fnrh=d.link_fnrh.strip() or None,
        politicas=politicas,
        fuso="America/Sao_Paulo",
    )
    db.add(hotel)
    db.flush()
    for t in d.tipos:
        tipo = TipoAcomodacao(hotel_id=hotel.id, nome=t.nome.strip(), capacidade=t.capacidade,
                              tarifa_base=t.tarifa_base, descricao=t.descricao or None)
        db.add(tipo)
        db.flush()
        for ident in t.unidades:
            db.add(Unidade(hotel_id=hotel.id, tipo_id=tipo.id, identificacao=ident, ativa=True))
    for c in d.canais:
        db.add(Canal(hotel_id=hotel.id, tipo=c.tipo, comissao_pct=c.comissao_pct, anuncio_por=c.anuncio_por))
    if d.responsavel_nome.strip():
        db.add(UsuarioEquipe(hotel_id=hotel.id, nome=d.responsavel_nome.strip(), papel="responsável",
                             contato_alerta=d.responsavel_contato.strip() or None))
    respostas = dict(d.respostas)
    if not (respostas.get("pet") or "").strip():
        respostas["pet"] = (
            "Sim, aceitamos pets. Fale com a equipe sobre as condições." if d.aceita_pet
            else "Infelizmente não aceitamos pets."
        )
    gerar_base(db, hotel, respostas, agora)
    db.commit()
    return hotel

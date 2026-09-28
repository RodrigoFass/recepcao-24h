"""Formatação para exibição (padrão brasileiro) e normalização de texto."""
import re
import unicodedata
from datetime import date, datetime

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
DIAS_SEMANA_LONGO = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def moeda(valor) -> str:
    """1234.5 -> 'R$ 1.234,50'."""
    if valor is None:
        return "—"
    texto = f"{float(valor):,.2f}"  # 1,234.50
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def moeda_curta(valor) -> str:
    """Sem centavos quando o valor é inteiro: 'R$ 280' / 'R$ 62,50'."""
    if valor is None:
        return "—"
    if float(valor).is_integer():
        return f"R$ {int(valor):,}".replace(",", ".")
    return moeda(valor)


def data_br(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        return d.strftime("%d/%m/%Y %H:%M")
    return d.strftime("%d/%m/%Y")


def data_curta(d: date) -> str:
    return d.strftime("%d/%m")


def hora_br(hhmm: str | None) -> str:
    """'14:00' -> '14h'; '22:30' -> '22h30'."""
    if not hhmm:
        return "—"
    h, m = hhmm.split(":")[:2]
    h = str(int(h))
    return f"{h}h" if m == "00" else f"{h}h{m}"


def pct(valor, casas=1) -> str:
    if valor is None:
        return "—"
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


def numero(valor, casas=1) -> str:
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def ler_moeda(texto: str | None) -> float | None:
    """'1.234,56' / 'R$ 1234.56' / '560' -> float. Vazio -> None."""
    t = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def minutos(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def hhmm(total_minutos: int) -> str:
    total_minutos %= 24 * 60
    return f"{total_minutos // 60:02d}:{total_minutos % 60:02d}"


# ---------------------------------------------------------------- texto

_FEMININOS = {"pousada", "hospedaria", "casa", "estalagem", "fazenda", "vila", "cabana", "suite", "residencia",
              "morada", "chacara", "estancia", "hostal"}
_PREPOSICOES = {
    "de": {("m", "s"): "do", ("f", "s"): "da", ("m", "p"): "dos", ("f", "p"): "das"},
    "a": {("m", "s"): "ao", ("f", "s"): "à", ("m", "p"): "aos", ("f", "p"): "às"},
    "em": {("m", "s"): "no", ("f", "s"): "na", ("m", "p"): "nos", ("f", "p"): "nas"},
}


def com_preposicao(nome: str, preposicao: str) -> str:
    """'de' + 'Pousada Maré Alta' -> 'da Pousada Maré Alta'; 'a' + 'Chalés Serra Verde' -> 'aos Chalés Serra Verde'.

    Gênero e número vêm da primeira palavra do nome (padrão: masculino singular, como "Hotel", "Hostel").
    """
    palavra = sem_acentos(nome.split()[0].lower()) if nome.strip() else ""
    conhecidas = _FEMININOS | {"chale", "apartamento", "flat", "bangalo", "quarto", "loft", "studio"}
    numero = "p" if palavra.endswith("s") and palavra[:-1] in conhecidas else "s"
    base = palavra[:-1] if numero == "p" else palavra
    genero = "f" if base in _FEMININOS else "m"
    return f"{_PREPOSICOES[preposicao][(genero, numero)]} {nome}"

def sem_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_TROCAS = [
    (r"\bcheck\s+in\b", "checkin"),
    (r"\bcheck\s+out\b", "checkout"),
    (r"\bwi\s+fi\b", "wifi"),
    (r"\bweb\s+check\b", "webcheck"),
]


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, sem pontuação (exceto / e : de datas e horas)."""
    t = sem_acentos(texto.lower())
    t = re.sub(r"[^a-z0-9/:\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for padrao, troca in _TROCAS:
        t = re.sub(padrao, troca, t)
    return t


def telefone_digitos(tel: str | None) -> str:
    return re.sub(r"\D", "", tel or "")


def formatar_telefone(tel: str) -> str:
    """Normaliza para '(27) 99812-3456' quando possível."""
    d = telefone_digitos(tel)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel.strip()

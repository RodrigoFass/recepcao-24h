"""Popula o banco com os dois hotéis FICTÍCIOS da demo.

Uso:  python seed.py

"Hoje" é a data em que o seed roda. Rode no dia da apresentação para as datas
ficarem atuais. O script apaga e recria todo o banco e zera o relógio simulado.
Semente fixa (42): no mesmo dia, o resultado é sempre o mesmo.
"""
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app import db as banco
from app import relogio
from app.bot import textos
from app.models import (
    Alerta,
    Avaliacao,
    Canal,
    Conversa,
    Hospede,
    Hotel,
    Mensagem,
    Reserva,
    TipoAcomodacao,
    Unidade,
    UsuarioEquipe,
)
from app.formatacao import hora_br
from app.servicos.base_conhecimento import gerar_base, item_por_categoria
from app.servicos.conversas import registrar
from app.servicos.disponibilidade import proxima_sexta
from app.servicos.ical import EventoIcal, gerar_ics
from app.servicos.jornada import gerar_jornada, processar_ate
from app.servicos.reservas import valor_sugerido

RAIZ = Path(__file__).resolve().parent
ARQUIVO_ICS = RAIZ / "data" / "exemplo.ics"

# --------------------------------------------------------------------- dados

HOTEIS = [
    {
        "hotel": dict(
            nome="Pousada Maré Alta",
            slug="mare-alta",
            cidade="Guarapari (ES)",
            endereco="Rua das Gaivotas, 120 – Praia do Farol, Guarapari/ES (endereço fictício)",
            telefone="(27) 3000-0101",
            whatsapp="(27) 99000-0101",
            checkin_hora="14:00",
            checkout_hora="12:00",
            early_checkin_permite=True,
            early_checkin_preco=60,
            late_checkout_permite=True,
            late_checkout_preco=60,
            modo_chegada="recepcao_horario",
            recepcao_inicio="08:00",
            recepcao_fim="22:00",
            link_fnrh="https://fnrh-digital.exemplo/pre-checkin/mare-alta",
            politicas={
                "aceita_pet": True,
                "early_checkin_a_partir": "11:00",
                "late_checkout_ate": "14:00",
                "wifi_rede": "MareAlta_Hospedes",
                "wifi_senha": "marealta2026",
                "instrucoes_chegada": (
                    "A recepção funciona das 8h às 22h e vai te receber com a chave. "
                    "Se chegar depois das 22h, a chave fica no cofre ao lado da porta de entrada."
                ),
                "contato_emergencia": "(27) 99000-0199",
                "google_avaliacao": "https://g.page/exemplo-pousada-mare-alta/review",
            },
        ),
        "tipos": [
            ("Suíte Casal", 2, 280, "Cama de casal, ar-condicionado, frigobar e varanda.", [f"{n}" for n in range(101, 109)]),
            ("Suíte Família", 4, 380, "Cama de casal + 2 de solteiro, ar-condicionado e frigobar.", [f"{n}" for n in range(201, 205)]),
        ],
        "canais": [("airbnb", 16, 50), ("booking", 15, 20), ("whatsapp", 0, 20), ("telefone", 0, 10)],
        "ocupacao_alvo": 0.55,
        "respostas": {
            "pet": "Sim! Aceitamos 1 pet por quarto, de até 10 kg, com taxa de R$ 50 por estadia. Avise na reserva, por favor.",
            "cafe": "O café da manhã está incluso na diária e é servido das 7h30 às 10h.",
            "estacionamento": "Temos estacionamento gratuito com 10 vagas, sem reserva (por ordem de chegada).",
            "como_chegar": (
                "Estamos na Rua das Gaivotas, 120, Praia do Farol, em Guarapari (ES), a 150 m da praia. "
                "No GPS, procure por \"Pousada Maré Alta\"."
            ),
            "chegada_fora_horario": (
                "A recepção funciona das 8h às 22h. Se você chegar depois das 22h, a chave fica num cofre na "
                "entrada, e o código do cofre é enviado por mensagem no dia da chegada."
            ),
            "criancas": "Crianças até 5 anos não pagam no quarto dos pais. Temos berço sem custo, é só pedir com antecedência.",
            "cancelamento": "O cancelamento é grátis até 7 dias antes do check-in. Depois disso, é cobrado 50% do valor da reserva.",
            "pagamento": (
                "Nas reservas diretas pedimos um sinal de 30% via Pix para confirmar; o restante pode ser pago no "
                "check-in (Pix, cartão ou dinheiro). Reservas do Airbnb e do Booking são pagas na própria plataforma."
            ),
            "lazer": "Temos piscina, aberta das 8h às 20h. A praia fica a 150 m da pousada.",
            "silencio": "Pedimos silêncio a partir das 22h, para o descanso de todos os hóspedes.",
            "roupa_cama": "Sim, roupa de cama e toalhas de banho estão incluídas. Para praia e piscina, leve a sua toalha.",
            "turismo": (
                "A praia fica a 150 m. Perto daqui: a orla com quiosques (5 min a pé), o centrinho com restaurantes "
                "(10 min de carro) e passeios de barco saindo do píer (15 min de carro)."
            ),
        },
        "equipe": ("Carla Mendes", "gerente", "(27) 99000-0199"),
    },
    {
        "hotel": dict(
            nome="Chalés Serra Verde",
            slug="serra-verde",
            cidade="Domingos Martins (ES)",
            endereco="Estrada do Vale Verde, km 3 – Domingos Martins/ES (endereço fictício)",
            telefone="(27) 3000-0202",
            whatsapp="(27) 99000-0202",
            checkin_hora="15:00",
            checkout_hora="12:00",
            early_checkin_permite=False,
            early_checkin_preco=None,
            late_checkout_permite=False,
            late_checkout_preco=None,
            modo_chegada="autoatendimento",
            recepcao_inicio="08:00",
            recepcao_fim="20:00",
            link_fnrh="https://fnrh-digital.exemplo/pre-checkin/serra-verde",
            politicas={
                "aceita_pet": False,
                "wifi_rede": "SerraVerde",
                "wifi_senha": "serra2026",
                "wifi_obs": "O sinal de celular é fraco na região, então o wifi é a melhor opção.",
                "instrucoes_chegada": (
                    "A entrada é por autoatendimento: use a senha abaixo na fechadura do seu chalé. "
                    "O zelador atende por telefone das 8h às 20h."
                ),
                "contato_emergencia": "(27) 99000-0299",
                "google_avaliacao": "https://g.page/exemplo-chales-serra-verde/review",
            },
        ),
        "tipos": [
            ("Chalé Casal", 2, 420, "Chalé com lareira, cama de casal e varanda com vista.", [f"C{n}" for n in range(1, 7)]),
            ("Chalé Família", 4, 560, "Chalé com lareira, 2 quartos e cozinha completa.", ["F1", "F2"]),
        ],
        "canais": [("airbnb", 16, 40), ("booking", 15, 10), ("whatsapp", 0, 50)],
        "ocupacao_alvo": 0.45,
        "respostas": {
            "pet": "Infelizmente não aceitamos pets.",
            "cafe": "O café da manhã está incluso: entregamos uma cesta no seu chalé todos os dias às 8h.",
            "estacionamento": "O estacionamento é gratuito, com 1 vaga em frente a cada chalé.",
            "como_chegar": (
                "Ficamos na Estrada do Vale Verde, km 3, em Domingos Martins (ES). O acesso tem 3 km de estrada "
                "de terra, que carro comum passa tranquilamente. Recomendamos chegar com luz do dia."
            ),
            "chegada_fora_horario": (
                "A entrada é por autoatendimento: a senha da fechadura do chalé é enviada por mensagem no dia, 3h "
                "antes do check-in, e você pode chegar a qualquer hora depois das 15h. O zelador atende por "
                "telefone das 8h às 20h."
            ),
            "criancas": "Crianças são bem-vindas somente no Chalé Família, que acomoda até 4 pessoas.",
            "cancelamento": "O cancelamento é grátis até 15 dias antes do check-in. Depois disso, não há reembolso.",
            "pagamento": (
                "Nas reservas pelo WhatsApp, o pagamento é por Pix: 50% para confirmar e o restante até o "
                "check-in. Reservas do Airbnb e do Booking são pagas na própria plataforma."
            ),
            "lazer": "Todos os chalés têm lareira, com lenha inclusa (1 cesto por dia). A região tem trilhas e cachoeiras.",
            "silencio": "Pedimos silêncio após as 22h: a proposta dos chalés é descanso e natureza.",
            "roupa_cama": "Sim, roupa de cama, cobertores e toalhas de banho estão incluídos.",
            "turismo": (
                "Perto dos chalés há trilhas, uma cachoeira a 4 km e a rota do agroturismo, com cafés e "
                "queijarias. O centro de Domingos Martins fica a 20 min de carro."
            ),
        },
        "equipe": ("Joaquim Rocha", "proprietário", "(27) 99000-0299"),
    },
]

NOMES = [
    "Ana", "Bruno", "Camila", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João",
    "Karina", "Lucas", "Mariana", "Nicolas", "Olívia", "Paulo", "Rafaela", "Samuel", "Tatiane", "Vinícius",
    "Larissa", "Rodrigo", "Juliana", "Marcelo", "Patrícia", "Gustavo", "Letícia", "André", "Beatriz", "Caio",
]
SOBRENOMES = [
    "Almeida", "Barbosa", "Cardoso", "Dias", "Esteves", "Ferreira", "Gomes", "Lima", "Moreira", "Nunes",
    "Oliveira", "Pereira", "Queiroz", "Ribeiro", "Santos", "Teixeira", "Vieira", "Xavier", "Costa", "Martins",
]

# probabilidade relativa de começar uma estadia em cada dia (seg..dom):
# quinta e sexta concentram as chegadas, deixando sexta e sábado mais cheios
PESO_CHECKIN = [0.35, 0.30, 0.35, 0.60, 1.00, 0.55, 0.25]
DURACOES, PESOS_DURACAO = [1, 2, 3, 4], [20, 30, 30, 20]  # média 2,5 noites
DIAS_HISTORICO = 90


def simular_historico(n_unidades: int, k: float, inicio: date, fim: date, seed: int):
    """Passeia dia a dia por unidade sorteando estadias. Devolve (unidade, check_in, check_out)."""
    rng = random.Random(seed)
    estadias = []
    for u in range(n_unidades):
        d = inicio
        while d < fim:
            if rng.random() < min(0.95, k * PESO_CHECKIN[d.weekday()]):
                n = rng.choices(DURACOES, PESOS_DURACAO)[0]
                if d.weekday() == 4:
                    n = max(n, 2)  # quem chega na sexta fica o fim de semana
                estadias.append((u, d, d + timedelta(days=n)))
                d += timedelta(days=n)
            else:
                d += timedelta(days=1)
    return estadias


def ocupacao_estadias(estadias, n_unidades: int, inicio: date, fim: date) -> float:
    """Ocupação das noites de inicio..fim (inclusive)."""
    noites = 0
    for _, ci, co in estadias:
        a, b = max(ci, inicio), min(co, fim + timedelta(days=1))
        noites += max(0, (b - a).days)
    return noites / (n_unidades * ((fim - inicio).days + 1))


# ------------------------------------------------------------------ gerador

class GeradorHotel:
    def __init__(self, db, cfg, agora: datetime, indice: int, telefones_usados: set):
        self.db = db
        self.cfg = cfg
        self.agora = agora
        self.hoje = agora.date()
        self.indice = indice
        self.telefones = telefones_usados
        self.ocupado: dict[int, set[date]] = {}
        self.reservas: list[Reserva] = []
        self.noites_fds_cheio: set[date] = set()

    # ---- cadastro
    def criar_hotel(self):
        cfg, db = self.cfg, self.db
        self.hotel = Hotel(**cfg["hotel"])
        db.add(self.hotel)
        db.flush()
        self.unidades = []
        for nome, cap, tarifa, desc, idents in cfg["tipos"]:
            tipo = TipoAcomodacao(hotel_id=self.hotel.id, nome=nome, capacidade=cap, tarifa_base=tarifa, descricao=desc)
            db.add(tipo)
            db.flush()
            for ident in idents:
                un = Unidade(hotel_id=self.hotel.id, tipo_id=tipo.id, identificacao=ident, ativa=True)
                un.tipo = tipo
                db.add(un)
                self.unidades.append(un)
        self.canais = {}
        self.pesos_canais = []
        for tipo, comissao, peso in cfg["canais"]:
            canal = Canal(hotel_id=self.hotel.id, tipo=tipo, comissao_pct=comissao, anuncio_por="unidade")
            db.add(canal)
            self.canais[tipo] = canal
            self.pesos_canais.append((tipo, peso))
        db.flush()
        for un in self.unidades:
            self.ocupado[un.id] = set()
        gerar_base(db, self.hotel, cfg["respostas"], self.agora - timedelta(days=20))
        nome, papel, contato = cfg["equipe"]
        db.add(UsuarioEquipe(hotel_id=self.hotel.id, nome=nome, papel=papel, contato_alerta=contato))

    # ---- auxiliares
    def novo_telefone(self) -> str:
        while True:
            ddd = random.choice(["27", "27", "27", "27", "11", "21", "31"])
            numero = f"9{random.randint(8000, 9999)}{random.randint(0, 9999):04d}"
            tel = f"({ddd}) {numero[:5]}-{numero[5:]}"
            if tel not in self.telefones:
                self.telefones.add(tel)
                return tel

    def livre(self, un: Unidade, ci: date, co: date) -> bool:
        d = ci
        while d < co:
            if d in self.ocupado[un.id]:
                return False
            d += timedelta(days=1)
        return True

    def livres_na_noite(self, noite: date) -> int:
        return sum(1 for un in self.unidades if noite not in self.ocupado[un.id])

    def reservar(self, un: Unidade, ci: date, co: date, canal_tipo: str | None = None, criada_em=None) -> Reserva:
        canal_tipo = canal_tipo or random.choices(
            [t for t, _ in self.pesos_canais], [p for _, p in self.pesos_canais]
        )[0]
        canal = self.canais[canal_tipo]
        direto = canal.comissao_pct == 0
        if criada_em is None:
            criada_em = datetime.combine(ci - timedelta(days=random.randint(2, 40)), time(random.randint(8, 22), random.choice([0, 15, 30, 45])))
            if criada_em > self.agora:
                criada_em = self.agora - timedelta(hours=random.randint(2, 30))

        nome = f"{random.choice(NOMES)} {random.choice(SOBRENOMES)}"
        telefone = None
        consentimento = None
        if direto:
            telefone = self.novo_telefone()
            consentimento = criada_em
        elif random.random() < 0.3:
            telefone = self.novo_telefone()  # veio pelo CSV da OTA, sem consentimento
        hospede = Hospede(
            hotel_id=self.hotel.id,
            nome=nome,
            telefone=telefone,
            email=None,
            consentimento_whatsapp_em=consentimento,
            idioma="pt",
        )
        self.db.add(hospede)

        tipo = un.tipo
        valor = valor_sugerido(tipo.tarifa_base, ci, co)
        if not direto and random.random() < 0.2:
            valor = None  # o iCal não traz valor: fica pendente
        codigo = None
        if canal_tipo == "airbnb":
            codigo = "HM" + "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
        elif canal_tipo == "booking":
            codigo = str(random.randint(1000000000, 9999999999))

        r = Reserva(
            hotel_id=self.hotel.id,
            unidade=un,
            hospede=hospede,
            canal=canal,
            check_in=ci,
            check_out=co,
            num_hospedes=min(tipo.capacidade, random.choice([1, 2, 2, 2, 3, 4])),
            valor_total=valor,
            status="concluida" if co < self.hoje else "confirmada",
            origem="seed",
            codigo_externo=codigo,
            criada_em=criada_em,
        )
        self.db.add(r)
        d = ci
        while d < co:
            self.ocupado[un.id].add(d)
            d += timedelta(days=1)
        self.reservas.append(r)
        return r

    # ---- reservas
    def gerar_historico(self):
        inicio = self.hoje - timedelta(days=DIAS_HISTORICO + 4)
        periodo_ini = self.hoje - timedelta(days=DIAS_HISTORICO)
        periodo_fim = self.hoje - timedelta(days=1)
        n = len(self.unidades)
        semente = 42 + self.indice
        # calibra a probabilidade para chegar perto da ocupação-alvo
        melhor_k, melhor_erro = 0.1, 9.0
        for i in range(5, 200):
            k = i / 100
            est = simular_historico(n, k, inicio, self.hoje, semente)
            erro = abs(ocupacao_estadias(est, n, periodo_ini, periodo_fim) - self.cfg["ocupacao_alvo"])
            if erro < melhor_erro:
                melhor_k, melhor_erro = k, erro
        for u, ci, co in simular_historico(n, melhor_k, inicio, self.hoje, semente):
            self.reservar(self.unidades[u], ci, co)

    def primeira_unidade_livre(self, ci: date, co: date, unidades=None):
        candidatas = list(unidades or self.unidades)
        random.shuffle(candidatas)
        for un in candidatas:
            if self.livre(un, ci, co):
                return un
        return None

    def gerar_futuro(self, alvo=15, lotar_fds=False, reserva_na_unidade: str | None = None):
        hoje = self.hoje
        # chegada hoje e amanhã (reservas diretas, com telefone e consentimento)
        for dia in (hoje, hoje + timedelta(days=1)):
            un = self.primeira_unidade_livre(dia, dia + timedelta(days=2))
            if un is None:  # improvável; libera uma noite só
                un = self.primeira_unidade_livre(dia, dia + timedelta(days=1))
                self.reservar(un, dia, dia + timedelta(days=1), "whatsapp")
            else:
                self.reservar(un, dia, dia + timedelta(days=2), "whatsapp")

        sexta = proxima_sexta(hoje)
        if lotar_fds:
            noites = [sexta, sexta + timedelta(days=1)]
            self.noites_fds_cheio = set(noites)
            for un in self.unidades:
                livres = [n for n in noites if n not in self.ocupado[un.id]]
                # agrupa noites livres consecutivas numa reserva só
                while livres:
                    ci = livres[0]
                    co = ci + timedelta(days=1)
                    while co in livres:
                        co += timedelta(days=1)
                    self.reservar(un, ci, co)
                    livres = [n for n in livres if n >= co]

        if reserva_na_unidade:
            un = next(u for u in self.unidades if u.identificacao == reserva_na_unidade)
            ci = hoje + timedelta(days=8)
            while not self.livre(un, ci - timedelta(days=1), ci + timedelta(days=2)):
                ci += timedelta(days=1)
            self.reserva_exemplo_ics = self.reservar(un, ci, ci + timedelta(days=2), "booking")

        tentativas = 0
        while self.contar_futuras() < alvo and tentativas < 1000:
            tentativas += 1
            ci = hoje + timedelta(days=random.randint(2, 29))
            co = ci + timedelta(days=random.choices(DURACOES, PESOS_DURACAO)[0])
            un = random.choice(self.unidades)
            if not self.livre(un, ci, co):
                continue
            # mantém pelo menos 3 unidades livres nas noites de sexta e sábado
            # (exceto no fim de semana lotado de propósito)
            noites = [ci + timedelta(days=i) for i in range((co - ci).days)]
            if any(
                n.weekday() in (4, 5) and n not in self.noites_fds_cheio and self.livres_na_noite(n) <= 3
                for n in noites
            ):
                continue
            self.reservar(un, ci, co)

    def contar_futuras(self) -> int:
        return sum(1 for r in self.reservas if r.check_in >= self.hoje)

    def gerar_jornadas(self):
        """Jornada das reservas em andamento e futuras, como se o sistema já estivesse rodando.

        As mensagens vencidas são entregues depois, por processar_ate(). Quem já recebeu a
        pergunta do horário de chegada "responde" (para o seed não começar cheio de alertas).
        """
        self.respostas_hora = []
        for r in self.reservas:
            if r.check_out < self.hoje:
                continue
            msgs = gerar_jornada(self.db, r, momento=r.criada_em, entregar=False)
            for m in msgs:
                if m.meio == "ota_manual" and m.enviar_em <= self.agora:
                    m.status = "enviada"  # a equipe já copiou no chat da OTA
            pergunta = next(m for m in msgs if m.etapa == "hora_chegada")
            if pergunta.meio == "whatsapp" and pergunta.enviar_em <= self.agora:
                r.hora_prevista_chegada = random.choice(["14:30", "15:30", "16:00", "17:00", "18:30", "20:00", "23:00"])
                self.respostas_hora.append((r, pergunta))

    def simular_respostas_hora(self):
        for r, pergunta in self.respostas_hora:
            quando = pergunta.enviar_em + timedelta(minutes=random.randint(15, 90))
            if quando >= self.agora:
                continue
            conv = (
                self.db.query(Conversa)
                .filter(Conversa.hotel_id == self.hotel.id, Conversa.telefone == r.hospede.telefone,
                        Conversa.criada_em <= quando)
                .order_by(Conversa.id.desc())
                .first()
            )
            hora = hora_br(r.hora_prevista_chegada)
            registrar(self.db, conv, "hospede", f"Devo chegar por volta das {hora}", quando)
            registrar(self.db, conv, "bot", f"Anotado! Registrei sua chegada prevista para as {hora} do dia "
                      f"{r.check_in:%d/%m}.", quando + timedelta(minutes=1))

    def alertas_valor_pendente(self):
        for r in self.reservas:
            if r.valor_total is None:
                self.db.add(
                    Alerta(
                        hotel_id=self.hotel.id,
                        tipo="valor_pendente",
                        referencia=f"reserva:{r.id}",
                        texto=(
                            f"Reserva {r.canal.nome} de {r.check_in:%d/%m} a {r.check_out:%d/%m} "
                            f"(unidade {r.unidade.identificacao}) sem valor. Complete pelo CSV ou digitando."
                        ),
                        resolvido=False,
                        criado_em=min(r.criada_em, self.agora),
                    )
                )

    # ---- conversas antigas
    def gerar_conversas(self):
        hotel, db = self.hotel, self.db
        resolvidas = [
            ("Boa noite! Vocês aceitam cachorro pequeno?", "pet"),
            ("Que horas é o café da manhã?", "cafe"),
            ("Tem estacionamento aí?", "estacionamento"),
            ("Qual a senha do wifi?", "wifi"),
            ("Que horas posso fazer o check-in?", "horarios"),
            ("Qual o endereço de vocês?", "como_chegar"),
            ("Se eu cancelar, tenho reembolso?", "cancelamento"),
        ]
        escaladas = [
            ("Consegue um desconto para 3 noites?", "Pedido de desconto ou negociação",
             "Olá, aqui é da equipe! Para 3 noites com pagamento via Pix conseguimos 5% de desconto. Quer que eu reserve?"),
            ("O chuveiro do quarto está frio, quero reclamar", "Reclamação",
             "Sentimos muito! Já estamos indo verificar o chuveiro. Obrigado por avisar."),
            ("Vocês têm acomodação adaptada para cadeira de rodas?", "Pergunta sem resposta na base",
             "Olá! Temos uma unidade térrea com banheiro adaptado. Quer que eu verifique as datas?"),
        ]
        diretos = [r for r in self.reservas if r.hospede and r.hospede.consentimento_whatsapp_em and r.status == "concluida"]
        diretos.sort(key=lambda r: r.check_in, reverse=True)
        roteiros = [(p, c, None, None) for p, c in resolvidas] + [(p, None, m, e) for p, m, e in escaladas]
        for i, (pergunta, categoria, motivo, resposta_equipe) in enumerate(roteiros):
            reserva = diretos[i % len(diretos)]
            inicio = datetime.combine(
                reserva.check_in - timedelta(days=random.randint(1, 5)),
                time(random.randint(7, 23), random.randint(0, 59)),
            )
            if inicio > self.agora - timedelta(days=2):
                inicio = self.agora - timedelta(days=random.randint(2, 20))
            conv = Conversa(
                hotel_id=hotel.id,
                hospede_id=reserva.hospede.id,
                telefone=reserva.hospede.telefone,
                status="encerrada",
                motivo_escalonamento=motivo,
                criada_em=inicio,
                atualizada_em=inicio,
            )
            db.add(conv)
            db.flush()
            t = inicio
            msgs = [("hospede", pergunta)]
            if categoria:
                item = item_por_categoria(db, hotel.id, categoria)
                msgs.append(("bot", f"{textos.apresentacao(hotel)} {item.resposta}"))
                msgs.append(("hospede", "Obrigado!"))
                msgs.append(("bot", "Por nada! Se precisar de algo, é só chamar."))
            else:
                msgs.append(("bot", f"{textos.apresentacao(hotel)} {textos.escalonamento(hotel)}"))
                msgs.append(("equipe", resposta_equipe))
                msgs.append(("hospede", "Obrigado pelo retorno!"))
                db.add(
                    Alerta(
                        hotel_id=hotel.id,
                        tipo="escalonamento",
                        referencia=f"conversa:{conv.id}",
                        texto=f"{motivo}: \"{pergunta}\"",
                        resolvido=True,
                        criado_em=inicio,
                    )
                )
            for autor, texto in msgs:
                t += timedelta(minutes=random.randint(1, 3) if autor == "bot" else random.randint(2, 40))
                db.add(Mensagem(conversa_id=conv.id, autor=autor, texto=texto, criada_em=t))
            conv.atualizada_em = t

    # ---- avaliações
    def gerar_avaliacoes(self, quantidade=20):
        candidatas = [r for r in self.reservas if r.status == "concluida" and r.check_out >= self.hoje - timedelta(days=60)]
        candidatas.sort(key=lambda r: r.check_out)
        escolhidas = random.sample(candidatas, min(quantidade, len(candidatas)))
        escolhidas.sort(key=lambda r: r.check_out)
        elogios = [
            "Lugar lindo e muito limpo.", "Atendimento excelente, voltaremos!", "Café da manhã muito bom.",
            "Tudo conforme o anúncio.", None, None,
        ]
        criticas = [
            "Demoraram para responder no WhatsApp na noite da chegada.",
            "Tivemos dificuldade para achar a entrada quando chegamos à noite.",
            "O chuveiro estava fraco.",
        ]
        notas = [random.choices([5, 4, 3, 2, 1], [50, 30, 10, 6, 4])[0] for _ in escolhidas]
        if notas and min(notas) > 3:
            notas[-2] = 3  # garante pelo menos uma nota baixa recente
        baixas = []
        for r, nota in zip(escolhidas, notas):
            av = Avaliacao(
                reserva_id=r.id,
                nota=nota,
                comentario=random.choice(criticas) if nota <= 3 else random.choice(elogios),
                alerta_enviado=nota <= 3,
                convite_enviado=True,
            )
            self.db.add(av)
            if nota <= 3:
                baixas.append((r, nota))
        for i, (r, nota) in enumerate(baixas):
            self.db.add(
                Alerta(
                    hotel_id=self.hotel.id,
                    tipo="nota_baixa",
                    referencia=f"reserva:{r.id}",
                    texto=f"Nota {nota} de {r.hospede.nome if r.hospede else 'hóspede'} (saída em {r.check_out:%d/%m}).",
                    resolvido=i < len(baixas) - 1,  # só a mais recente fica aberta
                    criado_em=datetime.combine(r.check_out, time(15, 0)),
                )
            )


def escrever_exemplo_ics(reserva: Reserva, agora: datetime, arquivo: Path = ARQUIVO_ICS):
    """VEVENT de 3 noites na unidade 101 que sobrepõe uma reserva do seed."""
    inicio = reserva.check_in - timedelta(days=1)
    evento = EventoIcal(
        uid="exemplo-101-bloqueio@airbnb.com",
        inicio=inicio,
        fim=inicio + timedelta(days=3),
        resumo="Airbnb (Not available)",
    )
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(gerar_ics("Airbnb - Suíte 101", [evento], agora), encoding="utf-8", newline="")


def gerar(agora: datetime | None = None, arquivo_ics: Path | None = ARQUIVO_ICS, silencioso: bool = False):
    """Recria o banco inteiro. Devolve um resumo por hotel."""
    random.seed(42)
    banco.apagar_tabelas()
    banco.criar_tabelas()
    resumo = {}
    with banco.sessao() as db:
        if agora is None:
            relogio.zerar(db)
            agora = relogio.agora(db)
        else:
            relogio.definir(db, agora)
        telefones: set[str] = set()
        geradores = []
        for i, cfg in enumerate(HOTEIS):
            g = GeradorHotel(db, cfg, agora, i, telefones)
            g.criar_hotel()
            g.gerar_historico()
            slug = cfg["hotel"]["slug"]
            g.gerar_futuro(
                alvo=15,
                lotar_fds=(slug == "serra-verde"),
                reserva_na_unidade="101" if slug == "mare-alta" else None,
            )
            db.flush()
            g.alertas_valor_pendente()
            g.gerar_conversas()
            g.gerar_avaliacoes()
            g.gerar_jornadas()
            db.flush()
            geradores.append(g)
            hist_ini = agora.date() - timedelta(days=DIAS_HISTORICO)
            hist_fim = agora.date() - timedelta(days=1)
            estadias = [(0, r.check_in, r.check_out) for r in g.reservas]
            resumo[slug] = {
                "reservas": len(g.reservas),
                "futuras": g.contar_futuras(),
                "ocupacao_90d": ocupacao_estadias(estadias, len(g.unidades), hist_ini, hist_fim),
            }
        processar_ate(db, agora)  # entrega as mensagens da jornada que já venceram
        for g in geradores:
            g.simular_respostas_hora()
        db.commit()
        if arquivo_ics:
            escrever_exemplo_ics(geradores[0].reserva_exemplo_ics, agora, arquivo_ics)

    if not silencioso:
        print(f"Banco recriado. Hoje (relógio simulado): {agora:%d/%m/%Y %H:%M}")
        for slug, r in resumo.items():
            print(
                f"  {slug}: {r['reservas']} reservas ({r['futuras']} a partir de hoje), "
                f"ocupação dos últimos 90 dias = {r['ocupacao_90d']:.0%}"
            )
        if arquivo_ics:
            print(f"  iCal de exemplo: {arquivo_ics}")
    return resumo


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    gerar()

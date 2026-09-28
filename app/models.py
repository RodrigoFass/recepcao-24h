"""Modelo de dados (ver CLAUDE.md, seção "Modelo de dados").

Toda entidade ligada a um hotel tem hotel_id (direto ou pela reserva/conversa).
Horários do hotel ficam como texto "HH:MM"; datas e datas-hora em ISO.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Hotel(Base):
    __tablename__ = "hotel"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    cidade: Mapped[str] = mapped_column(String(80))
    endereco: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(30))
    whatsapp: Mapped[str | None] = mapped_column(String(30))
    checkin_hora: Mapped[str] = mapped_column(String(5))
    checkout_hora: Mapped[str] = mapped_column(String(5))
    early_checkin_permite: Mapped[bool] = mapped_column(Boolean, default=False)
    early_checkin_preco: Mapped[float | None] = mapped_column(Float)
    late_checkout_permite: Mapped[bool] = mapped_column(Boolean, default=False)
    late_checkout_preco: Mapped[float | None] = mapped_column(Float)
    modo_chegada: Mapped[str] = mapped_column(String(20))  # recepcao_24h / recepcao_horario / autoatendimento
    recepcao_inicio: Mapped[str | None] = mapped_column(String(5))
    recepcao_fim: Mapped[str | None] = mapped_column(String(5))
    link_fnrh: Mapped[str | None] = mapped_column(String(200))
    politicas: Mapped[dict] = mapped_column(JSON, default=dict)
    fuso: Mapped[str] = mapped_column(String(40), default="America/Sao_Paulo")

    tipos: Mapped[list["TipoAcomodacao"]] = relationship(back_populates="hotel", order_by="TipoAcomodacao.id")
    unidades: Mapped[list["Unidade"]] = relationship(back_populates="hotel", order_by="Unidade.id")
    canais: Mapped[list["Canal"]] = relationship(back_populates="hotel", order_by="Canal.id")

    def politica(self, chave, padrao=None):
        return (self.politicas or {}).get(chave, padrao)


class TipoAcomodacao(Base):
    __tablename__ = "tipo_acomodacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    capacidade: Mapped[int] = mapped_column(Integer)
    tarifa_base: Mapped[float] = mapped_column(Float)
    descricao: Mapped[str | None] = mapped_column(Text)

    hotel: Mapped[Hotel] = relationship(back_populates="tipos")


class Unidade(Base):
    __tablename__ = "unidade"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    tipo_id: Mapped[int] = mapped_column(ForeignKey("tipo_acomodacao.id"))
    identificacao: Mapped[str] = mapped_column(String(20))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    hotel: Mapped[Hotel] = relationship(back_populates="unidades")
    tipo: Mapped[TipoAcomodacao] = relationship()


class Canal(Base):
    __tablename__ = "canal"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # airbnb / booking / whatsapp / telefone / balcao
    comissao_pct: Mapped[float] = mapped_column(Float, default=0)
    anuncio_por: Mapped[str] = mapped_column(String(10), default="unidade")  # unidade / tipo

    hotel: Mapped[Hotel] = relationship(back_populates="canais")

    @property
    def nome(self):
        return NOMES_CANAIS.get(self.tipo, self.tipo)

    @property
    def direto(self):
        return not self.comissao_pct


NOMES_CANAIS = {
    "airbnb": "Airbnb",
    "booking": "Booking.com",
    "whatsapp": "WhatsApp",
    "telefone": "Telefone",
    "balcao": "Balcão",
}


class CalendarioExterno(Base):
    __tablename__ = "calendario_externo"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"))
    canal_id: Mapped[int] = mapped_column(ForeignKey("canal.id"))
    ical_url: Mapped[str] = mapped_column(String(300))
    ultima_sincronizacao: Mapped[datetime | None] = mapped_column(DateTime)

    unidade: Mapped[Unidade] = relationship()
    canal: Mapped[Canal] = relationship()


class Hospede(Base):
    """Não guarda documento: ele fica na FNRH Digital."""

    __tablename__ = "hospede"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    telefone: Mapped[str | None] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    consentimento_whatsapp_em: Mapped[datetime | None] = mapped_column(DateTime)
    idioma: Mapped[str] = mapped_column(String(5), default="pt")


class Reserva(Base):
    __tablename__ = "reserva"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"), index=True)
    hospede_id: Mapped[int | None] = mapped_column(ForeignKey("hospede.id"))
    canal_id: Mapped[int] = mapped_column(ForeignKey("canal.id"))
    check_in: Mapped[date] = mapped_column(Date, index=True)
    check_out: Mapped[date] = mapped_column(Date, index=True)
    num_hospedes: Mapped[int] = mapped_column(Integer, default=2)
    valor_total: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="confirmada")  # confirmada / cancelada / concluida
    hora_prevista_chegada: Mapped[str | None] = mapped_column(String(5))
    origem: Mapped[str] = mapped_column(String(8), default="manual")  # manual / ical / csv / seed
    codigo_externo: Mapped[str | None] = mapped_column(String(120))
    criada_em: Mapped[datetime] = mapped_column(DateTime)

    unidade: Mapped[Unidade] = relationship()
    hospede: Mapped[Hospede | None] = relationship()
    canal: Mapped[Canal] = relationship()
    mensagens_agendadas: Mapped[list["MensagemAgendada"]] = relationship(
        back_populates="reserva", order_by="MensagemAgendada.id"
    )
    avaliacao: Mapped["Avaliacao | None"] = relationship(back_populates="reserva", uselist=False)

    @property
    def noites(self):
        return (self.check_out - self.check_in).days


class ItemBaseConhecimento(Base):
    __tablename__ = "item_base_conhecimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    categoria: Mapped[str] = mapped_column(String(40))
    pergunta: Mapped[str] = mapped_column(String(200))
    palavras_chave: Mapped[str] = mapped_column(Text)  # separadas por vírgula
    resposta: Mapped[str] = mapped_column(Text)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime)


class Conversa(Base):
    __tablename__ = "conversa"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    hospede_id: Mapped[int | None] = mapped_column(ForeignKey("hospede.id"))
    telefone: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(10), default="bot")  # bot / humano / encerrada
    motivo_escalonamento: Mapped[str | None] = mapped_column(String(200))
    criada_em: Mapped[datetime] = mapped_column(DateTime)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime)

    hospede: Mapped[Hospede | None] = relationship()
    mensagens: Mapped[list["Mensagem"]] = relationship(
        back_populates="conversa", order_by="(Mensagem.criada_em, Mensagem.id)"
    )


class Mensagem(Base):
    __tablename__ = "mensagem"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversa.id"), index=True)
    autor: Mapped[str] = mapped_column(String(10))  # hospede / bot / equipe / sistema
    texto: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime)

    conversa: Mapped[Conversa] = relationship(back_populates="mensagens")


class MensagemAgendada(Base):
    __tablename__ = "mensagem_agendada"

    id: Mapped[int] = mapped_column(primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id"), index=True)
    etapa: Mapped[str] = mapped_column(String(30))
    enviar_em: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(15), default="pendente")
    # pendente / enviada / reenviada / sem_resposta / cancelada
    texto: Mapped[str] = mapped_column(Text)
    meio: Mapped[str] = mapped_column(String(12), default="whatsapp")  # whatsapp / ota_manual

    reserva: Mapped[Reserva] = relationship(back_populates="mensagens_agendadas")


class Avaliacao(Base):
    __tablename__ = "avaliacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id"), unique=True)
    nota: Mapped[int] = mapped_column(Integer)
    comentario: Mapped[str | None] = mapped_column(Text)
    alerta_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    convite_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    reserva: Mapped[Reserva] = relationship(back_populates="avaliacao")


class Alerta(Base):
    __tablename__ = "alerta"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    # conflito / sem_resposta / nota_baixa / escalonamento / valor_pendente
    referencia: Mapped[str | None] = mapped_column(String(60))  # ex.: "reserva:12", "conversa:3"
    texto: Mapped[str] = mapped_column(Text)
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime)


class UsuarioEquipe(Base):
    __tablename__ = "usuario_equipe"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    papel: Mapped[str] = mapped_column(String(40))
    contato_alerta: Mapped[str | None] = mapped_column(String(60))


class Configuracao(Base):
    """Chave/valor global (ex.: deslocamento do relógio simulado)."""

    __tablename__ = "configuracao"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)

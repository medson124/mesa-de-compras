"""Banco de dados: compras registradas e configuração de taxas."""
import json
import os
import time

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mesa.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


class Compra(Base):
    __tablename__ = "compras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    cod = Column(String(80), default="")
    forn = Column(String(120), default="")
    qtd = Column(Integer, default=1)
    tab = Column(Float, nullable=False)          # preço de tabela do fornecedor
    desc = Column(Float, default=0)              # desconto em %
    venda = Column(Float, nullable=True)         # preço de venda de referência no marketplace
    criado = Column(Float, default=lambda: time.time() * 1000)

    def to_dict(self):
        return {
            "id": self.id, "nome": self.nome, "cod": self.cod or "", "forn": self.forn or "",
            "qtd": self.qtd or 1, "tab": self.tab, "desc": self.desc or 0,
            "venda": self.venda, "criado": self.criado,
        }


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    dados = Column(Text, nullable=False)

    def to_dict(self):
        return json.loads(self.dados)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

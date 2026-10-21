import os

os.environ["DATABASE_URL"] = "sqlite:///./test_mesa.db"
os.environ["ADMIN_USER"] = "admin"
os.environ["ADMIN_PASSWORD"] = "segredo"
os.environ["COOKIE_SECURE"] = "0"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ia  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def cli():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def entrar(c):
    r = c.post("/login", data={"usuario": "admin", "senha": "segredo"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_sem_login_bloqueia(cli):
    assert cli.get("/api/compras").status_code == 401
    assert cli.get("/", follow_redirects=False).headers["location"] == "/login"


def test_senha_errada(cli):
    r = cli.post("/login", data={"usuario": "admin", "senha": "x"}, follow_redirects=False)
    assert r.headers["location"] == "/login?erro=1"


def test_compras_crud(cli):
    entrar(cli)
    r = cli.post("/api/compras", json={"nome": "Escova progressiva", "tab": 12.0, "desc": 25, "qtd": 10, "venda": 18.99})
    assert r.status_code == 201
    cid = r.json()["id"]
    lista = cli.get("/api/compras").json()
    assert len(lista) == 1 and lista[0]["nome"] == "Escova progressiva" and lista[0]["desc"] == 25
    assert cli.delete(f"/api/compras/{cid}").status_code == 204
    assert cli.get("/api/compras").json() == []


def test_compra_invalida(cli):
    entrar(cli)
    assert cli.post("/api/compras", json={"nome": "", "tab": 0}).status_code == 422


def test_config(cli):
    entrar(cli)
    assert cli.get("/api/config").json() is None
    cfg = {"div": 0.7, "alvo": 10, "mkts": [{"k": "tiktok", "ativo": True, "tiers": [{"ate": 999999, "pct": 14, "fixo": 4}]}]}
    assert cli.put("/api/config", json=cfg).status_code == 200
    assert cli.get("/api/config").json() == cfg
    assert cli.put("/api/config", json={"x": 1}).status_code == 400


def test_ia_sem_chave(cli):
    entrar(cli)
    assert cli.get("/api/status").json() == {"ia": False}
    r = cli.post("/api/ia/buscar", json={"termo": "escova progressiva"})
    assert r.status_code == 503


def test_ia_buscar_simulada(cli, monkeypatch):
    entrar(cli)
    monkeypatch.setattr(ia, "buscar", lambda termo: {"ml": [29.9], "shopee": [27.9], "tiktok": []})
    r = cli.post("/api/ia/buscar", json={"termo": "touca de cetim"})
    assert r.json() == {"ml": [29.9], "shopee": [27.9], "tiktok": []}


def test_ia_ler_simulada(cli, monkeypatch):
    entrar(cli)
    monkeypatch.setattr(ia, "ler_precos", lambda t, n, imgs: {"ml": [1.0], "shopee": [], "tiktok": [], "outros": [len(imgs)]})
    r = cli.post("/api/ia/ler", data={"texto": "ML 29,90", "nome": "x"},
                 files=[("imagens", ("a.png", b"\x89PNG", "image/png"))])
    assert r.json()["outros"] == [1]


def test_json_e_precos():
    assert ia._json('texto {"ml":[1]} fim') == {"ml": [1]}
    assert ia._json('```json\n{"a":2}\n```') == {"a": 2}
    assert ia._precos(["R$ 29,90", "1.299,00", "29.90", 0, "x", 12]) == [29.9, 1299.0, 29.9, 12.0]

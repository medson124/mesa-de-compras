"""Mesa de Compras — API e telas."""
import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import ia
from .db import Compra, Config, get_session, init_db

STATIC = Path(__file__).parent / "static"
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave")
MAX_IMG = 10 * 1024 * 1024

@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Mesa de Compras", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax",
                   https_only=os.getenv("COOKIE_SECURE", "1") == "1", max_age=60 * 60 * 24 * 30)


# ---------- login ----------
def logado(request: Request):
    if not request.session.get("user"):
        raise HTTPException(401, "Faça login")
    return request.session["user"]


@app.get("/login")
def tela_login():
    return FileResponse(STATIC / "login.html")


@app.post("/login")
def fazer_login(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    ok = bool(ADMIN_PASSWORD) and hmac.compare_digest(usuario, ADMIN_USER) and hmac.compare_digest(senha, ADMIN_PASSWORD)
    if not ok:
        return RedirectResponse("/login?erro=1", status_code=303)
    request.session["user"] = usuario
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def sair(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def inicio(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status(_=Depends(logado)):
    return {"ia": ia.disponivel()}


# ---------- compras ----------
class CompraIn(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    cod: str = ""
    forn: str = ""
    qtd: int = Field(default=1, ge=1)
    tab: float = Field(gt=0)
    desc: float = Field(default=0, ge=0, lt=100)
    venda: float | None = Field(default=None, gt=0)


@app.get("/api/compras")
def listar(_=Depends(logado), s: Session = Depends(get_session)):
    return [c.to_dict() for c in s.query(Compra).order_by(Compra.criado.desc()).all()]


@app.post("/api/compras", status_code=201)
def criar(dados: CompraIn, _=Depends(logado), s: Session = Depends(get_session)):
    c = Compra(**dados.model_dump())
    s.add(c)
    s.commit()
    return c.to_dict()


@app.delete("/api/compras/{cid}", status_code=204)
def excluir(cid: int, _=Depends(logado), s: Session = Depends(get_session)):
    c = s.get(Compra, cid)
    if not c:
        raise HTTPException(404, "Compra não encontrada")
    s.delete(c)
    s.commit()


# ---------- taxas ----------
@app.get("/api/config")
def ler_config(_=Depends(logado), s: Session = Depends(get_session)):
    c = s.get(Config, 1)
    return c.to_dict() if c else None


@app.put("/api/config")
async def salvar_config(request: Request, _=Depends(logado), s: Session = Depends(get_session)):
    dados = await request.json()
    if not isinstance(dados, dict) or not isinstance(dados.get("mkts"), list):
        raise HTTPException(400, "Configuração inválida")
    c = s.get(Config, 1) or Config(id=1, dados="{}")
    c.dados = json.dumps(dados)
    s.merge(c)
    s.commit()
    return dados


# ---------- IA ----------
def _erro_ia(e: Exception):
    if isinstance(e, ia.IAIndisponivel):
        return JSONResponse({"erro": "A IA não está configurada no servidor."}, status_code=503)
    return JSONResponse({"erro": "A IA não respondeu agora. Tente de novo."}, status_code=502)


async def _ler_img(f: UploadFile | None):
    if not f:
        return None
    dados = await f.read()
    if len(dados) > MAX_IMG:
        raise HTTPException(413, "Imagem maior que 10 MB")
    return dados, (f.content_type or "image/jpeg")


@app.post("/api/ia/identificar")
async def ia_identificar(foto: UploadFile | None = File(None), nome: str = Form(""), cod: str = Form(""), _=Depends(logado)):
    img = await _ler_img(foto)
    try:
        return ia.identificar(img[0] if img else None, img[1] if img else "", nome, cod)
    except Exception as e:  # noqa: BLE001
        return _erro_ia(e)


class BuscaIn(BaseModel):
    termo: str = Field(min_length=2, max_length=120)


@app.post("/api/ia/buscar")
def ia_buscar(dados: BuscaIn, _=Depends(logado)):
    try:
        return ia.buscar(dados.termo)
    except Exception as e:  # noqa: BLE001
        return _erro_ia(e)


@app.post("/api/ia/ler")
async def ia_ler(texto: str = Form(""), nome: str = Form(""), imagens: list[UploadFile] = File(default=[]), _=Depends(logado)):
    imgs = [i for i in [await _ler_img(f) for f in imagens[:5]] if i]
    if not texto.strip() and not imgs:
        raise HTTPException(400, "Cole algum texto ou envie prints")
    try:
        return ia.ler_precos(texto, nome, imgs)
    except Exception as e:  # noqa: BLE001
        return _erro_ia(e)

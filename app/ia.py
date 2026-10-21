"""Funções de IA (Anthropic): identificar produto pela foto, buscar preços na web e ler preços colados."""
import base64
import json
import os
import re

MODELO = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MODELO_RAPIDO = os.getenv("ANTHROPIC_MODEL_RAPIDO", "claude-haiku-5-5")
DOMINIOS = ["mercadolivre.com.br", "shopee.com.br", "tiktok.com"]


class IAIndisponivel(Exception):
    pass


def disponivel() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _cliente():
    if not disponivel():
        raise IAIndisponivel("ANTHROPIC_API_KEY não configurada")
    import anthropic
    return anthropic.Anthropic()


def _json(texto: str):
    """Extrai o primeiro objeto JSON de uma resposta."""
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.S)
    if m:
        texto = m.group(1)
    else:
        ini, fim = texto.find("{"), texto.rfind("}")
        if ini == -1 or fim == -1:
            raise ValueError("resposta sem JSON")
        texto = texto[ini:fim + 1]
    return json.loads(texto)


def _texto(resp) -> str:
    return "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _imagem(dados: bytes, tipo: str):
    return {"type": "image", "source": {"type": "base64", "media_type": tipo or "image/jpeg",
                                        "data": base64.b64encode(dados).decode()}}


def _precos(lista):
    out = []
    for v in lista or []:
        try:
            if isinstance(v, str):
                v = v.replace("R$", "").strip()
                if "," in v:
                    v = v.replace(".", "").replace(",", ".")
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0:
            out.append(round(f, 2))
    return out[:20]


def identificar(foto: bytes | None, tipo: str, nome: str, cod: str) -> dict:
    """Devolve {"nome", "busca"} para pesquisar o produto."""
    if not foto:
        termo = nome or cod
        return {"nome": nome, "busca": termo}
    resp = _cliente().messages.create(
        model=MODELO, max_tokens=300,
        messages=[{"role": "user", "content": [
            _imagem(foto, tipo),
            {"type": "text", "text": (
                "Identifique o produto da foto para pesquisar o preço dele em marketplaces brasileiros.\n"
                f'Dados digitados (podem estar vazios): nome="{nome}", código="{cod}".\n'
                'Responda só com JSON: {"nome": "nome comercial curto em português", '
                '"busca": "termo de busca de 2 a 6 palavras"}')},
        ]}],
    )
    d = _json(_texto(resp))
    return {"nome": str(d.get("nome") or nome), "busca": str(d.get("busca") or nome or cod)}


def buscar(termo: str) -> dict:
    """Pesquisa na web os preços praticados no Mercado Livre, Shopee e TikTok Shop."""
    resp = _cliente().messages.create(
        model=MODELO, max_tokens=2000,
        tools=[{
            "type": "web_search_20250305", "name": "web_search", "max_uses": 6,
            "allowed_domains": DOMINIOS,
            "user_location": {"type": "approximate", "country": "BR", "timezone": "America/Sao_Paulo"},
        }],
        messages=[{"role": "user", "content": (
            f'Pesquise o preço de venda atual do produto "{termo}" no Mercado Livre, na Shopee e no TikTok Shop (Brasil).\n'
            "Considere só anúncios do MESMO produto (mesmo tipo e mesma quantidade por unidade/kit). "
            "Use o preço à vista, ignore parcelas e preços riscados.\n"
            'Ao final, responda só com JSON: {"ml":[números],"shopee":[números],"tiktok":[números]} '
            "com até 10 preços por marketplace; lista vazia quando não achar.")}],
    )
    d = _json(_texto(resp))
    return {k: _precos(d.get(k)) for k in ("ml", "shopee", "tiktok")}


def ler_precos(texto: str, nome: str, imagens: list[tuple[bytes, str]]) -> dict:
    """Lê preços colados (texto, links ou prints) e separa por marketplace."""
    conteudo = [_imagem(b, t) for b, t in imagens[:5]]
    conteudo.append({"type": "text", "text": (
        "O usuário colou preços de venda de um produto encontrados em marketplaces brasileiros"
        f"{' (e prints de anúncios ou etiquetas)' if imagens else ''}. Produto: \"{nome}\".\n"
        'Separe os preços à vista em reais. "ML", "mercado livre", "meli" e links mercadolivre.com.br = ml; '
        '"shopee" = shopee; "tiktok", "tt" = tiktok; Kwai, Shein, Amazon, Magalu ou sem marketplace = outros. '
        "Ignore parcelas e preços riscados.\n"
        'Responda só com JSON: {"ml":[números],"shopee":[números],"tiktok":[números],"outros":[números]}.\n\n'
        f"TEXTO:\n{texto[:8000]}")})
    resp = _cliente().messages.create(
        model=MODELO if imagens else MODELO_RAPIDO, max_tokens=800,
        messages=[{"role": "user", "content": conteudo}],
    )
    d = _json(_texto(resp))
    return {k: _precos(d.get(k)) for k in ("ml", "shopee", "tiktok", "outros")}

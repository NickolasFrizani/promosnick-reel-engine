# Wrapper HTTP pro motor — o n8n chama POST /gerar com os dados do produto.
from fastapi import FastAPI
from pydantic import BaseModel
import gerar_reel as engine

app = FastAPI(title="PromosNick Reel Engine")

class Produto(BaseModel):
    nome: str
    img: str
    slug: str
    de: str = ""
    por: str = ""
    pct: str = ""
    link: str = ""

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/gerar")
def gerar(p: Produto):
    try:
        res = engine.gerar_reel(p.nome, p.img, p.slug, p.de, p.por, p.pct, p.link)
        return {"ok": True, **res}
    except Exception as e:
        return {"ok": False, "erro": str(e)[:500]}

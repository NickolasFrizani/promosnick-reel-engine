import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import gerar_reel as engine

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/gerar")
async def gerar(req: Request):
    d = await req.json()
    try:
        res = engine.gerar_reel(
            d.get("nome", ""),
            d.get("img", ""),
            d.get("slug", "reel"),
            d.get("de", ""),
            d.get("por", ""),
            d.get("pct", ""),
            d.get("link", ""),
        )
        path = res["path"]
        return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "erro": str(e)})

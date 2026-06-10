# ---------- retry automatico do Veo (filtro intermitente) ----------
if "_gerar_video_original" not in globals():
    _gerar_video_original = gerar_video

def gerar_video(frame, slug, client):
    for tentativa in range(1, 4):
        try:
            return _gerar_video_original(frame, slug, client)
        except Exception as e:
            eh_filtro = ("falhou" in str(e)) or ("filtered" in str(e).lower())
            if tentativa == 3 or not eh_filtro:
                raise
            log(f"[{slug}] Veo filtrou (tentativa {tentativa}/3), repetindo...")
#
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

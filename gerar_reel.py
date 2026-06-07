#!/usr/bin/env python3
"""
Motor de Reel UGC ACHADINHOS — v2 (produção)
============================================
1 produto -> Reel 9:16 pronto e LEGENDADO, opcionalmente já enviado pro Drive.

Pipeline: foto -> Flash-Image (cena UGC) -> Veo 3.1 Lite (vídeo) -> copy neuromarketing (Gemini)
          -> ElevenLabs (voz clonada) -> ffmpeg (boomerang + legenda + voz) -> [upload Drive]

VARIÁVEIS DE AMBIENTE:
  GEMINI_API_KEY        (obrigatório)  chave Gemini (Veo + Flash-Image + copy)
  ELEVENLABS_API_KEY    (obrigatório)  chave ElevenLabs
  ELEVEN_VOICE_ID       clone (default pJfNXyrcKXCSt52XxsuN = Nickolas profissional)
  VEO_MODEL             default veo-3.1-lite-generate-preview
  HANDLE                default @promos.nick
  CTA_TEXT              default "ENTRA NO GRUPO  ->  LINK NA BIO"
  OUTDIR                default /data
  DRIVE_FOLDER_ID       (opcional) se setado + GOOGLE_SA_JSON, faz upload no Drive
  GOOGLE_SA_JSON        (opcional) caminho do JSON da conta de serviço Google

USO CLI:
  python3 gerar_reel.py --nome "Creatina Growth 250g" --img "https://...webp" \
      --de "R$62,90" --por "R$39,90" --pct "36%" --link "https://..." --slug creatina
"""
import os, sys, time, json, argparse, subprocess, base64, requests
from PIL import Image, ImageFilter
from google import genai
from google.genai import types

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID   = os.environ.get("ELEVEN_VOICE_ID", "pJfNXyrcKXCSt52XxsuN")
VEO_MODEL  = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-preview")
HANDLE     = os.environ.get("HANDLE", "@promos.nick")
CTA_TEXT   = os.environ.get("CTA_TEXT", "ENTRA NO GRUPO  \u2192  LINK NA BIO")
OUTDIR     = os.environ.get("OUTDIR", "/data")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
GOOGLE_SA_JSON  = os.environ.get("GOOGLE_SA_JSON")

def log(*a): print(*a, flush=True)
def dur(path):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nk=1:nw=1", path]).decode().strip())

# ---------- copy de neuromarketing (Gemini) ----------
def gerar_copy(nome, de, por, pct):
    prompt = f"""Você é copywriter de resposta direta (Kennedy, Hormozi, Brunson) + neuromarketing. Escreva o ROTEIRO DE NARRAÇÃO de um Reel de uma OFERTA de afiliado, em português do Brasil.
REGRAS: máx 38 palavras (~14s); estrutura gancho -> ancoragem "de X por Y" -> 1 benefício concreto -> CTA único pra clicar no link; escreva os NÚMEROS POR EXTENSO (ex.: "trinta e nove e noventa"); tom confiante e direto; sem emojis, sem hashtags, sem aspas; devolva SÓ o texto falado.
PRODUTO: {nome}
PREÇO CHEIO: {de}
PREÇO PROMOCIONAL: {por} (no Pix)
DESCONTO: {pct}"""
    try:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
                          json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if t: return " ".join(t.split())
    except Exception as e:
        log("  (copy via Gemini falhou, template):", repr(e)[:120])
    return f"Para tudo! {nome.split('-')[0].strip()} de {de} por só {por} no Pix, {pct} off. Corre no link antes que suma!"

# ---------- cena UGC (Flash-Image) + quadro 9:16 ----------
def gerar_cena(img_url, slug, client):
    img = requests.get(img_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).content
    prompt = ("Foto autêntica estilo UGC para redes sociais. Use EXATAMENTE o mesmo produto da imagem de "
              "referência (mesma embalagem, rótulo, cores e marca, sem alterar). Produto segurado pela mão de "
              "uma pessoa, ambiente doméstico real e bem iluminado, luz natural, estética de foto de celular, "
              "enquadramento casual, fundo levemente desfocado, aparência espontânea. Sem nenhum texto na imagem.")
    payload = {"contents": [{"parts": [{"text": prompt},
               {"inline_data": {"mime_type": "image/webp", "data": base64.b64encode(img).decode()}}]}],
               "generationConfig": {"responseModalities": ["IMAGE"]}}
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={GEMINI_KEY}",
                      json=payload, timeout=120)
    cena = f"{OUTDIR}/cena_{slug}.png"
    for part in r.json()["candidates"][0]["content"]["parts"]:
        inl = part.get("inlineData") or part.get("inline_data")
        if inl and inl.get("data"):
            open(cena, "wb").write(base64.b64decode(inl["data"])); break
    else:
        raise RuntimeError("Flash-Image não retornou imagem")
    orig = Image.open(cena).convert("RGB"); W, H = 1080, 1920
    bg = orig.resize((W, W)).resize((W, H)).filter(ImageFilter.GaussianBlur(45))
    bg.paste(orig.resize((W, W)), (0, (H - W)//2))
    frame = f"/tmp/frame_{slug}.png"; bg.save(frame)
    return frame

# ---------- vídeo (Veo 3.1 Lite) — áudio do Veo é descartado na montagem ----------
def gerar_video(frame, slug, client):
    op = client.models.generate_videos(model=VEO_MODEL,
        prompt=("A person's hand holds the product and slowly turns it to show it; subtle handheld camera "
                "motion; bright modern home; soft natural light; authentic UGC; no speech, no on-screen text."),
        image=types.Image(image_bytes=open(frame, "rb").read(), mime_type="image/png"),
        config=types.GenerateVideosConfig(aspect_ratio="9:16", number_of_videos=1))
    for _ in range(30):
        if getattr(op, "done", False): break
        time.sleep(11); op = client.operations.get(op)
    resp = getattr(op, "response", None) or getattr(op, "result", None)
    gv = getattr(resp, "generated_videos", None)
    if not gv: raise RuntimeError(f"Veo falhou: {str(resp)[:200]}")
    client.files.download(file=gv[0].video)
    vid = f"/tmp/video_{slug}.mp4"; gv[0].video.save(vid)
    return vid

# ---------- voz (ElevenLabs) ----------
def gerar_voz(texto, slug):
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        headers={"xi-api-key": ELEVEN_KEY, "content-type": "application/json"},
        json={"text": texto, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.4, "similarity_boost": 0.85, "style": 0.4, "use_speaker_boost": True}},
        timeout=120)
    r.raise_for_status()
    mp3 = f"/tmp/voz_{slug}.mp3"; open(mp3, "wb").write(r.content)
    return mp3

# ---------- legenda ASS (handle + caption sincronizada + CTA) ----------
ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Handle,DejaVu Sans,34,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,1,8,40,40,55,1
Style: Cap,DejaVu Sans,52,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,1,2,50,50,360,1
Style: CTA,DejaVu Sans,42,&H00FFFFFF,&H000000FF,&H0025D366,&H0025D366,1,0,0,0,100,100,0,0,3,6,0,2,40,40,110,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
def _tc(sec):
    cs = int(round(sec*100)); h=cs//360000; cs%=360000; m=cs//6000; cs%=6000; s=cs//100; c=cs%100
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"
def build_ass(narr, D, slug):
    words = narr.replace("\u2014", " ").split(); out=[]; cur=[]
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w.endswith((".","!","?")):
            out.append(" ".join(cur)); cur=[]
    if cur: out.append(" ".join(cur))
    lines = [l.rstrip(",").strip() for l in out if l.strip()]
    tw = sum(len(l.split()) for l in lines) or 1; t0 = 0.15; span = max(0.1, D-0.35-0.15)
    ev = [f"Dialogue: 0,{_tc(0)},{_tc(D)},Handle,,0,0,0,,{HANDLE}",
          f"Dialogue: 0,{_tc(0)},{_tc(D)},CTA,,0,0,0,,{CTA_TEXT}"]
    acc = t0
    for l in lines:
        d = span*(len(l.split())/tw); ev.append(f"Dialogue: 1,{_tc(acc)},{_tc(acc+d)},Cap,,0,0,0,,{l.upper()}"); acc += d
    af = f"/tmp/cap_{slug}.ass"; open(af, "w", encoding="utf-8").write(ASS_HEAD + "\n".join(ev) + "\n")
    return af

# ---------- montagem: boomerang + legenda + voz (1 passada ffmpeg) ----------
def montar(video, voz, ass_file, slug):
    D = dur(voz); out = f"{OUTDIR}/reel_{slug}_final.mp4"; fade = max(0.0, D-0.4)
    fc = (f"[0:v]split=2[a][b];[b]reverse[r];[a][r]concat=n=2:v=1,setpts=PTS-STARTPTS,ass={ass_file}[v];"
          f"[1:a]afade=t=out:st={fade:.2f}:d=0.4[aud]")
    subprocess.run(["ffmpeg","-y","-i",video,"-i",voz,"-filter_complex",fc,"-map","[v]","-map","[aud]",
        "-c:v","libx264","-pix_fmt","yuv420p","-crf","21","-c:a","aac","-b:a","160k","-shortest",
        "-movflags","+faststart", out], check=True, stderr=subprocess.DEVNULL)
    return out

# ---------- upload Drive (conta de serviço) ----------
def upload_drive(filepath):
    if not (DRIVE_FOLDER_ID and GOOGLE_SA_JSON): return None
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SA_JSON, scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds)
    meta = {"name": os.path.basename(filepath), "parents": [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype="video/mp4", resumable=True)
    f = svc.files().create(body=meta, media_body=media, fields="id,webViewLink",
                           supportsAllDrives=True).execute()
    return f.get("webViewLink")

# ---------- orquestração ----------
def gerar_reel(nome, img, slug, de="", por="", pct="", link=""):
    os.makedirs(OUTDIR, exist_ok=True)
    client = genai.Client(api_key=GEMINI_KEY)
    log(f"[{slug}] copy…");   copy = gerar_copy(nome, de, por, pct); log("   →", copy)
    log(f"[{slug}] cena…");   frame = gerar_cena(img, slug, client)
    log(f"[{slug}] vídeo {VEO_MODEL}…"); video = gerar_video(frame, slug, client)
    log(f"[{slug}] voz…");    voz = gerar_voz(copy, slug)
    D = dur(voz); af = build_ass(copy, D, slug)
    log(f"[{slug}] montando + legenda…"); final = montar(video, voz, af, slug)
    drive = upload_drive(final)
    res = {"path": final, "drive_url": drive, "copy": copy, "dur": round(D, 1)}
    log("RESULT=" + json.dumps(res, ensure_ascii=False))
    return res

def main():
    ap = argparse.ArgumentParser()
    for a in ["nome", "img", "de", "por", "pct", "link", "slug"]:
        ap.add_argument(f"--{a}", default="", required=(a in ("nome", "img", "slug")))
    a = ap.parse_args()
    assert GEMINI_KEY and ELEVEN_KEY, "Defina GEMINI_API_KEY e ELEVENLABS_API_KEY"
    gerar_reel(a.nome, a.img, a.slug, a.de, a.por, a.pct, a.link)

if __name__ == "__main__":
    main()

import os
import requests
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from yt_dlp import YoutubeDL
from urllib.parse import urlparse, parse_qs

# Playwright
from playwright.async_api import async_playwright

app = FastAPI()

# Static + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/favicon.ico")
def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/", response_class=HTMLResponse)
def root():
    return templates.TemplateResponse("index.html", {"request": {}})


# ----------------- Hybrid Extractor (YouTube = Playwright, Others = yt-dlp) -----------------
@app.websocket("/ws/extract")
async def websocket_extract(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            url = await websocket.receive_text()
            await websocket.send_json({"status": "progress", "message": "🔍 Extracting info..."})

            try:
                formats = []
                title, thumbnail = "", ""

                # Case 1: YouTube → Playwright
                if "youtube.com" in url or "youtu.be" in url:
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                        page = await browser.new_page()
                        await page.goto(url, wait_until="domcontentloaded")

                        title = await page.title()
                        video_url = await page.evaluate("""() => {
                            const vid = document.querySelector("video");
                            return vid ? vid.src : "";
                        }""")

                        await browser.close()

                        if video_url:
                            formats.append({
                                "format_id": "yt_playwright",
                                "type": "video+audio",
                                "resolution": "best",
                                "ext": "mp4",
                                "direct_url": video_url
                            })

                # Case 2: Other platforms → yt-dlp
                else:
                    ydl_opts = {"quiet": True, "skip_download": True, "format": "bestvideo+bestaudio/best"}
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                    title = info.get("title", "Untitled")
                    thumbnail = info.get("thumbnail", "")

                    seen = set()
                    for f in info.get("formats", []):
                        url_f = f.get("url")
                        if not url_f:
                            continue
                        vcodec, acodec, height = f.get("vcodec"), f.get("acodec"), f.get("height")

                        if vcodec != "none" and acodec != "none":
                            label = f"{height}p" if height else "unknown"
                            formats.append({
                                "format_id": f["format_id"],
                                "type": "video+audio",
                                "resolution": label,
                                "ext": f.get("ext"),
                                "direct_url": url_f
                            })
                        elif vcodec != "none" and height and height not in seen:
                            formats.append({
                                "format_id": f["format_id"],
                                "type": "video",
                                "resolution": f"{height}p",
                                "ext": f.get("ext"),
                                "direct_url": url_f
                            })
                            seen.add(height)
                        elif vcodec == "none" and acodec != "none":
                            formats.append({
                                "format_id": f["format_id"],
                                "type": "audio",
                                "bitrate": f.get("abr"),
                                "ext": f.get("ext"),
                                "direct_url": url_f
                            })

                # Final response
                result = {"title": title, "thumbnail": thumbnail, "formats": formats}
                await websocket.send_json(result)
                await websocket.send_json({"status": "done", "message": "🎯 Done! Direct links ready."})

            except Exception as e:
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        print("Client disconnected")


# ----------------- Download Endpoint -----------------
@app.get("/download")
def download(
    video_url: str = Query(...),
    title: str = Query(default="video"),
    resolution: str = Query(default=""),
    type_: str = Query(default="")
):
    """Progressive streams → force download | Adaptive streams → redirect"""
    if type_ == "video+audio":
        r = requests.get(video_url, stream=True)
        qs = parse_qs(urlparse(video_url).query)
        mime = qs.get("mime", ["video/mp4"])[0]
        ext = mime.split("/")[-1] if "/" in mime else "mp4"

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        filename_parts = [safe_title]
        if resolution:
            filename_parts.append(resolution)
        if type_:
            filename_parts.append(type_)
        filename = "_".join(filename_parts) + f".{ext}"

        return StreamingResponse(
            r.iter_content(chunk_size=1024*1024),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        return RedirectResponse(url=video_url)

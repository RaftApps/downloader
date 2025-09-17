import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from yt_dlp import YoutubeDL
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/favicon.ico")
def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/", response_class=HTMLResponse)
def root():
    return templates.TemplateResponse("index.html", {"request": {}})


# ----------------- Hybrid WebSocket Extractor -----------------
@app.websocket("/ws/extract")
async def websocket_extract(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            url = await websocket.receive_text()
            await websocket.send_json({"status": "progress", "message": "🔍 Extracting info..."})

            try:
                formats = []
                title = ""
                thumbnail = ""

                if "youtube.com" in url or "youtu.be" in url:
                    # ------------------ YouTube via Playwright ------------------
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()

                        # Optional: load cookies from a JSON file to handle age-restricted/private videos
                        cookies_path = "youtube_cookies.json"
                        if os.path.exists(cookies_path):
                            cookies = []
                            import json
                            with open(cookies_path, "r") as f:
                                cookies = json.load(f)
                            await context.add_cookies(cookies)

                        page = await context.new_page()
                        await page.goto(url, wait_until="networkidle")

                        # Get title
                        title = await page.title()

                        # Try to get video URL from <video> tag first
                        video_url = await page.evaluate("""() => {
                            const vid = document.querySelector('video');
                            return vid ? vid.src : '';
                        }""")

                        # If video tag not found, fallback to yt-dlp inside Playwright context
                        if not video_url:
                            # Use yt-dlp with page content
                            html_content = await page.content()
                            ydl_opts = {"quiet": True, "skip_download": True, "format": "bestvideo+bestaudio/best"}
                            with YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(url, download=False)
                                for f in info.get("formats", []):
                                    if f.get("url"):
                                        formats.append({
                                            "format_id": f["format_id"],
                                            "type": "video+audio" if f.get("vcodec") != "none" and f.get("acodec") != "none" else "video" if f.get("vcodec") != "none" else "audio",
                                            "resolution": f"{f.get('height', '')}p" if f.get("height") else "",
                                            "ext": f.get("ext"),
                                            "direct_url": f["url"]
                                        })
                                title = info.get("title")
                                thumbnail = info.get("thumbnail", "")

                        else:
                            formats.append({
                                "format_id": "yt_playwright",
                                "type": "video+audio",
                                "resolution": "best",
                                "ext": "mp4",
                                "direct_url": video_url
                            })

                        await browser.close()
                else:
                    # ------------------ Other platforms via yt-dlp ------------------
                    ydl_opts = {"quiet": True, "skip_download": True, "format": "bestvideo+bestaudio/best"}
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                    for f in info.get("formats", []):
                        if f.get("url"):
                            formats.append({
                                "format_id": f["format_id"],
                                "type": "video+audio" if f.get("vcodec") != "none" and f.get("acodec") != "none" else "video" if f.get("vcodec") != "none" else "audio",
                                "resolution": f"{f.get('height', '')}p" if f.get("height") else "",
                                "ext": f.get("ext"),
                                "direct_url": f["url"]
                            })
                    title = info.get("title")
                    thumbnail = info.get("thumbnail", "")

                result = {"title": title or "Video", "thumbnail": thumbnail, "formats": formats}
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
    """Handles progressive vs adaptive streams differently."""
    if type_ == "video+audio":
        import requests
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







# import os
# import requests
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
# from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, RedirectResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from yt_dlp import YoutubeDL
# from urllib.parse import urlparse, parse_qs

# app = FastAPI()

# # Mount static and templates
# app.mount("/static", StaticFiles(directory="static"), name="static")
# templates = Jinja2Templates(directory="templates")

# # Path to cookies file
# COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies/cookies.txt")

# @app.get("/favicon.ico")
# def favicon():
#     return FileResponse("static/favicon.ico")

# @app.get("/", response_class=HTMLResponse)
# def root():
#     return templates.TemplateResponse("index.html", {"request": {}})

# # WebSocket for extracting video info
# @app.websocket("/ws/extract")
# async def websocket_extract(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             url = await websocket.receive_text()
#             await websocket.send_json({"status": "progress", "message": "🔍 Extracting info..."})

#             try:
#                 ydl_opts = {
#                     "quiet": True,
#                     "skip_download": True,
#                     "cookies": COOKIES_FILE,
#                     "format": "bestvideo+bestaudio/best",
#                     "cookiefile": COOKIES_FILE  # Cookies for logged-in YouTube
#                 }

#                 with YoutubeDL(ydl_opts) as ydl:
#                     info = ydl.extract_info(url, download=False)

#                 formats = []
#                 seen = set()

#                 for f in info.get("formats", []):
#                     height = f.get("height")
#                     acodec = f.get("acodec")
#                     vcodec = f.get("vcodec")
#                     url_f = f.get("url")
#                     if not url_f:
#                         continue

#                     if vcodec != "none" and acodec != "none":
#                         label = f"{height}p" if height else "unknown"
#                         formats.append({
#                             "format_id": f["format_id"],
#                             "type": "video+audio",
#                             "resolution": label,
#                             "ext": f.get("ext"),
#                             "direct_url": url_f
#                         })
#                     elif vcodec != "none" and height and height not in seen:
#                         formats.append({
#                             "format_id": f["format_id"],
#                             "type": "video",
#                             "resolution": f"{height}p",
#                             "ext": f.get("ext"),
#                             "direct_url": url_f
#                         })
#                         seen.add(height)
#                     elif vcodec == "none" and acodec != "none":
#                         formats.append({
#                             "format_id": f["format_id"],
#                             "type": "audio",
#                             "bitrate": f.get("abr"),
#                             "ext": f.get("ext"),
#                             "direct_url": url_f
#                         })

#                 result = {"title": info.get("title"), "thumbnail": info.get("thumbnail"), "formats": formats}
#                 await websocket.send_json(result)
#                 await websocket.send_json({"status": "done", "message": "🎯 Done! Direct links ready."})

#             except Exception as e:
#                 await websocket.send_json({"error": str(e)})

#     except WebSocketDisconnect:
#         print("Client disconnected")


# @app.get("/download")
# def download(
#     video_url: str = Query(...),
#     title: str = Query(default="video"),
#     resolution: str = Query(default=""),
#     type_: str = Query(default="")
# ):
#     """Handles progressive vs adaptive streams differently."""

#     if type_ == "video+audio":
#         # Progressive stream → Force download
#         r = requests.get(video_url, stream=True)

#         qs = parse_qs(urlparse(video_url).query)
#         mime = qs.get("mime", ["video/mp4"])[0]
#         ext = mime.split("/")[-1] if "/" in mime else "mp4"

#         safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)

#         filename_parts = [safe_title]
#         if resolution:
#             filename_parts.append(resolution)
#         if type_:
#             filename_parts.append(type_)
#         filename = "_".join(filename_parts) + f".{ext}"

#         return StreamingResponse(
#             r.iter_content(chunk_size=1024*1024),
#             media_type="application/octet-stream",
#             headers={"Content-Disposition": f"attachment; filename={filename}"}
#         )
#     else:
#         # Redirect for adaptive streams (video-only / audio-only)
#         return RedirectResponse(url=video_url)

from typing import Any, Dict, Iterable, List, Set

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import yt_dlp


class ExtractRequest(BaseModel):
    url: str


def _collect_titles(node: Any) -> Iterable[str]:
    if node is None:
        return []
    if isinstance(node, dict):
        if "entries" in node and node.get("entries") is not None:
            titles: List[str] = []
            for entry in node["entries"]:
                titles.extend(list(_collect_titles(entry)))
            return titles
        title = node.get("title")
        return [title] if title else []
    if isinstance(node, list):
        titles: List[str] = []
        for entry in node:
            titles.extend(list(_collect_titles(entry)))
        return titles
    return []


def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


app = FastAPI(title="Video Title Extractor", version="1.0.0")


# Static files and index
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse("static/index.html")


@app.post("/api/extract")
def extract_titles(payload: ExtractRequest) -> JSONResponse:
    if not payload.url or not isinstance(payload.url, str):
        raise HTTPException(status_code=400, detail="A valid URL string is required")

    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        # Avoid unintentionally enumerating extremely large feeds without limit
        "playlistend": 2000,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info: Dict[str, Any] = ydl.extract_info(payload.url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=f"Extraction error: {str(e)}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    # Collect titles
    titles: List[str]
    if isinstance(info, dict):
        if "entries" in info and info.get("entries") is not None:
            titles = _unique_preserve_order(_collect_titles(info.get("entries")))
        else:
            title = info.get("title")
            titles = [title] if title else []
    elif isinstance(info, list):
        titles = _unique_preserve_order(_collect_titles(info))
    else:
        titles = []

    return JSONResponse({
        "count": len(titles),
        "titles": titles,
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


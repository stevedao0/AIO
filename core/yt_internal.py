# -*- coding: utf-8 -*-
"""
yt_internal.py
Gọi YouTube Internal API (youtubei) + tự động lấy INNERTUBE_API_KEY / CONTEXT từ HTML kênh.
Yêu cầu: httpx
"""
from __future__ import annotations
import re, json, asyncio
from typing import Optional, List, Dict, Tuple
import httpx

API_BASE = "https://www.youtube.com/youtubei/v1"

def _build_channel_url(channel: str) -> str:
    s = channel.strip()
    if s.startswith("http"):
        return s
    if s.startswith("UC"):  # channel id
        return f"https://www.youtube.com/channel/{s}"
    if s.startswith("@"):   # handle
        return f"https://www.youtube.com/{s}"
    # tên c/ user/ không hỗ trợ auto, cứ trả thẳng (YT redirect được)
    return f"https://www.youtube.com/{s}"

async def autodiscover(channel: str, proxy: Optional[str]=None, cookies: Optional[dict]=None) -> Tuple[str, Dict]:
    """
    Lấy (api_key, context) từ HTML kênh.
    """
    url = _build_channel_url(channel)
    async with httpx.AsyncClient(http2=True, cookies=cookies) as session:
        r = await session.get(url, proxy=proxy, timeout=30)
        r.raise_for_status()
        html = r.text

    key = None
    ctx = None

    m = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    if m: key = m.group(1)

    m2 = re.search(r'"INNERTUBE_CONTEXT":(\{.*?\})', html)
    if m2:
        try:
            ctx = json.loads(m2.group(1))
        except Exception:
            ctx = None

    if ctx is None:
        mv = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
        cv = mv.group(1) if mv else "2.20240101.00.00"
        ctx = {
            "client": {
                "hl": "vi", "gl": "VN",
                "clientName": "WEB",
                "clientVersion": cv,
                "originalUrl": url,
                "platform": "DESKTOP"
            }
        }

    if not key:
        raise RuntimeError("Không tìm thấy INNERTUBE_API_KEY trong HTML kênh")

    return key, ctx

async def _post_json(session: httpx.AsyncClient, endpoint: str, payload: dict, key: str, proxy: Optional[str]=None):
    params = {"key": key}
    r = await session.post(f"{API_BASE}/{endpoint}", params=params, json=payload, proxy=proxy, timeout=30)
    r.raise_for_status()
    return r.json()

def _extract_title(item: dict) -> str:
    r = (item.get("gridVideoRenderer") or item.get("richItemRenderer", {}).get("content", {}).get("videoRenderer") or {})
    title = r.get("title", {}).get("runs", [{}])[0].get("text") or r.get("headline", {}).get("simpleText")
    return title or "N/A"

def _extract_video_id(item: dict) -> Optional[str]:
    r = item.get("gridVideoRenderer") or item.get("richItemRenderer", {}).get("content", {}).get("videoRenderer")
    if not r: return None
    return r.get("videoId")

async def browse_channel_items(channel: str, key: str, context: dict, tab: str="videos",
                               limit: int=200, proxy: Optional[str]=None, cookies: Optional[dict]=None) -> List[dict]:
    """
    Trả về danh sách item: {'id': videoId, 'title': title}
    """
    items: List[dict] = []
    payload = {"context": context, "browseId": channel, "params": "EgZ2aWRlb3M" if tab=="videos" else "EgZzaG9ydHM"}
    async with httpx.AsyncClient(http2=True, cookies=cookies) as session:
        data = await _post_json(session, "browse", payload, key, proxy)
        contents = (data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {})
                    .get("tabs", [])[0].get("tabRenderer", {}).get("content", {})
                    .get("sectionListRenderer", {}).get("contents", [])[0]
                    .get("itemSectionRenderer", {}).get("contents", []))
        grids = []
        for c in contents:
            gr = c.get("gridRenderer", {}) or c.get("richGridRenderer", {})
            if gr:
                grids = gr.get("items", [])
                break
        for it in grids:
            vid = _extract_video_id(it)
            if vid:
                items.append({"id": vid, "title": _extract_title(it)})
            if len(items) >= limit:
                break
    return items[:limit]

async def player_info_many(video_ids: List[str], key: str, context: dict, proxy: Optional[str]=None,
                           cookies: Optional[dict]=None, concurrency: int=20) -> List[dict]:
    import asyncio as _asyncio
    sem = _asyncio.Semaphore(concurrency)
    results: List[dict] = []
    async with httpx.AsyncClient(http2=True, cookies=cookies) as session:
        async def fetch(vid):
            async with sem:
                payload = {"context": context, "videoId": vid}
                try:
                    data = await _post_json(session, "player", payload, key, proxy)
                    if "videoDetails" not in data:
                        data["videoId"] = vid
                    results.append(data)
                except Exception as e:
                    results.append({"videoId": vid, "error": str(e)})
        await _asyncio.gather(*(fetch(v) for v in video_ids))
    return results

# -*- coding: utf-8 -*-
"""
core/enricher.py
Phase 2: Batch Detail Enrichment cho YouTube video bằng yt-dlp (không dùng Google API).
- Đầu vào: list ID/URL hoặc file .xlsx/.csv có cột 'ID Video'
- Đầu ra: DataFrame + file Excel chứa trường nâng cao (tags, chapters, description, like_count, ...)

Yêu cầu: yt-dlp, pandas
Tuỳ chọn: youtube-transcript-api (để lấy transcript_text)
"""

from __future__ import annotations
import os
import re
import json
from typing import Optional, List, Dict, Tuple, Iterable, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yt_dlp


def _read_ids(input_value: Union[str, List[str]]) -> List[str]:
    """Nhận vào: đường dẫn file (.xlsx/.csv) hoặc list hoặc 1 chuỗi ID/URL.
       Trả về: list video IDs/URLs (ưu tiên ID)."""
    ids: List[str] = []
    if isinstance(input_value, list):
        for x in input_value:
            s = str(x).strip()
            if s:
                ids.append(s)
        return ids

    if isinstance(input_value, str) and os.path.isfile(input_value):
        ext = os.path.splitext(input_value)[1].lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(input_value)
        elif ext == ".csv":
            df = pd.read_csv(input_value)
        else:
            raise ValueError("Định dạng file không hỗ trợ. Cần .xlsx/.xls hoặc .csv")
        col = None
        # chấp nhận nhiều tên cột phổ biến
        for c in df.columns:
            if c.strip().lower() in ("id video", "id", "video id"):
                col = c
                break
        if col is None:
            raise ValueError("Không tìm thấy cột 'ID Video' (hoặc 'ID'/'Video ID') trong file đầu vào.")
        return [str(v).strip() for v in df[col].tolist() if str(v).strip()]

    # là một chuỗi đơn (ID/URL)
    if isinstance(input_value, str):
        s = input_value.strip()
        if s:
            return [s]

    raise ValueError("Input không hợp lệ.")


def _to_watch_url(s: str) -> str:
    # cho phép người dùng đưa trực tiếp ID hoặc URL
    if re.match(r"^[0-9A-Za-z_-]{11}$", s):
        return f"https://www.youtube.com/watch?v={s}"
    return s


def _extract_detail(url_or_id: str, include_transcript: bool = True) -> Dict:
    """Lấy metadata chi tiết 1 video bằng yt-dlp (không tải).
       Trả về dict đã chuẩn hoá các field nâng cao."""
    url = _to_watch_url(url_or_id)
    opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return {"id": url_or_id, "error": "Không lấy được metadata"}

    # Chuẩn hóa các trường mong muốn
    out = {
        "id": info.get("id"),
        "title": info.get("title"),
        "webpage_url": info.get("webpage_url") or url,
        "uploader": info.get("uploader"),
        "channel_id": info.get("channel_id") or info.get("uploader_id"),
        "duration": info.get("duration"),
        "duration_str": _format_duration(info.get("duration")),
        "upload_date": _format_date(info.get("upload_date")),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "dislike_count": info.get("dislike_count"),
        "comment_count": info.get("comment_count"),
        "tags": info.get("tags") or [],
        "description": info.get("description") or "",
        "chapters": info.get("chapters") or [],
        "subtitles": _subtitles_index(info.get("subtitles")),
        "automatic_captions": _subtitles_index(info.get("automatic_captions")),
    }

    # Lấy transcript_text nếu có thư viện youtube-transcript-api
    if include_transcript:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            vid = out["id"] or _maybe_extract_id_from_url(out["webpage_url"])
            if vid:
                # cố gắng lấy transcript với ngôn ngữ ưu tiên
                transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
                # ưu tiên vi, en (tự điều chỉnh nếu cần)
                preferred = ["vi", "en"]
                text = None
                for lang in preferred:
                    try:
                        trs = transcript_list.find_transcript([lang])
                        lines = trs.fetch()
                        text = " ".join([seg.get("text", "") for seg in lines]).strip()
                        if text:
                            break
                    except Exception:
                        continue
                # Nếu vẫn chưa có, thử auto-generated
                if not text:
                    try:
                        trs = transcript_list.find_generated_transcript(["vi", "en"])
                        lines = trs.fetch()
                        text = " ".join([seg.get("text", "") for seg in lines]).strip()
                    except Exception:
                        pass
                out["transcript_text"] = text
        except Exception:
            # Không có thư viện hoặc bị chặn -> bỏ qua
            out["transcript_text"] = None

    return out


def _format_duration(seconds: Optional[Union[int, float]]) -> str:
    if seconds is None:
        return "N/A"
    try:
        sec = int(float(seconds))
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f"{h:02}:{m:02}:{s:02}"
    except Exception:
        return "N/A"


def _format_date(yyyymmdd: Optional[Union[str, int]]) -> str:
    if not yyyymmdd:
        return "N/A"
    s = str(yyyymmdd)
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    return s


def _subtitles_index(subs: Optional[Dict]) -> List[str]:
    """Chuyển dict phụ đề thành danh sách mã ngôn ngữ có sẵn."""
    if not subs or not isinstance(subs, dict):
        return []
    return sorted(list(subs.keys()))


def _maybe_extract_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"[?&]v=([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


def enrich(
    input_value: Union[str, List[str]],
    max_workers: int = 8,
    include_transcript: bool = True,
    out_excel: Optional[str] = None,
    progress: Optional[callable] = None,
    log: Optional[callable] = None,
) -> Tuple[pd.DataFrame, Optional[str]]:
    """Batch enrichment:
       - Đọc ID/URL từ file/list
       - Đa luồng lấy metadata chi tiết bằng yt-dlp
       - Xuất DataFrame và (tuỳ chọn) file Excel.
    """
    ids = _read_ids(input_value)
    total = len(ids)
    if progress:
        progress(0, total)
    if log:
        log(f"Bắt đầu enrich {total} video...", prefix="Enricher")

    rows: List[Dict] = []
    done = 0
    workers = max(1, min(max_workers, 16))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_extract_detail, vid, include_transcript): vid for vid in ids}
        for fut in as_completed(futures):
            vid = futures[fut]
            try:
                data = fut.result()
                rows.append(data)
            except Exception as e:
                rows.append({"id": vid, "error": str(e)})
            finally:
                done += 1
                if progress:
                    progress(done, total)
                if log and done % 10 == 0:
                    log(f"Đã enrich {done}/{total}", prefix="Enricher")

    # Lưu DataFrame
    df = pd.DataFrame(rows)

    # Sắp xếp cột cho dễ đọc
    preferred_cols = [
        "id", "title", "webpage_url", "uploader", "channel_id",
        "duration", "duration_str", "upload_date",
        "view_count", "like_count", "dislike_count", "comment_count",
        "tags", "chapters", "description",
        "subtitles", "automatic_captions", "transcript_text", "error"
    ]
    # Đảm bảo cột tồn tại
    for c in preferred_cols:
        if c not in df.columns:
            df[c] = None
    df = df[preferred_cols]

    saved_path = None
    if out_excel:
        try:
            os.makedirs(os.path.dirname(out_excel) or ".", exist_ok=True)
            df.to_excel(out_excel, index=False)
            saved_path = out_excel
            if log:
                log(f"Đã lưu: {saved_path}", prefix="Enricher")
        except Exception as e:
            if log:
                log(f"Lỗi lưu Excel: {e}", prefix="Enricher")

    return df, saved_path

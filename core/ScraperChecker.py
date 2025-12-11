# -*- coding: utf-8 -*-
"""
ScraperChecker.py - ENHANCED LOGGING với ETA countdown và real-time progress
"""
import os
import re
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import yt_dlp
import multiprocessing
from typing import Callable, Optional, Union, List, Tuple, Dict, Any
import time
import random
from functools import lru_cache
import threading

TOPIC_OVERRIDES = {
    "UCdW9arh-ckZrMW_wHu4xPYA": ("UCNqz53FCc3mUg5NyzHxsXGQ", "Quang Lê Official"),
}


class ProgressTracker:
    """Track detailed progress với ETA calculation"""

    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.start_time = time.time()
        self.last_update = time.time()
        self.processing_rates = []  # Track speeds over time
        self.current_item = "Initializing..."
        self.batch_info = ""

    def update(self, completed: int, current_item: str = "", batch_info: str = ""):
        self.completed = completed
        self.current_item = current_item
        self.batch_info = batch_info

        current_time = time.time()
        elapsed = current_time - self.start_time

        if elapsed > 0 and completed > 0:
            # Calculate rate (items per second)
            rate = completed / elapsed
            self.processing_rates.append(rate)

            # Keep only last 10 measurements for smoothing
            if len(self.processing_rates) > 10:
                self.processing_rates = self.processing_rates[-10:]

        self.last_update = current_time

    def get_eta(self) -> Tuple[float, str]:
        """Trả về ETA seconds và formatted string"""
        if self.completed == 0 or len(self.processing_rates) == 0:
            return 0, "Calculating..."

        # Use average of recent rates
        avg_rate = sum(self.processing_rates) / len(self.processing_rates)
        remaining = self.total - self.completed

        if avg_rate > 0:
            eta_seconds = remaining / avg_rate
            eta_str = self._format_time(eta_seconds)
            return eta_seconds, eta_str
        else:
            return 0, "Unknown"

    def get_elapsed(self) -> str:
        """Thời gian đã trôi qua"""
        elapsed = time.time() - self.start_time
        return self._format_time(elapsed)

    def get_rate(self) -> float:
        """Tốc độ xử lý hiện tại"""
        if len(self.processing_rates) > 0:
            return sum(self.processing_rates[-5:]) / min(5, len(self.processing_rates))
        return 0

    def _format_time(self, seconds: float) -> str:
        """Format seconds thành HH:MM:SS"""
        if seconds < 0:
            return "00:00:00"
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_progress_info(self) -> Dict[str, Any]:
        """Trả về dict chứa tất cả thông tin progress"""
        eta_seconds, eta_str = self.get_eta()

        return {
            'completed': self.completed,
            'total': self.total,
            'percentage': (self.completed / self.total * 100) if self.total > 0 else 0,
            'current_item': self.current_item,
            'batch_info': self.batch_info,
            'elapsed': self.get_elapsed(),
            'eta': eta_str,
            'eta_seconds': eta_seconds,
            'rate': self.get_rate(),
            'rate_str': f"{self.get_rate():.1f} items/sec"
        }


class Utils:
    @staticmethod
    def format_duration(seconds):
        if seconds is None:
            return "N/A"
        try:
            sec = int(float(seconds));
            h, rem = divmod(sec, 3600);
            m, s = divmod(rem, 60)
            return f"{h:02}:{m:02}:{s:02}"
        except Exception:
            return "N/A"

    @staticmethod
    def format_date(upload_date):
        if not upload_date:
            return "N/A"
        try:
            dt = datetime.strptime(str(upload_date), "%Y%m%d");
            return dt.strftime("%d/%m/%Y")
        except Exception:
            try:
                if isinstance(upload_date, datetime): return upload_date.strftime("%d/%m/%Y")
                dt = datetime.fromisoformat(str(upload_date));
                return dt.strftime("%d/%m/%Y")
            except Exception:
                return "N/A"

    @staticmethod
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[\\/*?:\"<>|]', "", str(name)).strip()

    @staticmethod
    def extract_channel_id(info: dict) -> str:
        for key in ("owner_channel_id", "channel_id", "uploader_id"):
            cid = info.get(key)
            if cid and isinstance(cid, str) and cid.startswith("UC"):
                return cid
        for key in ("uploader_url", "channel_url"):
            url = info.get(key, "")
            m = re.search(r"/channel/(UC[0-9A-Za-z_-]+)", url)
            if m: return m.group(1)
        return "N/A"


# ===== STABLE CACHING =====
@lru_cache(maxsize=500)
def _cached_normalize_input(channel: str) -> str:
    c = channel.strip()
    if c.startswith("http"):
        for pat, prefix in [(r"/channel/([^/?&]+)", ""),
                            (r"/c/([^/?&]+)", ""),
                            (r"/user/([^/?&]+)", ""),
                            (r"/@([^/?&]+)", "@")]:
            m = re.search(pat, c)
            if m: return prefix + m.group(1)
    return c


def get_video_info(video_id: str, retries: int = 2, use_turbo: bool = True, cookies_file: Optional[str] = None) -> dict:
    """Lấy thông tin video với retry và fallback modes"""

    def _get_opts(turbo: bool, cookies: Optional[str]) -> dict:
        opts = {
            'quiet': True, 'skip_download': True, 'nocheckcertificate': True,
            'ignoreerrors': True, 'extractor_retries': 1, 'retries': 1,
            'socket_timeout': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        } if turbo else {
            'quiet': True, 'skip_download': True, 'nocheckcertificate': True,
            'ignoreerrors': False, 'extractor_retries': 3, 'retries': 3,
            'socket_timeout': 20
        }
        if cookies and os.path.exists(cookies):
            opts['cookiefile'] = cookies
        return opts

    current_turbo = use_turbo
    for attempt in range(retries + 1):
        opts = _get_opts(current_turbo, cookies_file)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if info:
                    return info
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if "sign in to confirm" in error_msg:
                if current_turbo:  # Nếu đang turbo, thử lại với safe mode
                    current_turbo = False
                    continue
                return {"error": "Sign-in required"} # Nếu đã ở safe mode mà vẫn lỗi, báo lỗi
            elif "private video" in error_msg:
                return {"error": "Private video"}
            elif "video unavailable" in error_msg:
                return {"error": "Video unavailable"}
            elif "live event will begin" in error_msg:
                return {"error": "Upcoming livestream"}
            elif "429" in error_msg or "too many requests" in error_msg:
                if attempt < retries:
                    time.sleep(random.uniform(2, 5))
                    continue
                return {"error": "Rate limited"}
            elif attempt < retries:
                time.sleep(random.uniform(1, 3))
                continue
            else:
                return {"error": f"Download error: {str(e)[:80]}"}
        except Exception as e:
            if attempt < retries:
                time.sleep(random.uniform(0.5, 1.5))
                continue
            return {"error": f"Unexpected error: {str(e)[:80]}"}
    
    return {"error": "Failed after retries"}


def get_channel_info_stable(channel_input: str, use_turbo: bool = True) -> Tuple[str, list]:
    """Lấy thông tin kênh với multiple fallback strategies"""
    cid = _cached_normalize_input(channel_input)
    entries, title = [], cid

    timeout = 12 if use_turbo else 20
    ydl_opts = {
        'quiet': True, 'extract_flat': True, 'skip_download': True,
        'ignoreerrors': True, 'nocheckcertificate': True,
        'extractor_retries': 1 if use_turbo else 2,
        'retries': 1 if use_turbo else 2,
        'socket_timeout': timeout,
    }

    # Strategy 1: Try direct approaches first
    urls_to_try = []

    if cid.startswith("UC"):
        urls_to_try.extend([
            f"https://www.youtube.com/channel/{cid}/videos",
            f"https://www.youtube.com/playlist?list=UU{cid[2:]}"  # uploads playlist
        ])
    elif cid.startswith("@"):
        urls_to_try.append(f"https://www.youtube.com/{cid}/videos")
    else:
        urls_to_try.extend([
            f"https://www.youtube.com/@{cid}/videos",
            f"https://www.youtube.com/c/{cid}/videos",
            f"https://www.youtube.com/user/{cid}/videos"
        ])

    for url in urls_to_try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(url, download=False)
                if data and data.get('entries'):
                    title = data.get('uploader') or data.get('title') or title
                    entries = data.get('entries', [])[:300]  # Tăng từ 200 lên 300
                    if entries:
                        return title, entries
        except:
            pass

        # Small delay between attempts
        time.sleep(random.uniform(0.3, 0.8))

    return title, entries


def get_shorts_info_stable(channel_input: str, use_turbo: bool = True) -> Tuple[str, list]:
    """Lấy shorts với stable approach"""
    cid = _cached_normalize_input(channel_input)

    timeout = 12 if use_turbo else 20
    ydl_opts = {
        'quiet': True, 'extract_flat': True, 'skip_download': True,
        'ignoreerrors': True, 'nocheckcertificate': True,
        'extractor_retries': 1 if use_turbo else 2,
        'socket_timeout': timeout
    }

    urls_to_try = []
    if cid.startswith("UC"):
        urls_to_try.append(f"https://www.youtube.com/channel/{cid}/shorts")
    elif cid.startswith("@"):
        urls_to_try.append(f"https://www.youtube.com/{cid}/shorts")
    else:
        urls_to_try.extend([
            f"https://www.youtube.com/@{cid}/shorts",
            f"https://www.youtube.com/c/{cid}/shorts"
        ])

    for url in urls_to_try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(url, download=False)
                if data:
                    title = data.get('uploader') or data.get('title') or cid
                    entries = data.get('entries', [])[:150]  # Tăng từ 100 lên 150
                    return title, entries
        except:
            pass

        time.sleep(random.uniform(0.2, 0.6))

    return cid, []


def _scraper_worker_enhanced(args_batch: List[Tuple], batch_idx: int, tracker: ProgressTracker, cookies_file: Optional[str] = None) -> List[dict]:
    """Enhanced worker với detailed progress tracking"""
    results = []
    batch_size = len(args_batch)

    for local_idx, (entry, idx, title, cid_input, ftype) in enumerate(args_batch):
        vid = entry.get('id')
        if not vid:
            continue

        # Update tracker với thông tin chi tiết
        current_item = f"Batch {batch_idx + 1} - Video {local_idx + 1}/{batch_size}: {vid}"
        batch_info = f"Processing {ftype} video"

        # Cập nhật tracker (sẽ được gửi về UI)
        global_completed = tracker.completed + local_idx
        tracker.update(global_completed, current_item, batch_info)

        # Small delay để tránh rate limiting
        time.sleep(random.uniform(0.15, 0.4))

        try:
            start_time = time.time()
            info = get_video_info(vid, retries=2, use_turbo=True, cookies_file=cookies_file)
            process_time = time.time() - start_time

            # Log thời gian xử lý
            status_info = f"Processed in {process_time:.1f}s"

        except Exception as e:
            info = {"error": f"Worker error: {str(e)[:50]}"}
            status_info = f"Error: {str(e)[:30]}"

        if not info or 'error' in info:
            result = {
                'Số thứ tự': idx, 'Tên Kênh': title, 'ID Kênh': cid_input,
                'Tên Video': 'N/A', 'ID Video': vid,
                'Link Video': f'https://www.youtube.com/watch?v={vid}',
                'Thời gian': 'N/A', 'Ngày xuất bản': 'N/A', 'Lượt xem': 'N/A',
                'Tình trạng': info.get('error', 'N/A') if info else 'N/A',
                'Hình thức': ftype,
                '_debug_info': status_info
            }
        else:
            cid_real = Utils.extract_channel_id(info)
            name_real = info.get('uploader', title)

            if cid_real in TOPIC_OVERRIDES:
                cid_real, name_real = TOPIC_OVERRIDES[cid_real]

            result = {
                'Số thứ tự': idx, 'Tên Kênh': name_real, 'ID Kênh': cid_real,
                'Tên Video': info.get('title', 'N/A'), 'ID Video': vid,
                'Link Video': info.get('webpage_url', f'https://www.youtube.com/watch?v={vid}'),
                'Thời gian': Utils.format_duration(info.get('duration')),
                'Ngày xuất bản': Utils.format_date(info.get('upload_date')),
                'Lượt xem': info.get('view_count', 'N/A'),
                'Tình trạng': 'OK', 'Hình thức': ftype,
                '_debug_info': status_info
            }

        results.append(result)

    return results


def run_scraper(channel_input: str, out_folder: str,
                log_func: Optional[Callable] = None,
                progress_callback: Optional[Callable[[int, int], None]] = None,
                detail_callback: Optional[Callable[[Dict[str, Any]], None]] = None,  # NEW: Detailed callback
                stop_event: Optional[object] = None,
                turbo_mode: bool = True,
                max_workers: int = None,
                cookies_file: Optional[str] = None) -> Optional[str]:
    """
    ENHANCED SCRAPER với detailed progress tracking và ETA
    detail_callback: callback nhận dict với thông tin chi tiết
    """

    log_func and log_func(f'🚀 ENHANCED TURBO: Starting scrape {channel_input}', prefix='EnhancedScraper')

    # Get channel info
    try:
        log_func and log_func('📡 Fetching channel info...', prefix='EnhancedScraper')
        s_title, s_items = get_shorts_info_stable(channel_input, use_turbo=turbo_mode)
        u_title, u_items = get_channel_info_stable(channel_input, use_turbo=turbo_mode)
    except Exception as e:
        log_func and log_func(f'❌ Channel info error: {str(e)}', prefix='EnhancedScraper')
        return None

    if not (s_items or u_items):
        log_func and log_func('❌ No videos found. Check channel URL/ID.', prefix='EnhancedScraper')
        return None

    title = s_title if s_items else u_title
    log_func and log_func(f'✅ Found channel: {title}', prefix='EnhancedScraper')

    # Prepare args
    args, idx = [], 1
    for e in s_items:
        args.append((e, idx, title, channel_input, 'Shorts'))
        idx += 1
    for e in u_items:
        args.append((e, idx, title, channel_input, 'Video'))
        idx += 1

    total = len(args)
    log_func and log_func(f'📊 Total: {total} videos (Shorts: {len(s_items)}, Videos: {len(u_items)})',
                          prefix='EnhancedScraper')

    # Initialize progress tracker
    tracker = ProgressTracker(total)

    if progress_callback:
        progress_callback(0, total)

    results = []

    # Progress update thread
    def progress_updater():
        """Thread để gửi progress updates liên tục"""
        while tracker.completed < tracker.total:
            if detail_callback:
                progress_info = tracker.get_progress_info()
                try:
                    detail_callback(progress_info)
                except:
                    pass
            time.sleep(0.5)  # Update every 500ms

    progress_thread = threading.Thread(target=progress_updater, daemon=True)
    progress_thread.start()

    # Processing strategy
    if turbo_mode and total > 40:
        # BATCH PROCESSING
        batch_size = min(20, max(8, total // 8))
        batches = [args[i:i + batch_size] for i in range(0, len(args), batch_size)]

        if max_workers is None:
            cpu_count = multiprocessing.cpu_count()
            max_workers = min(cpu_count * 2, len(batches), 8)

        log_func and log_func(
            f'⚡ Batch processing: {len(batches)} batches, {max_workers} workers, {batch_size} items/batch',
            prefix='EnhancedScraper')

        try:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # Submit all batches
                futures = {
                    executor.submit(_scraper_worker_enhanced, batch, i, tracker, cookies_file): i
                    for i, batch in enumerate(batches)
                }

                done_batches = 0

                for future in as_completed(futures):
                    if stop_event and stop_event.is_set():
                        executor.shutdown(cancel_futures=True)
                        return None

                    batch_idx = futures[future]
                    batch = batches[batch_idx]

                    try:
                        batch_results = future.result(timeout=120)  # 2 phút timeout per batch
                        if batch_results:
                            results.extend(batch_results)

                        # Update tracker
                        tracker.update(
                            done_batches * batch_size + len(batch),
                            f"Completed batch {batch_idx + 1}",
                            f"✅ {len(batch_results)} results"
                        )

                        log_func and log_func(
                            f'✅ Batch {batch_idx + 1}/{len(batches)} completed: {len(batch_results)} results',
                            prefix='EnhancedScraper')

                    except Exception as e:
                        log_func and log_func(f'⚠️ Batch {batch_idx + 1} failed: {str(e)[:100]}',
                                              prefix='EnhancedScraper')

                        # Update tracker for failed batch
                        tracker.update(
                            done_batches * batch_size + len(batch),
                            f"Failed batch {batch_idx + 1}",
                            f"❌ Error: {str(e)[:50]}"
                        )

                    done_batches += 1
                    processed_count = min(done_batches * batch_size, total)
                    if progress_callback:
                        progress_callback(processed_count, total)

                    # ETA logging
                    eta_seconds, eta_str = tracker.get_eta()
                    rate_str = tracker.get_rate()
                    if done_batches % 2 == 0:
                        log_func and log_func(
                            f'⏱️ Progress: {done_batches}/{len(batches)} batches | Rate: {rate_str:.1f} items/s | ETA: {eta_str}',
                            prefix='EnhancedScraper')

        except Exception as e:
            log_func and log_func(f'❌ Batch processing failed: {str(e)}. Falling back...', prefix='EnhancedScraper')
            turbo_mode = False

    # STANDARD PROCESSING (fallback)
    if not turbo_mode or total <= 40 or not results:
        if not results:
            log_func and log_func('🔄 Using standard processing mode', prefix='EnhancedScraper')
            results = []

        max_workers = max_workers or min(multiprocessing.cpu_count(), total, 8)

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            single_batches = [(([arg], 0, tracker)) for arg in args]
            futures = {
                executor.submit(_scraper_worker_enhanced, [batch[0]], batch[1], batch[2], cookies_file): i
                for i, batch in enumerate(single_batches)
            }

            done = 0

            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(cancel_futures=True)
                    return None

                try:
                    batch_results = future.result(timeout=45)
                    if batch_results:
                        results.extend(batch_results)

                    # Update detailed progress
                    tracker.update(done + 1, f"Item {done + 1}/{total}", "Standard processing")

                except Exception as e:
                    item_idx = futures[future]
                    log_func and log_func(f'⚠️ Item {item_idx + 1} failed: {str(e)[:50]}', prefix='EnhancedScraper')

                done += 1
                if progress_callback:
                    progress_callback(done, total)

                if done % 25 == 0:
                    eta_seconds, eta_str = tracker.get_eta()
                    rate = tracker.get_rate()
                    log_func and log_func(f'📈 Standard progress: {done}/{total} | Rate: {rate:.1f}/s | ETA: {eta_str}',
                                          prefix='EnhancedScraper')

    # Final update
    tracker.update(tracker.total, "Processing complete", "Saving results...")
    if detail_callback:
        detail_callback(tracker.get_progress_info())

    if not results:
        log_func and log_func('❌ No results obtained', prefix='EnhancedScraper')
        return None

    # Process results
    df = pd.DataFrame(results)

    if not df.empty:
        # Remove debug info before saving
        if '_debug_info' in df.columns:
            df = df.drop('_debug_info', axis=1)

        # Remove duplicates
        df = df.drop_duplicates(subset=['ID Video'], keep='first')
        df = df.sort_values('Số thứ tự').reset_index(drop=True)
        df['Số thứ tự'] = range(1, len(df) + 1)

    # Save file
    safe = Utils.sanitize_filename(title)
    os.makedirs(out_folder, exist_ok=True)

    suffix = "_ENHANCED" if turbo_mode else "_STANDARD"
    path = os.path.join(out_folder, f"{safe}_Videos{suffix}.xlsx")

    try:
        df.to_excel(path, index=False)
        success_count = len(df[df['Tình trạng'] == 'OK']) if 'Tình trạng' in df.columns else len(df)
        total_count = len(df)
        elapsed_time = tracker.get_elapsed()

        log_func and log_func(f'🎉 SUCCESS! Saved {success_count}/{total_count} videos in {elapsed_time}',
                              prefix='EnhancedScraper')
        log_func and log_func(f'📁 File: {path}', prefix='EnhancedScraper')

        return path
    except Exception as e:
        log_func and log_func(f'❌ Save error: {str(e)}', prefix='EnhancedScraper')
        return None


# ===== ENHANCED CHECKER với detailed progress =====
def _checker_worker_enhanced(batch_items: List[Tuple[int, str]], batch_idx: int, tracker: ProgressTracker) -> List[
    dict]:
    """Enhanced checker worker với progress tracking"""
    results = []
    batch_size = len(batch_items)

    for local_idx, (idx, vid) in enumerate(batch_items):
        # Update progress
        current_item = f"Batch {batch_idx + 1} - Checking {local_idx + 1}/{batch_size}: {vid}"
        batch_info = f"Validating video info"

        global_completed = tracker.completed + local_idx
        tracker.update(global_completed, current_item, batch_info)

        time.sleep(random.uniform(0.3, 0.7))  # Rate limiting

        try:
            start_time = time.time()
            info = get_video_info(vid, retries=2, use_turbo=True)
            process_time = time.time() - start_time

            status_info = f"Checked in {process_time:.1f}s"

        except Exception as e:
            info = {"error": f"Check error: {str(e)[:50]}"}
            status_info = f"Error: {str(e)[:30]}"

        status = 'OK' if info and 'error' not in info else f"Error: {info.get('error', 'N/A') if info else 'N/A'}"

        result = {
            'index': idx,
            'ID Kênh': info.get('channel_id', 'N/A') if info and 'error' not in info else 'N/A',
            'Tên Kênh': info.get('uploader', 'N/A') if info and 'error' not in info else 'N/A',
            'ID Video': vid,
            'Tên Video': info.get('title', 'N/A') if info and 'error' not in info else 'N/A',
            'Thời Lượng': Utils.format_duration(info.get('duration')) if info and 'error' not in info else 'N/A',
            'Ngày Xuất Bản': Utils.format_date(info.get('upload_date')) if info and 'error' not in info else 'N/A',
            'Lượt View': info.get('view_count', 'N/A') if info and 'error' not in info else 'N/A',
            'Tình trạng': status,
            'Hình thức': 'Shorts' if info and info.get('duration', 0) and info.get('duration') <= 60 else 'Video',
            '_debug_info': status_info
        }
        results.append(result)

    return results


def run_checker(fp: str, max_workers: int = 6,
                progress_callback: Optional[Callable[[int, int], None]] = None,
                detail_callback: Optional[Callable[[Dict[str, Any]], None]] = None,  # NEW
                log_func: Optional[Callable] = None,
                stop_event: Optional[object] = None,
                turbo_mode: bool = True) -> Optional[str]:
    """ENHANCED CHECKER với detailed progress"""

    def read_input_file(fp: str) -> Optional[pd.DataFrame]:
        ext = os.path.splitext(fp)[1].lower()
        if ext in ['.xls', '.xlsx']: return pd.read_excel(fp)
        if ext == '.csv': return pd.read_csv(fp)
        return None

    df_in = read_input_file(fp)
    if df_in is None or 'ID Video' not in df_in.columns:
        log_func and log_func("❌ Invalid file or missing 'ID Video' column.", prefix='EnhancedChecker')
        return None

    items = list(df_in['ID Video'].items())
    total = len(items)

    log_func and log_func(f'🚀 ENHANCED CHECKER: {total} videos', prefix='EnhancedChecker')

    # Initialize progress tracker
    tracker = ProgressTracker(total)

    if progress_callback:
        progress_callback(0, total)

    # Progress update thread
    def progress_updater():
        while tracker.completed < tracker.total:
            if detail_callback:
                progress_info = tracker.get_progress_info()
                try:
                    detail_callback(progress_info)
                except:
                    pass
            time.sleep(0.5)

    progress_thread = threading.Thread(target=progress_updater, daemon=True)
    progress_thread.start()

    results = []

    if turbo_mode and total > 15:
        # Batch processing
        batch_size = min(15, max(5, total // 6))
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        max_workers = min(max_workers, len(batches), 6)

        log_func and log_func(f'⚡ Batch checking: {len(batches)} batches, {max_workers} workers',
                              prefix='EnhancedChecker')

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_checker_worker_enhanced, batch, i, tracker): i
                for i, batch in enumerate(batches)
            }
            done_batches = 0

            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(cancel_futures=True)
                    return None

                batch_idx = futures[future]
                batch = batches[batch_idx]

                try:
                    batch_results = future.result(timeout=90)
                    results.extend(batch_results)

                    tracker.update(
                        done_batches * batch_size + len(batch),
                        f"Completed check batch {batch_idx + 1}",
                        f"✅ {len(batch_results)} checked"
                    )

                    log_func and log_func(f'✅ Check batch {batch_idx + 1}/{len(batches)}: {len(batch_results)} results',
                                          prefix='EnhancedChecker')

                except Exception as e:
                    log_func and log_func(f'⚠️ Check batch {batch_idx + 1} error: {str(e)[:50]}',
                                          prefix='EnhancedChecker')

                done_batches += 1
                processed = min(done_batches * batch_size, total)
                if progress_callback:
                    progress_callback(processed, total)

                if done_batches % 2 == 0:
                    eta_seconds, eta_str = tracker.get_eta()
                    rate = tracker.get_rate()
                    log_func and log_func(
                        f'⏱️ Check progress: {done_batches}/{len(batches)} batches | Rate: {rate:.1f}/s | ETA: {eta_str}',
                        prefix='EnhancedChecker')
    else:
        # Standard processing
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            single_batches = [(([item], 0, tracker)) for item in items]
            futures = {
                executor.submit(_checker_worker_enhanced, [batch[0]], batch[1], batch[2]): i
                for i, batch in enumerate(single_batches)
            }
            done = 0

            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(cancel_futures=True)
                    return None

                try:
                    batch_results = future.result(timeout=30)
                    results.extend(batch_results)

                    tracker.update(done + 1, f"Checked item {done + 1}/{total}", "Standard check")

                except:
                    pass

                done += 1
                if progress_callback:
                    progress_callback(done, total)

    # Final processing
    tracker.update(tracker.total, "Check complete", "Saving results...")
    if detail_callback:
        detail_callback(tracker.get_progress_info())

    df_out = pd.DataFrame(results)

    # Remove debug info
    if '_debug_info' in df_out.columns:
        df_out = df_out.drop('_debug_info', axis=1)

    df_out.insert(0, 'Số thứ tự', range(1, len(df_out) + 1))

    cols = ['Số thứ tự', 'ID Kênh', 'Tên Kênh', 'ID Video', 'Tên Video', 'Thời Lượng', 'Ngày Xuất Bản', 'Lượt View',
            'Tình trạng', 'Hình thức']
    df_out = df_out[cols]

    suffix = "_ENHANCED" if turbo_mode else "_STANDARD"
    out_path = os.path.splitext(fp)[0] + f'_checked{suffix}.xlsx'

    try:
        df_out.to_excel(out_path, index=False)
        success_count = len(df_out[df_out['Tình trạng'] == 'OK']) if 'Tình trạng' in df_out.columns else 0
        elapsed_time = tracker.get_elapsed()

        log_func and log_func(f'🎉 CHECKER COMPLETE: {success_count}/{len(df_out)} OK in {elapsed_time}',
                              prefix='EnhancedChecker')
        log_func and log_func(f'📁 File: {out_path}', prefix='EnhancedChecker')

        return out_path
    except Exception as e:
        log_func and log_func(f'❌ Save error: {str(e)}', prefix='EnhancedChecker')
        return None


# ===== Keep original download functions =====
def _build_ydl_opts_for_download(
        out_folder: str,
        quality: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        audio_only: bool = False,
        preferred_audio_codec: str = 'mp3',
        preferred_audio_quality: str = '192',
        concurrent_frags: int = 8,
        merge_to: str = 'mp4',
        cookies_file: Optional[str] = None,
        proxy: Optional[str] = None,
        write_thumbnail: bool = False,
        add_metadata: bool = True,
        embed_thumbnail: bool = False,
        download_archive_path: Optional[str] = None,
        enable_aria2: bool = False,
        rate_limit: Optional[int] = None,
        throttled_rate: Optional[int] = None,
        http_chunk_size: Optional[int] = 10_485_760,
        retries: int = 10,
        fragment_retries: int = 10,
        sleep_interval: Optional[float] = None,
        max_sleep_interval: Optional[float] = None
) -> dict:
    os.makedirs(out_folder, exist_ok=True)
    outtmpl = os.path.join(out_folder, '%(uploader)s - %(title)s [%(id)s].%(ext)s')
    ydl_opts = {
        'outtmpl': outtmpl, 'quiet': True, 'no_warnings': True, 'restrictfilenames': False, 'windowsfilenames': True,
        'noprogress': True, 'format': 'bestaudio/best' if audio_only else quality,
        'concurrent_fragment_downloads': concurrent_frags, 'merge_output_format': None if audio_only else merge_to,
        'postprocessors': [], 'continuedl': True, 'retries': retries, 'fragment_retries': fragment_retries,
        'nocheckcertificate': True,
        'ffmpeg_location': os.environ.get('FFMPEG_LOCATION'),
    }
    if proxy: ydl_opts['proxy'] = proxy
    if cookies_file and os.path.exists(cookies_file): ydl_opts['cookiefile'] = cookies_file
    if download_archive_path: ydl_opts['download_archive'] = download_archive_path
    if rate_limit: ydl_opts['ratelimit'] = rate_limit
    if throttled_rate: ydl_opts['throttled_rate'] = throttled_rate
    if http_chunk_size: ydl_opts['http_chunk_size'] = http_chunk_size
    if sleep_interval: ydl_opts['sleep_interval'] = sleep_interval
    if max_sleep_interval: ydl_opts['max_sleep_interval'] = max_sleep_interval
    if enable_aria2:
        ydl_opts['external_downloader'] = 'aria2c'
        ydl_opts['external_downloader_args'] = ['-x16', '-k1M', '--file-allocation=none']
    if add_metadata: ydl_opts['postprocessors'].append({'key': 'FFmpegMetadata'})
    if write_thumbnail: ydl_opts['writethumbnail'] = True
    if embed_thumbnail: ydl_opts['postprocessors'].append({'key': 'EmbedThumbnail'})
    if audio_only:
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio', 'preferredcodec': preferred_audio_codec,
            'preferredquality': preferred_audio_quality
        })
    return ydl_opts


def download_video(
        video: str, out_folder: str = 'downloads',
        quality: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        audio_only: bool = False, concurrent_frags: int = 8,
        cookies_file: Optional[str] = None, proxy: Optional[str] = None,
        write_thumbnail: bool = False, embed_thumbnail: bool = False,
        add_metadata: bool = True, download_archive_path: Optional[str] = None,
        enable_aria2: bool = False, rate_limit: Optional[int] = None,
        throttled_rate: Optional[int] = None, http_chunk_size: Optional[int] = 10_485_760,
        retries: int = 10, fragment_retries: int = 10,
        sleep_interval: Optional[float] = None, max_sleep_interval: Optional[float] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        log_func: Optional[Callable[[str], None]] = None, stop_event: Optional[object] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    if not video: return False, None, 'Thiếu video ID/URL'
    url = f'https://www.youtube.com/watch?v={video}' if re.match(r'^[0-9A-Za-z_-]{11}$', video) else video
    ydl_opts = _build_ydl_opts_for_download(
        out_folder=out_folder, quality=quality, audio_only=audio_only,
        concurrent_frags=concurrent_frags, cookies_file=cookies_file, proxy=proxy,
        write_thumbnail=write_thumbnail, embed_thumbnail=embed_thumbnail, add_metadata=add_metadata,
        download_archive_path=download_archive_path, enable_aria2=enable_aria2,
        rate_limit=rate_limit, throttled_rate=throttled_rate, http_chunk_size=http_chunk_size,
        retries=retries, fragment_retries=fragment_retries, sleep_interval=sleep_interval,
        max_sleep_interval=max_sleep_interval
    )

    def _hook(d):
        if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
            raise yt_dlp.utils.DownloadError("Cancelled by user")
        if progress_callback:
            payload = {'phase': d.get('status')}
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                percent = (downloaded / total) if total else None
                payload.update({'percent': percent, 'downloaded': downloaded, 'total': total,
                                'speed': d.get('speed'), 'eta': d.get('eta'), 'filename': d.get('filename')})
            elif d.get('status') in ('finished', 'postprocessing'):
                payload.update({'filename': d.get('filename')})
            try:
                progress_callback(payload)
            except Exception:
                pass
        if log_func and d.get('status') == 'downloading':
            info = []
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total and d.get('downloaded_bytes'):
                try:
                    p = d['downloaded_bytes'] / float(total);
                    info.append(f"{p * 100:.1f}%")
                except Exception:
                    pass
            if d.get('speed'): info.append(f"{d['speed'] / 1024 / 1024:.2f} MB/s")
            if d.get('eta'): info.append(f"ETA {d['eta']}s")
            if info: log_func('[Downloader] ' + ' | '.join(info))

    ydl_opts['progress_hooks'] = [_hook]
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            out_path = None
            if info:
                if '_filename' in info:
                    out_path = info.get('_filename')
                else:
                    ext = info.get('ext') or ('mp3' if audio_only else 'mp4')
                    out_path = os.path.join(
                        out_folder,
                        f"{Utils.sanitize_filename(info.get('uploader', ''))} - "
                        f"{Utils.sanitize_filename(info.get('title', ''))} [{info.get('id', '')}].{ext}"
                    )
            return True, out_path, None
    except Exception as e:
        if log_func: log_func(f'[Downloader] Lỗi: {e}')
        return False, None, str(e)


def _expand_video_ids_from_url(url: str) -> List[str]:
    flat_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True, 'ignoreerrors': True,
                 'nocheckcertificate': True}
    ids: List[str] = []
    try:
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            data = ydl.extract_info(url, download=False)
        if not data: return ids
        entries = data.get('entries') or []
        if entries:
            for e in entries:
                if not e: continue
                vid = e.get('id')
                if vid and re.match(r'^[0-9A-Za-z_-]{11}$', vid): ids.append(vid)
        else:
            vid = data.get('id')
            if vid and re.match(r'^[0-9A-Za-z_-]{11}$', vid): ids.append(vid)
    except Exception:
        pass
    return ids


def run_downloader(
        input_value: Union[str, List[str]], out_folder: str,
        quality: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        audio_only: bool = False, max_workers: int = 2, concurrent_frags: int = 8,
        cookies_file: Optional[str] = None, proxy: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        detail_callback: Optional[Callable[[dict], None]] = None,
        log_func: Optional[Callable[[str, str], None]] = None,
        stop_event: Optional[object] = None, enable_aria2: bool = False, use_archive: bool = True
) -> Optional[str]:
    os.makedirs(out_folder, exist_ok=True)
    archive_path = os.path.join(out_folder, 'download_archive.txt') if use_archive else None

    def _log(msg: str):
        if log_func:
            try:
                log_func(msg, prefix='[Downloader]')
            except TypeError:
                log_func(f'[Downloader] {msg}')

    def read_input_file(fp: str) -> Optional[pd.DataFrame]:
        ext = os.path.splitext(fp)[1].lower()
        if ext in ['.xls', '.xlsx']: return pd.read_excel(fp)
        if ext == '.csv': return pd.read_csv(fp)
        return None

    id_list: List[str] = []
    if isinstance(input_value, list):
        id_list = [str(x).strip() for x in input_value if str(x).strip()]
    elif isinstance(input_value, str) and os.path.isfile(input_value):
        df = read_input_file(input_value)
        if df is None or 'ID Video' not in df.columns:
            _log('File không hợp lệ hoặc thiếu cột ID Video');
            return None
        id_list = [str(x).strip() for x in df['ID Video'].tolist() if str(x).strip()]
    elif isinstance(input_value, str):
        s = input_value.strip()
        if s.startswith('http'):
            expanded = _expand_video_ids_from_url(s);
            id_list = expanded if expanded else [s]
        else:
            id_list = [s]
    else:
        _log('Input không hợp lệ');
        return None

    total = len(id_list)
    if total == 0:
        _log('Không có mục nào để tải');
        return None
    if progress_callback: progress_callback(0, total)

    results, done_counter = [], 0

    def _task(vid):
        return download_video(
            vid, out_folder=out_folder, quality=quality, audio_only=audio_only,
            concurrent_frags=concurrent_frags, cookies_file=cookies_file, proxy=proxy,
            progress_callback=detail_callback, log_func=_log, stop_event=stop_event,
            download_archive_path=archive_path, enable_aria2=enable_aria2
        )

    if total == 1 or max_workers <= 1:
        ok, path, err = _task(id_list[0]);
        done_counter += 1
        if progress_callback: progress_callback(done_counter, total)
        results.append({'ID/URL': id_list[0], 'Trạng thái': 'OK' if ok else f'Error: {err}', 'Đường dẫn': path})
    else:
        workers = max(1, min(max_workers, 4))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_task, vid): vid for vid in id_list}
            for fut in as_completed(futures):
                vid = futures[fut]
                ok, path, err = fut.result();
                done_counter += 1
                if progress_callback: progress_callback(done_counter, total)
                results.append({'ID/URL': vid, 'Trạng thái': 'OK' if ok else f'Error: {err}', 'Đường dẫn': path})

    if total == 1: return None
    try:
        df_out = pd.DataFrame(results);
        df_out.insert(0, 'Số thứ tự', range(1, len(df_out) + 1))
        out_report = os.path.join(out_folder, 'Download_Report.xlsx');
        df_out.to_excel(out_report, index=False)
        _log(f'Đã lưu báo cáo: {out_report}');
        return out_report
    except Exception as e:
        _log(f'Lỗi lưu báo cáo: {e}');
        return None
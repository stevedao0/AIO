# Đóng gói AIO kèm FFmpeg (Windows)

## Chuẩn bị
1) Tạo thư mục `ffmpeg` cạnh `main.py`, chép vào đó:
   - `ffmpeg.exe`
   - `ffprobe.exe`
2) Cài gói:
   ```bash
   pip install -U -r requirements.txt
   ```

## Cách A — Flet pack (khuyến nghị)
```bat
flet pack main.py --name AIO --icon icon.ico --add-data "core;core" --add-data "ui;ui" --add-data "ffmpeg;ffmpeg"
```
> Bản Flet mới không dùng `--noconsole`. Mặc định app GUI sẽ không mở console.

## Cách B — PyInstaller
```bat
pyinstaller --noconsole --onefile --name AIO main.py ^
  --add-data "core;core" --add-data "ui;ui" --add-data "ffmpeg;ffmpeg"
```

## Vì sao không lỗi khi pack?
- `main.py` đã có **FFmpeg bootstrap**: tự thêm `./ffmpeg` vào `PATH` và đặt `FFMPEG_LOCATION` cho `yt_dlp`.
- `ScraperChecker.py` đã set `ffmpeg_location=os.environ['FFMPEG_LOCATION']` nếu có, nên hậu xử lý OK.
- `multiprocessing.freeze_support()` đã bật → Windows onefile an toàn.

## Lưu ý tải chất lượng cao
- Chọn preset chất lượng trong app (ví dụ `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best`). Nếu gặp 403/SABR, cân nhắc dùng cookies/PO token như wiki yt-dlp.

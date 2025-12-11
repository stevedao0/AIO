# -*- coding: utf-8 -*-
import os, io, time, threading, multiprocessing, sys
from pathlib import Path


# ---- FFmpeg bootstrap (bundle-friendly)
def _inject_ffmpeg_into_path():
    try:
        base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
        ffdir = os.path.join(base, "ffmpeg")
        if os.path.isdir(ffdir):
            os.environ["PATH"] = ffdir + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("FFMPEG_LOCATION", ffdir)
    except Exception:
        pass


_inject_ffmpeg_into_path()

import flet as ft
from flet import Colors, Icons, ThemeMode, FontWeight, padding, margin, ScrollMode
from ui.widgets import group_tile, sticky_actions, status_bar, two_pane
from core.ScraperChecker import run_scraper, run_checker, run_downloader


def main(page: ft.Page):
    page.title = "🚀 AIO ENHANCED • YouTube Scraper with ETA • Checker • Downloader"
    page.theme = ft.Theme(color_scheme_seed=Colors.ORANGE_200)
    page.theme_mode = ThemeMode.LIGHT
    page.bgcolor = Colors.GREY_50
    page.window_width = 1300  # Tăng width để chứa thêm info
    page.window_height = 950  # Tăng height

    # ===== AppBar với enhanced status =====
    def toggle_theme(_):
        page.theme_mode = ThemeMode.DARK if page.theme_mode == ThemeMode.LIGHT else ThemeMode.LIGHT
        theme_btn.icon = Icons.LIGHT_MODE if page.theme_mode == ThemeMode.LIGHT else Icons.DARK_MODE
        page.update()

    theme_btn = ft.IconButton(icon=Icons.LIGHT_MODE, tooltip="Chuyển giao diện", on_click=toggle_theme)

    ratio_dd = ft.Dropdown(
        label="Bố cục", value="2/3 : 1/3",
        options=[ft.dropdown.Option("2/3 : 1/3"), ft.dropdown.Option("1/2 : 1/2"), ft.dropdown.Option("1/3 : 2/3")],
        width=140
    )

    # Enhanced status indicator
    status_indicator = ft.Container(
        content=ft.Row([
            ft.Icon(Icons.SPEED, color=Colors.ORANGE, size=18),
            ft.Text("ENHANCED", size=12, weight=FontWeight.BOLD, color=Colors.ORANGE)
        ], spacing=4),
        bgcolor=Colors.ORANGE_50,
        border_radius=10,
        padding=padding.symmetric(horizontal=10, vertical=6),
        tooltip="Enhanced mode with ETA and detailed progress"
    )

    page.appbar = ft.AppBar(
        title=ft.Row([
            ft.Text("🚀 AIO ENHANCED", weight=FontWeight.BOLD, size=20),
            status_indicator,
            ft.Text("with ETA & Progress Tracking", size=16, style="italic")
        ], spacing=8),
        center_title=True, bgcolor=Colors.SURFACE, actions=[ratio_dd, theme_btn], elevation=2
    )

    # ===== Global variables =====
    output_dir = os.path.expanduser("~/Downloads");
    os.makedirs(output_dir, exist_ok=True)
    stop_event = threading.Event()
    log_buffer = io.StringIO()

    # ===== Enhanced logging =====
    def map_ratio(v: str):
        return {"2/3 : 1/3": (2, 1), "1/2 : 1/2": (1, 1), "1/3 : 2/3": (1, 2)}.get(v, (2, 1))

    def trim_log_if_needed():
        if len(log_list.controls) > 2000:
            del log_list.controls[:500]

    def log(msg, prefix=''):
        timestamp = time.strftime('%H:%M:%S')
        line = f"{timestamp} | {prefix} {msg}"
        log_buffer.write(line + "\n")

        # Enhanced styling với icons
        color = None
        weight = None
        icon = None

        if "🚀" in msg or "ENHANCED" in prefix:
            color = Colors.ORANGE_700
            weight = FontWeight.BOLD
        elif "✅" in msg or "SUCCESS" in msg:
            color = Colors.GREEN_700
            weight = FontWeight.W_500
        elif "⚠️" in msg or "WARNING" in msg:
            color = Colors.YELLOW_800
        elif "❌" in msg or "ERROR" in msg:
            color = Colors.RED_700
            weight = FontWeight.W_500
        elif "⏱️" in msg or "ETA" in msg:
            color = Colors.BLUE_700
        elif "📊" in msg or "Progress" in msg:
            color = Colors.PURPLE_700

        log_list.controls.append(ft.Text(
            line, size=12, font_family="Consolas",
            color=color, weight=weight
        ))
        trim_log_if_needed()
        page.update()

    # ===== ENHANCED Progress Tracking =====
    overall_text = ft.Text("0/0", size=14, weight=FontWeight.W_500)
    overall_bar = ft.ProgressBar(value=0, color=Colors.PRIMARY, expand=True, height=8)

    def overall_progress(done, total=0, *_):
        try:
            d, t = int(done), int(total)
        except:
            d, t = 0, 0
        overall_text.value = f"{d}/{t}"
        overall_bar.value = None if t == 0 else d / t
        page.update()

    # ===== DETAILED Progress Display =====
    current_title = ft.Text("Ready to start", size=14, weight=FontWeight.W_500)
    current_meta = ft.Text("", size=12, color=Colors.GREY_700)
    current_bar = ft.ProgressBar(value=0, color=Colors.AMBER, expand=True, height=6)

    # ETA and timing info
    eta_text = ft.Text("ETA: Calculating...", size=12, color=Colors.BLUE_700, weight=FontWeight.W_500)
    elapsed_text = ft.Text("Elapsed: 00:00:00", size=12, color=Colors.GREEN_700)
    rate_text = ft.Text("Rate: 0.0 items/s", size=12, color=Colors.PURPLE_700)

    # Current processing info
    current_item_text = ft.Text("", size=11, color=Colors.GREY_600, max_lines=2)
    batch_info_text = ft.Text("", size=11, color=Colors.GREY_500, style="italic")

    def detail_progress(data: dict):
        """Callback nhận detailed progress info"""
        if isinstance(data, dict):
            # Data từ enhanced progress tracker
            completed = data.get('completed', 0)
            total = data.get('total', 1)
            percentage = data.get('percentage', 0)
            current_item = data.get('current_item', '')
            batch_info = data.get('batch_info', '')
            elapsed = data.get('elapsed', '00:00:00')
            eta = data.get('eta', 'Calculating...')
            rate = data.get('rate', 0)

            # Update progress bar
            current_bar.value = max(0.0, min(1.0, percentage / 100))

            # Update text displays
            current_title.value = f"Processing: {completed}/{total} ({percentage:.1f}%)"
            eta_text.value = f"⏱️ ETA: {eta}"
            elapsed_text.value = f"🕐 Elapsed: {elapsed}"
            rate_text.value = f"⚡ Rate: {rate:.1f} items/s"
            current_item_text.value = current_item[:100] + "..." if len(current_item) > 100 else current_item
            batch_info_text.value = batch_info

        else:
            # Fallback cho download progress (old format)
            phase = data.get('phase', '') if hasattr(data, 'get') else ''
            if phase == 'downloading':
                p = data.get('percent');
                spd = data.get('speed');
                eta = data.get('eta')
                current_title.value = f"Downloading: {os.path.basename(data.get('filename', ''))}"
                current_bar.value = max(0.0, min(1.0, p if p is not None else 0.0))
                parts = []
                if p is not None: parts.append(f"{p * 100:0.1f}%")
                if spd: parts.append(f"{spd / 1024 / 1024:0.2f} MB/s")
                if eta: parts.append(f"ETA {int(eta)}s")
                current_meta.value = " · ".join(parts)
            elif phase == 'finished':
                current_title.value = "Download finished, post-processing..."
                current_bar.value = None
                current_meta.value = ""
            elif phase == 'postprocessing':
                current_title.value = "Post-processing (merge/convert/metadata)..."
                current_bar.value = None
                current_meta.value = ""

        page.update()

    # ===== File pickers =====
    file_picker = ft.FilePicker();
    d_file_picker = ft.FilePicker()
    cookies_picker = ft.FilePicker();
    scraper_cookies_picker = ft.FilePicker();
    folder_picker = ft.FilePicker()
    page.overlay.extend([file_picker, d_file_picker, cookies_picker, scraper_cookies_picker, folder_picker])

    def on_folder_chosen(e: ft.FilePickerResultEvent):
        nonlocal output_dir
        if e.path:
            output_dir = e.path
            scraper_out.value = output_dir;
            downloader_out.value = output_dir
            page.update()

    folder_picker.on_result = on_folder_chosen

    # ===== Left Pane: Enhanced Input Controls =====
    # --- Scraper
    scraper_channel = ft.TextField(label="URL / ID Kênh", expand=True, filled=True)
    scraper_out = ft.TextField(label="Thư mục xuất", expand=True, value=output_dir, disabled=True, filled=True)
    scraper_browse = ft.OutlinedButton("📁 Chọn thư mục...", icon=Icons.FOLDER,
                                       on_click=lambda _: folder_picker.get_directory_path(dialog_title="Chọn thư mục"))

    scraper_cookies_text = ft.TextField(label="cookies.txt (optional)", expand=True, read_only=True, value="")
    scraper_cookies_pick = ft.OutlinedButton("📁 Chọn cookies.txt", icon=Icons.FILE_OPEN,
                                     on_click=lambda _: scraper_cookies_picker.pick_files(allow_multiple=False,
                                                                                  dialog_title="Chọn cookies.txt",
                                                                                  allowed_extensions=['txt']))

    def on_scraper_cookies(e: ft.FilePickerResultEvent):
        if e.files: scraper_cookies_text.value = e.files[0].path; page.update()

    scraper_cookies_picker.on_result = on_scraper_cookies

    # Enhanced Turbo controls
    turbo_scraper_enabled = ft.Checkbox(label="🚀 Enhanced Mode", value=True,
                                        tooltip="Enhanced processing with detailed progress and ETA")
    scraper_workers = ft.Slider(
        min=2, max=16, divisions=14, value=8, label="Workers: {value}",
        tooltip="Parallel processing threads. Higher = faster but more resource usage"
    )

    def on_turbo_scraper_change(e):
        scraper_workers.disabled = not turbo_scraper_enabled.value
        if not turbo_scraper_enabled.value:
            scraper_workers.value = 4
        page.update()

    turbo_scraper_enabled.on_change = on_turbo_scraper_change

    scraper_panel = ft.Column([
        group_tile(Icons.LINK, "Channel Input", ft.Row([scraper_channel], spacing=8), expanded=True),
        group_tile(Icons.FOLDER, "Output Directory", ft.Row([scraper_out, scraper_browse], spacing=8), expanded=True),
        group_tile(Icons.SPEED, "⚡ Enhanced Settings",
                   ft.Column([
                       turbo_scraper_enabled,
                       ft.Row([
                           ft.Text("Workers:", size=12, width=70),
                           scraper_workers
                       ], spacing=8),
                       ft.Row([scraper_cookies_text, scraper_cookies_pick], spacing=8),
                   ], spacing=8),
                   expanded=False),
    ], scroll=ScrollMode.AUTO)

    # --- Checker
    checker_file_path = ""
    checker_file = ft.TextField(label="File .xlsx/.csv có cột 'ID Video'", expand=True, disabled=True, filled=True)
    checker_browse_file = ft.OutlinedButton("📁 Chọn file...", icon=Icons.FOLDER_OPEN,
                                            on_click=lambda _: file_picker.pick_files(allow_multiple=False,
                                                                                      dialog_title="Chọn file .xlsx/.csv",
                                                                                      allowed_extensions=['xlsx', 'xls',
                                                                                                          'csv']))

    def on_checker_file(e: ft.FilePickerResultEvent):
        nonlocal checker_file_path
        if e.files:
            checker_file_path = e.files[0].path;
            checker_file.value = checker_file_path;
            page.update()

    file_picker.on_result = on_checker_file

    # Enhanced Checker controls
    turbo_checker_enabled = ft.Checkbox(label="🚀 Enhanced Mode", value=True)
    checker_workers = ft.Slider(min=2, max=10, divisions=8, value=6, label="Workers: {value}")

    def on_turbo_checker_change(e):
        checker_workers.disabled = not turbo_checker_enabled.value
        if not turbo_checker_enabled.value:
            checker_workers.value = 3
        page.update()

    turbo_checker_enabled.on_change = on_turbo_checker_change

    checker_panel = ft.Column([
        group_tile(Icons.DESCRIPTION, "Input File", ft.Row([checker_file, checker_browse_file], spacing=8),
                   expanded=True),
        group_tile(Icons.FOLDER, "Output Directory", ft.Row([scraper_out, scraper_browse], spacing=8), expanded=False),
        group_tile(Icons.SPEED, "⚡ Enhanced Settings",
                   ft.Column([
                       turbo_checker_enabled,
                       ft.Row([
                           ft.Text("Workers:", size=12, width=70),
                           checker_workers
                       ], spacing=8)
                   ], spacing=8),
                   expanded=False),
    ], scroll=ScrollMode.AUTO)

    # --- Downloader (enhanced)
    downloader_input = ft.TextField(
        label="ID/URL Video • File (.xlsx/.csv) • Playlist/Channel URLs",
        expand=True, filled=True, multiline=True, max_lines=3
    )
    downloader_pick_file = ft.OutlinedButton("📁 Chọn file danh sách...", icon=Icons.ATTACH_FILE,
                                             on_click=lambda _: d_file_picker.pick_files(allow_multiple=False,
                                                                                         dialog_title="Chọn file .xlsx/.csv",
                                                                                         allowed_extensions=['xlsx',
                                                                                                             'xls',
                                                                                                             'csv']))

    def on_dl_file(e: ft.FilePickerResultEvent):
        if e.files: downloader_input.value = e.files[0].path; page.update()

    d_file_picker.on_result = on_dl_file

    quality = ft.Dropdown(
        label="Quality", expand=True,
        options=[
            ft.dropdown.Option("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", "Best Quality (MP4)"),
            ft.dropdown.Option("best", "Best Available"),
            ft.dropdown.Option("bestvideo+bestaudio/best", "Best Video+Audio"),
            ft.dropdown.Option("worst", "Worst Quality (Fast)")
        ],
        value="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
    )
    audio_only = ft.Checkbox(label="🎵 Audio only (MP3)", value=False)
    threads = ft.Slider(min=1, max=6, divisions=5, value=3, label="{value} threads")
    con_frags = ft.Slider(min=4, max=20, divisions=16, value=12, label="{value} fragments/thread")

    downloader_out = ft.TextField(label="Download Directory", expand=True, value=output_dir, disabled=True, filled=True)
    downloader_browse_out = ft.OutlinedButton("📁 Chọn thư mục...", icon=Icons.FOLDER,
                                              on_click=lambda _: folder_picker.get_directory_path(
                                                  dialog_title="Chọn thư mục tải về"))

    cookies_text = ft.TextField(label="cookies.txt (optional)", expand=True, read_only=True, value="")
    cookies_pick = ft.OutlinedButton("📁 Chọn cookies.txt", icon=Icons.FILE_OPEN,
                                     on_click=lambda _: cookies_picker.pick_files(allow_multiple=False,
                                                                                  dialog_title="Chọn cookies.txt",
                                                                                  allowed_extensions=['txt']))

    def on_cookies(e: ft.FilePickerResultEvent):
        if e.files: cookies_text.value = e.files[0].path; page.update()

    cookies_picker.on_result = on_cookies

    proxy_text = ft.TextField(label="Proxy (http://user:pass@host:port)", expand=True, value="")
    use_archive = ft.Checkbox(label="📝 Skip duplicates (archive)", value=True)
    use_aria2 = ft.Checkbox(label="🚀 Use aria2c if available", value=False)

    downloader_panel = ft.Column([
        group_tile(Icons.LINK, "Input", ft.Row([downloader_input, downloader_pick_file], spacing=8), expanded=True),
        group_tile(Icons.SETTINGS, "Quality & Format", ft.Row([quality, audio_only], spacing=8), expanded=True),
        group_tile(Icons.SPEED, "Performance", ft.Row([threads, con_frags], spacing=8), expanded=False),
        group_tile(Icons.SECURITY, "Advanced Options",
                   ft.Column([
                       ft.Row([cookies_text, cookies_pick], spacing=8),
                       ft.Row([proxy_text], spacing=8),
                       ft.Row([use_archive, use_aria2], spacing=16)
                   ], spacing=8), expanded=False),
        group_tile(Icons.FOLDER, "Output", ft.Row([downloader_out, downloader_browse_out], spacing=8), expanded=True),
    ], scroll=ScrollMode.AUTO)

    # ===== Tab controls =====
    tab_scraper = ft.Tab(text="🚀 Enhanced Scraper", icon=Icons.LIST)
    tab_checker = ft.Tab(text="⚡ Enhanced Checker", icon=Icons.CHECK_CIRCLE)
    tab_downloader = ft.Tab(text="📥 Downloader", icon=Icons.DOWNLOAD)
    tabs = ft.Tabs(tabs=[tab_scraper, tab_checker, tab_downloader], selected_index=0)

    left_panel = ft.Column([tabs], expand=True, spacing=10, scroll=ScrollMode.AUTO)

    def update_left_panel(_=None):
        left_panel.controls = [tabs,
                               scraper_panel if tabs.selected_index == 0 else
                               checker_panel if tabs.selected_index == 1 else
                               downloader_panel
                               ]
        page.update()

    tabs.on_change = update_left_panel
    update_left_panel()

    # ===== Right Pane: Enhanced Progress Display =====
    spinner = ft.ProgressRing(visible=False)
    start_btn = ft.FilledButton("🚀 START ENHANCED", icon=Icons.ROCKET_LAUNCH,
                                bgcolor=Colors.ORANGE, color=Colors.WHITE, height=55,
                                style=ft.ButtonStyle(text_style=ft.TextStyle(weight=FontWeight.BOLD, size=16)))
    cancel_btn = ft.OutlinedButton("⏹️ STOP", icon=Icons.STOP, height=40, on_click=lambda _: stop_event.set())
    clear_log_btn = ft.OutlinedButton("🗑️ Clear", icon=Icons.CLEAR, height=40,
                                      on_click=lambda _: (log_list.controls.clear(), page.update()))
    save_log_btn = ft.OutlinedButton("💾 Save Log", icon=Icons.SAVE, height=40, on_click=lambda _: save_log())

    def save_log():
        path = os.path.join(output_dir, f"enhanced_log_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(log_buffer.getvalue())
        log(f"📁 Log saved: {path}", "[System]")

    log_list = ft.ListView(expand=True, spacing=3, auto_scroll=True)

    # ===== Enhanced Performance Monitor =====
    perf_cpu = ft.Text("CPU: --%", size=11, color=Colors.BLUE_700, weight=FontWeight.W_500)
    perf_mem = ft.Text("RAM: --%", size=11, color=Colors.GREEN_700, weight=FontWeight.W_500)
    perf_temp = ft.Text("", size=10, color=Colors.GREY_600)

    def update_perf_monitor():
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent
            perf_cpu.value = f"CPU: {cpu:.1f}%"
            perf_mem.value = f"RAM: {memory:.1f}%"

            # Temperature warning
            if cpu > 80 or memory > 85:
                perf_temp.value = "⚠️ High usage"
                perf_temp.color = Colors.RED_600
            elif cpu > 60 or memory > 70:
                perf_temp.value = "⚡ Moderate usage"
                perf_temp.color = Colors.ORANGE_600
            else:
                perf_temp.value = "✅ Normal"
                perf_temp.color = Colors.GREEN_600

        except:
            perf_cpu.value = "CPU: N/A"
            perf_mem.value = "RAM: N/A"
            perf_temp.value = "Monitor unavailable"
        page.update()

    def perf_timer():
        while True:
            update_perf_monitor()
            time.sleep(2)

    threading.Thread(target=perf_timer, daemon=True).start()

    # ===== Enhanced Right Panel Layout =====
    right_panel = ft.Column([
        # Current progress with detailed info
        group_tile(Icons.TIMER, "📊 Current Progress",
                   ft.Column([
                       current_title,
                       ft.Container(current_bar, padding=padding.only(top=6, bottom=6)),
                       current_meta,
                       ft.Divider(height=1, color=Colors.GREY_300),
                       ft.Row([
                           current_item_text
                       ], spacing=8),
                       ft.Row([
                           batch_info_text
                       ], spacing=8)
                   ], spacing=4),
                   expanded=True),

        # Overall progress
        group_tile(Icons.ANALYTICS, "📈 Overall Progress",
                   status_bar(overall_text, overall_bar),
                   expanded=True),

        # Enhanced timing info
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(Icons.ACCESS_TIME, size=16, color=Colors.BLUE),
                        ft.Text("Progress Timing", size=14, weight=FontWeight.W_500)
                    ], spacing=8),
                    ft.Divider(height=1, color=Colors.GREY_300),
                    ft.Row([elapsed_text, eta_text], spacing=16),
                    ft.Row([rate_text], spacing=8)
                ], spacing=6),
                padding=padding.all(12)
            ),
            elevation=1,
            shape=ft.RoundedRectangleBorder(radius=12),
            margin=margin.only(bottom=8)
        ),

        # System performance
        ft.Container(
            content=ft.Row([
                ft.Icon(Icons.MONITOR, size=16, color=Colors.PURPLE),
                ft.Text("System:", size=12, weight=FontWeight.W_500),
                perf_cpu, perf_mem, perf_temp
            ], spacing=8),
            bgcolor=Colors.PURPLE_50,
            padding=padding.all(10),
            border_radius=10,
            margin=margin.only(bottom=12)
        ),

        # Action buttons
        sticky_actions([start_btn, cancel_btn], [clear_log_btn, save_log_btn]),

        # Enhanced log display
        ft.Card(
            content=ft.Container(
                content=log_list,
                height=340,  # Slightly smaller to fit timing info
                padding=8
            ),
            elevation=1,
            margin=margin.only(top=8),
            shape=ft.RoundedRectangleBorder(radius=12)
        ),
    ], expand=True, spacing=12, scroll=ScrollMode.AUTO)

    # ===== Combine as 2-pane =====
    left_w, right_w = map_ratio(ratio_dd.value)
    root_row = two_pane(left=left_panel, right=right_panel, left_expand=left_w, right_expand=right_w)

    def on_ratio_change(e):
        lw, rw = map_ratio(ratio_dd.value)
        root_row.controls[0].expand = lw
        root_row.controls[1].expand = rw
        page.update()

    ratio_dd.on_change = on_ratio_change

    # ===== Page body =====
    page.add(ft.Container(content=root_row, padding=padding.all(12), expand=True))

    # ===== Enhanced Actions =====
    def on_start(_=None):
        stop_event.clear()
        # Reset UI
        current_title.value = "Initializing enhanced mode..."
        current_meta.value = ""
        current_bar.value = 0
        overall_progress(0, 0)
        spinner.visible = True;
        start_btn.disabled = True

        # Reset timing displays
        eta_text.value = "⏱️ ETA: Calculating..."
        elapsed_text.value = "🕐 Elapsed: 00:00:00"
        rate_text.value = "⚡ Rate: 0.0 items/s"
        current_item_text.value = ""
        batch_info_text.value = ""

        # Update start button
        start_btn.text = "🔥 ENHANCED RUNNING..."
        start_btn.bgcolor = Colors.RED
        page.update()

        def work():
            try:
                if tabs.selected_index == 0:  # ENHANCED SCRAPER
                    if not scraper_channel.value.strip():
                        log("❌ Missing channel input.", "[Error]");
                        return

                    log("🚀 Starting ENHANCED SCRAPER with detailed progress tracking...", "[EnhancedScraper]")

                    # ===== ENHANCED SCRAPER CALL với detail_callback =====
                    res = run_scraper(
                        scraper_channel.value.strip(),
                        scraper_out.value,
                        log_func=log,
                        progress_callback=overall_progress,
                        detail_callback=detail_progress,  # ⭐ NEW: Detailed callback
                        stop_event=stop_event,
                        turbo_mode=turbo_scraper_enabled.value,
                        max_workers=int(scraper_workers.value) if turbo_scraper_enabled.value else 4,
                        cookies_file=scraper_cookies_text.value or None
                    )

                elif tabs.selected_index == 1:  # ENHANCED CHECKER
                    if not checker_file.value.strip():
                        log("❌ Missing input file.", "[Error]");
                        return

                    log("⚡ Starting ENHANCED CHECKER with progress tracking...", "[EnhancedChecker]")

                    # ===== ENHANCED CHECKER CALL với detail_callback =====
                    res = run_checker(
                        checker_file.value,
                        max_workers=int(checker_workers.value) if turbo_checker_enabled.value else 3,
                        progress_callback=overall_progress,
                        detail_callback=detail_progress,  # ⭐ NEW: Detailed callback
                        log_func=log,
                        stop_event=stop_event,
                        turbo_mode=turbo_checker_enabled.value
                    )

                else:  # ENHANCED DOWNLOADER
                    if not downloader_input.value.strip():
                        log("❌ Missing download input.", "[Error]");
                        return

                    log("📥 Starting ENHANCED DOWNLOADER...", "[EnhancedDownloader]")

                    # ===== ENHANCED DOWNLOADER CALL =====
                    res = run_downloader(
                        downloader_input.value.strip(), out_folder=downloader_out.value,
                        quality=quality.value, audio_only=audio_only.value,
                        max_workers=int(threads.value), concurrent_frags=int(con_frags.value),
                        cookies_file=cookies_text.value or None, proxy=proxy_text.value or None,
                        progress_callback=overall_progress, detail_callback=detail_progress,
                        log_func=log, enable_aria2=use_aria2.value, use_archive=use_archive.value,
                        stop_event=stop_event
                    )

                if res:
                    log(f"🎉 Result file: {res}", "[System]")
                if stop_event.is_set():
                    log("⏹️ Stopped by user request.", "[System]")
                else:
                    log("✅ ENHANCED PROCESSING COMPLETE!", "[System]")

                # Final progress update
                current_title.value = "✅ Processing complete!"
                current_bar.value = 1.0
                eta_text.value = "⏱️ ETA: Complete"
                rate_text.value = "⚡ Rate: Finished"

            except Exception as e:
                log(f"💥 Error: {str(e)}", "[Error]")
                current_title.value = f"❌ Error: {str(e)[:50]}"
                current_bar.value = 0
            finally:
                spinner.visible = False
                start_btn.disabled = False
                start_btn.text = "🚀 START ENHANCED"
                start_btn.bgcolor = Colors.ORANGE
                page.update()

        threading.Thread(target=work, daemon=True).start()

    start_btn.on_click = on_start

    # Welcome messages
    log("🚀 ENHANCED MODE ACTIVATED! Welcome to AIO Enhanced Edition.", "[System]")
    log("⚡ Features: Real-time ETA, detailed progress tracking, and enhanced logging.", "[System]")
    log("💡 Pro tip: Monitor system resources and adjust workers accordingly.", "[System]")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    ft.app(target=main)
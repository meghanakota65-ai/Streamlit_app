
import numpy as np
from PIL import Image, ImageDraw
import uharfbuzz as hb
import freetype
import math
import unicodedata
import re
import streamlit as st
import os
import tempfile

def _clean_ticker_text(text: str) -> str:
    """Remove characters unsupported by NotoSansTelugu to prevent □ boxes."""
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)
    # Remove or replace English numerals with Telugu numerals (optional)
    # Remove bullet/list markers that render as boxes
    text = re.sub(r'[\u2460-\u2473]', '', text)   # ①②③ circled numbers
    text = re.sub(r'[\u25a0-\u25ff]', '', text)   # geometric shapes
    text = re.sub(r'[\u2580-\u259f]', '', text)   # block elements
    # Normalize unicode (NFC is correct for Telugu)
    text = unicodedata.normalize('NFC', text)
    # Collapse multiple spaces/newlines into single space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Ramabhadra-Regular.ttf")

st.set_page_config(
    page_title="Telugu Video Editor",
    page_icon="🎬",
    layout="wide",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 24px;
        font-family: 'Segoe UI', sans-serif;
    }
    .section-card {
        background: #f8f9fa;
        border-left: 4px solid #e63946;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .preview-box {
        background: #000;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    /* Remove black border/gap around st.video player */
    [data-testid="stVideo"] {
        padding: 0 !important;
        margin: 0 !important;
        line-height: 0 !important;
    }
    [data-testid="stVideo"] video {
        display: block !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        outline: none !important;
        background: transparent !important;
    }
    [data-testid="stVideo"] > div {
        padding: 0 !important;
        margin: 0 !important;
        line-height: 0 !important;
        background: transparent !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #e63946, #c1121f);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: bold;
        font-size: 16px;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #c1121f, #9d0208);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎬 Telugu Video Broadcaster</h1>
    <p>Add Telugu scrolling text, logo, and intro to your news videos</p>
</div>
""", unsafe_allow_html=True)

# ─── Telugu rendering helper ───────────────────────────────────────────────

def render_telugu_line(text: str, font_size: int, color: tuple, padding_x: int = 12) -> np.ndarray:
    """Render Telugu text using HarfBuzz shaping + FreeType into an RGBA numpy array.

    THE KEY BUG FIX: FreeType's Bitmap object is a live C pointer into the glyph slot.
    Every load_glyph() call overwrites it — so storing 'bm' as a reference means
    ALL glyphs in the list end up with the LAST glyph's bitmap data (wrong pixels,
    wrong dimensions), producing the garbled repeated-shape output.
    Fix: immediately call int(bm.rows), int(bm.width), bytes(bm.buffer) to force
    Python copies before the next load_glyph() overwrites the slot.
    """

    # ── HarfBuzz setup ─────────────────────────────────────────────
    blob    = hb.Blob.from_file_path(FONT_PATH)
    face_hb = hb.Face(blob)
    hb_font = hb.Font(face_hb)
    upem    = face_hb.upem
    hb_font.scale = (upem, upem)   # output advances in raw font units

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})

    infos     = buf.glyph_infos
    positions = buf.glyph_positions

    # ── FreeType setup ─────────────────────────────────────────────
    face_ft = freetype.Face(FONT_PATH)
    face_ft.set_pixel_sizes(0, font_size)
    scale = font_size / upem       # font units → pixels

    # ── First pass: collect glyph data + measure canvas bounds ─────
    pen_x      = 0
    glyph_data = []
    min_bx     = 0
    max_right  = 0
    max_top    = 0
    max_bot    = 0

    for info, pos in zip(infos, positions):
        face_ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        g  = face_ft.glyph
        bm = g.bitmap

        # *** THE FIX: copy to plain Python scalars/bytes RIGHT NOW ***
        # bm is a live C pointer — next load_glyph() overwrites all its fields
        bm_rows  = int(bm.rows)
        bm_width = int(bm.width)
        bm_buf   = bytes(bm.buffer)   # force real pixel data copy
        bl       = int(g.bitmap_left)
        bt       = int(g.bitmap_top)

        x_off = int(round(pos.x_offset  * scale))
        y_off = int(round(pos.y_offset  * scale))
        x_adv = int(round(pos.x_advance * scale))

        bx         = pen_x + x_off + bl
        bitmap_top = bt + y_off

        glyph_data.append({
            "bm_buf":    bm_buf,
            "bm_rows":   bm_rows,
            "bm_width":  bm_width,
            "bx":        bx,
            "bitmap_top": bitmap_top,
        })

        if bm_rows > 0 and bm_width > 0:
            min_bx    = min(min_bx,    bx)
            max_right = max(max_right, bx + bm_width)
            max_top   = max(max_top,   bitmap_top)
            max_bot   = max(max_bot,   bm_rows - bitmap_top)

        pen_x += x_adv

    # ── Compute canvas dimensions ──────────────────────────────────
    shift_x  = padding_x - min(0, min_bx)
    baseline = max_top + 4
    total_h  = max(1, baseline + max_bot + 4)
    total_w  = max(1, int(max_right + shift_x + padding_x),
                   pen_x + shift_x + padding_x)

    canvas = np.zeros((total_h, total_w, 4), dtype=np.uint8)

    # ── Second pass: paint each glyph ─────────────────────────────
    for gd in glyph_data:
        if gd["bm_width"] == 0 or gd["bm_rows"] == 0:
            continue

        arr = np.frombuffer(gd["bm_buf"], dtype=np.uint8).reshape(
                  gd["bm_rows"], gd["bm_width"])

        bx = gd["bx"] + shift_x
        by = baseline - gd["bitmap_top"]

        r1 = max(0, by);  r2 = min(total_h, by + gd["bm_rows"])
        c1 = max(0, bx);  c2 = min(total_w, bx + gd["bm_width"])
        ar1 = r1 - by;    ar2 = ar1 + (r2 - r1)
        ac1 = c1 - bx;    ac2 = ac1 + (c2 - c1)

        if r2 <= r1 or c2 <= c1:
            continue

        alpha_slice = arr[ar1:ar2, ac1:ac2]
        canvas[r1:r2, c1:c2, 0] = color[0]
        canvas[r1:r2, c1:c2, 1] = color[1]
        canvas[r1:r2, c1:c2, 2] = color[2]
        # max-blend so overlapping Telugu matras combine correctly
        canvas[r1:r2, c1:c2, 3] = np.maximum(
            canvas[r1:r2, c1:c2, 3], alpha_slice)

    return canvas


def make_ticker_frame(
    red_text: str, blue_text: str, frame_w: int, bar_h: int,
    t: float, scroll_speed: float = 150, font_size: int = 28
) -> np.ndarray:
    """Build one ticker bar frame (RGBA) with red label + scrolling blue text."""
    bar = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)

    # font_size comes from parameter — no longer hardcoded

    red_w = int(frame_w * 0.28)
    slant = bar_h  # 45° slant

    # Fill entire bar blue first
    bar[:, :, 0] = 8
    bar[:, :, 1] = 34
    bar[:, :, 2] = 94
    bar[:, :, 3] = 255

    # Draw red parallelogram with slanted right edge
    for row in range(bar_h):
        slant_offset = int(slant * row / bar_h)
        end_x = min(frame_w, red_w + slant_offset)
        bar[row, :end_x, 0] = 186
        bar[row, :end_x, 1] = 48
        bar[row, :end_x, 2] = 36
        bar[row, :end_x, 3] = 255

    # Render red label text
    if red_text.strip():
        r_img = render_telugu_line(_clean_ticker_text(red_text), font_size, (255, 255, 255))
        rh, rw = r_img.shape[:2]
        # If text wider than red box, shrink font until it fits
        shrink_font = font_size
        while rw > red_w - 8 and shrink_font > 10:
            shrink_font -= 2
            r_img = render_telugu_line(red_text, shrink_font, (255, 255, 255))
            rh, rw = r_img.shape[:2]
        ry = max(0, (bar_h - rh) // 2)
        rx = max(4, (red_w - rw) // 2)  # at least 4px left padding
        paste_rgba(bar, r_img, ry, rx, clamp_w=red_w)

    # Render blue scrolling text — continuous seamless ticker
    if blue_text.strip():
        b_img = render_telugu_line(_clean_ticker_text(blue_text), font_size, (255, 255, 255))
        bh, bw = b_img.shape[:2]
        by = max(0, (bar_h - bh) // 2)
        blue_area_w = frame_w - red_w
        gap = 60
        tile_w = bw + gap
        scrolled = int(t * scroll_speed)
        phase = scrolled % tile_w
        num_tiles = (blue_area_w // tile_w) + 3

        # Temp canvas for blue text
        blue_canvas = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
        for tile_i in range(-1, num_tiles + 1):
            bx = red_w + blue_area_w - phase + tile_i * tile_w
            if bx + bw < red_w or bx > frame_w:
                continue
            paste_rgba(blue_canvas, b_img, by, bx, clip_left=0, clip_right=frame_w)

        # Mask out pixels left of the diagonal slant edge, row by row
        for row in range(bar_h):
            cutoff = min(frame_w, red_w + int(slant * row / bar_h)) + 4
            blue_canvas[row, :cutoff, :] = 0

        # Composite onto bar
        alpha_b = blue_canvas[:, :, 3:4] / 255.0
        for c in range(3):
            bar[:, :, c] = (
                blue_canvas[:, :, c] * alpha_b[:, :, 0] +
                bar[:, :, c] * (1 - alpha_b[:, :, 0])
            ).astype(np.uint8)
        bar[:, :, 3] = np.maximum(bar[:, :, 3], blue_canvas[:, :, 3])

    return bar
def make_ticker_frame_cached(
    red_img: np.ndarray, blue_img: np.ndarray,
    frame_w: int, bar_h: int,
    t: float, scroll_speed: float = 150
) -> np.ndarray:
    """Fast ticker frame builder using pre-rendered text images — no font calls."""
    bar = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)

    red_w = int(frame_w * 0.28)
    slant = int(bar_h * 0.6)  # slant width in pixels

    # Fill entire bar blue
    bar[:, :, 0] = 8
    bar[:, :, 1] = 34
    bar[:, :, 2] = 94
    bar[:, :, 3] = 255

    # Draw red parallelogram row by row
    # Top row: red ends at red_w; bottom row: red ends at red_w + slant
    for row in range(bar_h):
        slant_offset = int(slant * row / bar_h)
        end_x = min(frame_w, red_w + slant_offset)
        bar[row, :end_x, 0] = 186
        bar[row, :end_x, 1] = 48
        bar[row, :end_x, 2] = 36
        bar[row, :end_x, 3] = 255

    # Paste pre-rendered red label — centered in safe red zone (before slant starts)
    rh, rw = red_img.shape[:2]
    ry = max(0, (bar_h - rh) // 2)
    rx = max(4, (red_w - rw) // 2)
    paste_rgba(bar, red_img, ry, rx, clamp_w=red_w - 4)

    # Build per-row blue clip mask — blue text only visible RIGHT of slant edge
    # slant_x[row] = red_w + slant_offset for that row
    slant_x_per_row = np.array([
        min(frame_w, red_w + int(slant * row / bar_h))
        for row in range(bar_h)
    ], dtype=np.int32)

    # Render blue text onto a temp canvas, then mask out the slant zone
    bh, bw = blue_img.shape[:2]
    by = max(0, (bar_h - bh) // 2)
    blue_area_w = frame_w - red_w
    gap = 60
    tile_w = bw + gap
    scrolled = int(t * scroll_speed)
    phase = scrolled % tile_w
    num_tiles = (blue_area_w // tile_w) + 3

    # Temp canvas for blue text only
    blue_canvas = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
    for tile_i in range(-1, num_tiles + 1):
        bx = red_w + blue_area_w - phase + tile_i * tile_w
        if bx + bw < red_w or bx > frame_w:
            continue
        paste_rgba(blue_canvas, blue_img, by, bx, clip_left=0, clip_right=frame_w)

    # Apply diagonal mask: zero out any blue pixel left of slant edge for that row
    for row in range(bar_h):
        cutoff = slant_x_per_row[row] + 4  # 4px padding after slant edge
        blue_canvas[row, :cutoff, :] = 0

    # Composite blue canvas onto bar
    alpha = blue_canvas[:, :, 3:4] / 255.0
    for c in range(3):
        bar[:, :, c] = (
            blue_canvas[:, :, c] * alpha[:, :, 0] +
            bar[:, :, c] * (1 - alpha[:, :, 0])
        ).astype(np.uint8)
    bar[:, :, 3] = np.maximum(bar[:, :, 3], blue_canvas[:, :, 3])

    return bar


def paste_rgba(canvas: np.ndarray, src: np.ndarray, y: int, x: int,
               clamp_w: int = None, clip_left: int = 0, clip_right: int = None):
    """Alpha-composite src onto canvas at (y, x)."""
    sh, sw = src.shape[:2]
    ch, cw = canvas.shape[:2]
    if clip_right is None:
        clip_right = cw

    r1 = max(0, y); r2 = min(ch, y + sh)
    c1 = max(clip_left, x); c2 = min(clip_right, x + sw)
    if clamp_w:
        c2 = min(c2, clamp_w)

    if r1 >= r2 or c1 >= c2:
        return

    sr1 = r1 - y; sr2 = sr1 + (r2 - r1)
    sc1 = c1 - x; sc2 = sc1 + (c2 - c1)

    src_crop = src[sr1:sr2, sc1:sc2]
    alpha = src_crop[:, :, 3:4] / 255.0
    for c in range(3):
        canvas[r1:r2, c1:c2, c] = (
            src_crop[:, :, c] * alpha[:, :, 0] +
            canvas[r1:r2, c1:c2, c] * (1 - alpha[:, :, 0])
        ).astype(np.uint8)
    canvas[r1:r2, c1:c2, 3] = np.maximum(
        canvas[r1:r2, c1:c2, 3],
        src_crop[:, :, 3]
    )


# ─── Sidebar: all inputs ───────────────────────────────────────────────────

with st.sidebar:
    st.header("📁 Upload Files")
    main_video = st.file_uploader("Main Video", type=["mp4", "avi", "mov", "mkv"])
    intro_video = st.file_uploader("Intro Video (optional)", type=["mp4", "avi", "mov", "mkv"])
    logo_file = st.file_uploader("Logo / Watermark (PNG/GIF)", type=["png", "jpg", "jpeg", "gif"])

    st.header("📝 Ticker Bar Text")

    red_label = st.text_area(
        "🟥 Red Box Label Text",
        value="నెల్లూరు జిల్లా వార్తలు",
        height=80,
        help="Short label shown in the red section (left side)"
    )

    blue_scroll = st.text_area(
        "🔵 Blue Scrolling Text",
        value="రహాదారి విస్తరణ, మౌలిక వసతుల మెరుగుదల  •  నగర అభివృద్ధి పనుల ప్రారంభం  •  గుంటూరు స్మార్ట్ సిటీ కొత్త ప్రాజెక్టులు",
        height=100,
        help="Text that scrolls from right to left. Use only Telugu/English text — avoid numbered lists (1. 2.) or special symbols which may render as □ boxes."
    )

    st.header("⚙️ Settings")
    scroll_speed = st.slider("Scroll Speed (px/sec)", 50, 400, 150)
    ticker_height = st.slider("Ticker Bar Height (px)", 40, 100, 60)
    ticker_font_size = st.slider("Ticker Font Size (px)", 10, 60, 28)

    logo_position = st.selectbox("Logo Position", ["Top Right", "Top Left", "Bottom Right", "Bottom Left"])
    logo_scale = st.slider("Logo Size (%)", 5, 30, 12)

    st.header("💾 Output")
    output_fps = st.selectbox("Output FPS", [24, 25, 30], index=2)
    output_quality = st.selectbox("Output Quality", ["high", "medium", "low"], index=1)


# ─── Main panel ────────────────────────────────────────────────────────────

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🎬 Process Video")

    if main_video:
        st.success(f"✅ Main video loaded: **{main_video.name}**")
    else:
        st.info("👈 Upload your main video in the sidebar to get started.")

    if intro_video:
        st.success(f"✅ Intro video loaded: **{intro_video.name}**")

    if logo_file:
        logo_img = Image.open(logo_file)
        # For GIF, extract first frame for preview
        if getattr(logo_img, "is_animated", False) or logo_img.format == "GIF":
            logo_img.seek(0)
        logo_img = logo_img.convert("RGBA")
        st.image(logo_img, caption="Logo Preview", width=120)

with col2:
    st.subheader("📋 Ticker Preview")
    try:
        prev_w, prev_h = 600, ticker_height * 2
        preview = make_ticker_frame(red_label, blue_scroll, prev_w, prev_h, t=0.5, scroll_speed=scroll_speed, font_size=ticker_font_size)
        preview_img = Image.fromarray(preview, "RGBA")
        bg = Image.new("RGB", preview_img.size, (30, 30, 30))
        bg.paste(preview_img, mask=preview_img.split()[3])
        st.image(bg, caption="Ticker bar preview", width="stretch")
    except Exception as e:
        st.warning(f"Preview error: {e}")


st.divider()

process_btn = st.button("🚀 Process & Export Video", disabled=(main_video is None))

if process_btn and main_video:
    progress = st.progress(0, text="Initializing…")
    status = st.empty()

    try:
        import subprocess
        import json
        import time

        tmp_dir = tempfile.mkdtemp()

        def ffprobe_info(path):
            """Get width, height, duration using ffprobe — no Python video decoder."""
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", path
            ], capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
            w = int(video_stream["width"])
            h = int(video_stream["height"])
            dur = float(data["format"]["duration"])
            return w, h, dur

        # ── Save uploaded files ────────────────────────────────────────
        main_path = os.path.join(tmp_dir, "main.mp4")
        t0 = time.time()
        with open(main_path, "wb") as f:
            f.write(main_video.read())

        status.info("Reading video info…")
        progress.progress(10, text="Reading video info…")
        W, H, main_duration = ffprobe_info(main_path)

        # Auto-detect and remove baked-in black bars (pillarbox/letterbox)
        status.info("Detecting black bars…")
        crop_result = subprocess.run([
            "ffmpeg", "-y", "-ss", "5", "-i", main_path,
            "-t", "5", "-vf", "cropdetect=24:16:0",
            "-f", "null", "-"
        ], capture_output=True, text=True)
        crop_params = None
        for line in reversed(crop_result.stderr.splitlines()):
            if "crop=" in line:
                import re as _re
                m = _re.search(r'crop=(\d+:\d+:\d+:\d+)', line)
                if m:
                    crop_params = m.group(1)
                    break
        if crop_params:
            cw, ch, cx, cy = map(int, crop_params.split(":"))
            # Only apply crop if it actually removes bars (>2% difference)
            if cw < W * 0.98 or ch < H * 0.98:
                status.info(f"Black bars detected — cropping {W}x{H} → {cw}x{ch}")
                cropped_path = os.path.join(tmp_dir, "main_cropped.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-i", main_path,
                    "-vf", f"crop={crop_params},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                    "-c:a", "copy", cropped_path
                ], check=True, capture_output=True)
                main_path = cropped_path
            else:
                status.info("No significant black bars detected.")
        else:
            status.info("cropdetect found nothing — skipping.")

        intro_duration = 0.0
        intro_path = None
        if intro_video:
            status.info("Saving intro video…")
            progress.progress(15, text="Saving intro…")
            intro_path = os.path.join(tmp_dir, "intro.mp4")
            with open(intro_path, "wb") as f:
                f.write(intro_video.read())
            _, _, intro_duration = ffprobe_info(intro_path)

        bar_h = ticker_height
        bitrate_map = {"high": "8000k", "medium": "4000k", "low": "2000k"}
        out_path = os.path.join(tmp_dir, "output.mp4")

        status.info(f"✅ Video info read in {time.time()-t0:.1f}s — {W}x{H}, {main_duration:.1f}s")

        # ── Step 1: No pre-concat — intro+main joined in final filter_complex ─
        # base_path is always just main; intro handled inline in filter_complex
        base_path = main_path

        # ── Step 2: Pre-render ticker strip as video file ──────────────
        t2 = time.time()
        status.info("Pre-rendering Telugu ticker…")
        progress.progress(35, text="Rendering ticker frames…")

        TICKER_FPS = 10  # 10fps is visually smooth enough for a ticker bar
        blue_text_img = render_telugu_line(blue_scroll, ticker_font_size, (255, 255, 255))
        text_w = blue_text_img.shape[1]
        blue_area_w = W - int(W * 0.28)
        gap = 60
        tile_w = text_w + gap
        scroll_period = tile_w / scroll_speed  # one tile cycle = seamless loop
        total_ticker_frames = max(30, int(scroll_period * TICKER_FPS))

        # H264 requires even width and height
        ticker_W = W if W % 2 == 0 else W - 1
        ticker_H = bar_h if bar_h % 2 == 0 else bar_h + 1

        ticker_path = os.path.join(tmp_dir, "ticker.mp4")
        ticker_stderr_path = os.path.join(tmp_dir, "ticker_ffmpeg.log")
        ticker_log = open(ticker_stderr_path, "wb")

        ffmpeg_ticker = subprocess.Popen([
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{ticker_W}x{ticker_H}",
            "-pix_fmt", "rgb24",
            "-r", str(TICKER_FPS),
            "-i", "pipe:0",
            "-vcodec", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast", ticker_path
        ], stdin=subprocess.PIPE, stderr=ticker_log)

        # Pre-render both text images ONCE before the loop
        red_img_cached = render_telugu_line(_clean_ticker_text(red_label), ticker_font_size, (255, 255, 255))
        blue_img_cached = render_telugu_line(_clean_ticker_text(blue_scroll), ticker_font_size, (255, 255, 255))

        # Shrink red label if too wide — do this once too
        red_w_box = int(ticker_W * 0.28)
        shrink_font = ticker_font_size
        rh, rw = red_img_cached.shape[:2]
        while rw > red_w_box - 8 and shrink_font > 10:
            shrink_font -= 2
            red_img_cached = render_telugu_line(_clean_ticker_text(red_label), shrink_font, (255, 255, 255))
            rh, rw = red_img_cached.shape[:2]

        pipe_ok = True
        for i in range(total_ticker_frames):
            t_sample = i / TICKER_FPS
            frame = make_ticker_frame_cached(
                red_img_cached, blue_img_cached, ticker_W, ticker_H,
                t_sample, scroll_speed
            )[:, :, :3]
            # Ensure frame is exactly the right size before writing
            if frame.shape[0] != ticker_H or frame.shape[1] != ticker_W:
                frame = np.pad(frame,
                    ((0, ticker_H - frame.shape[0]),
                     (0, ticker_W - frame.shape[1]),
                     (0, 0)), mode='edge')
            try:
                ffmpeg_ticker.stdin.write(frame.tobytes())
            except OSError as pipe_err:
                pipe_ok = False
                status.error(f"Pipe broke at frame {i}: {pipe_err}")
                break

        ffmpeg_ticker.stdin.close()
        ret = ffmpeg_ticker.wait()
        ticker_log.close()

        if ret != 0 or not pipe_ok:
            with open(ticker_stderr_path, "r", errors="replace") as f:
                ffmpeg_log_text = f.read()
            st.error("❌ FFmpeg ticker encoding failed. Log:")
            st.code(ffmpeg_log_text[-3000:])  # last 3000 chars
            st.stop()

        progress.progress(55, text="Ticker rendered…")
        status.info(f"✅ Ticker rendered {total_ticker_frames} frames in {time.time()-t2:.1f}s")

        # ── Step 3: Prepare logo if provided ──────────────────────────
        logo_filter = ""
        logo_input_args = []
        logo_map = ""

        is_gif = False
        if logo_file:
            status.info("Preparing logo…")
            progress.progress(60, text="Preparing logo…")
            logo_file.seek(0)
            logo_pil = Image.open(logo_file)
            is_gif = getattr(logo_pil, "is_animated", False) or logo_file.name.lower().endswith(".gif")

            # Get dimensions from frame 0
            logo_pil.seek(0)
            logo_pil_frame = logo_pil.convert("RGBA")
            logo_w_target = int(W * logo_scale / 100)
            ratio = logo_w_target / logo_pil_frame.width
            logo_h_target = int(logo_pil_frame.height * ratio)

            pos_map = {
                "Top Right":    (W - logo_w_target - 10, 10),
                "Top Left":     (10, 10),
                "Bottom Right": (W - logo_w_target - 10, H - bar_h - logo_h_target - 10),
                "Bottom Left":  (10, H - bar_h - logo_h_target - 10),
            }
            lx, ly = pos_map[logo_position]

            if is_gif:
                # Save GIF directly — FFmpeg reads GIF natively with alpha
                logo_gif_path = os.path.join(tmp_dir, "logo_anim.gif")
                logo_file.seek(0)
                with open(logo_gif_path, "wb") as gf:
                    gf.write(logo_file.read())

                # Resize via FFmpeg filter instead of Python
                logo_input_args = ["-stream_loop", "-1", "-i", logo_gif_path]
            else:
                # Static image — same as before
                logo_pil_frame = logo_pil_frame.resize((logo_w_target, logo_h_target), Image.LANCZOS)
                logo_png_path = os.path.join(tmp_dir, "logo.png")
                logo_pil_frame.save(logo_png_path)
                logo_input_args = ["-i", logo_png_path]

        # ── Step 4: FFmpeg composite — ticker on main only, logo on main only ─
        status.info("Compositing with FFmpeg…")
        progress.progress(70, text="FFmpeg compositing…")

        # ticker starts at intro_duration, loops for main_duration
        ticker_start = intro_duration

        if logo_file:
            if is_gif:
                gif_logo_filter = f"scale={logo_w_target}:{logo_h_target},format=rgba,setpts=PTS-STARTPTS"
            else:
                gif_logo_filter = "setpts=PTS-STARTPTS"
            if intro_path:
                # input 0=intro, 1=main, 2=ticker, 3=logo
                filter_complex = (
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[iv];"
                    f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[mv];"
                    f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ia];"
                    f"[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ma];"
                    f"[iv][ia][mv][ma]concat=n=2:v=1:a=1[cv][ca];"
                    f"[2:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                    f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                    f"[cv][ticker]overlay=0:H-{ticker_H}:enable='gte(t,{ticker_start})'[v1];"
                    f"[3:v]{gif_logo_filter}[logo];"
                    f"[v1][logo]overlay={lx}:{ly}:shortest=1:enable='gte(t,{ticker_start})'[vout]"
                )
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", intro_path,
                    "-i", base_path,
                    "-i", ticker_path,
                    *logo_input_args,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[ca]",
                    "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-r", str(output_fps),
                    "-preset", "ultrafast", out_path
                ]
            else:
                # input 0=main, 1=ticker, 2=logo
                filter_complex = (
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[scaled];"
                    f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                    f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                    f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                    f"[scaled][ticker]overlay=0:H-{ticker_H}[v1];"
                    f"[2:v]{gif_logo_filter}[logo];"
                    f"[v1][logo]overlay={lx}:{ly}:shortest=1[vout]"
                )
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", base_path,
                    "-i", ticker_path,
                    *logo_input_args,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[ca]",
                    "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-r", str(output_fps),
                    "-preset", "ultrafast", out_path
                ]
        else:
            if intro_path:
                filter_complex = (
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[iv];"
                    f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[mv];"
                    f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ia];"
                    f"[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ma];"
                    f"[iv][ia][mv][ma]concat=n=2:v=1:a=1[cv][ca];"
                    f"[2:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                    f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                    f"[cv][ticker]overlay=0:H-{bar_h}:enable='gte(t,{ticker_start})'[vout]"
                )
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", intro_path,
                    "-i", base_path,
                    "-i", ticker_path,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[ca]",
                    "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-r", str(output_fps),
                    "-preset", "fast", out_path
                ]
            else:
                filter_complex = (
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[scaled];"
                    f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                    f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                    f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                    f"[scaled][ticker]overlay=0:H-{bar_h}[vout]"
                )
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", base_path,
                    "-i", ticker_path,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[ca]",
                    "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-r", str(output_fps),
                    "-preset", "fast", out_path
                ]

        status.info("Exporting final video…")
        progress.progress(80, text="Exporting…")
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

        progress.progress(100, text="Done!")
        total_time = time.time() - t0
        status.success(f"✅ Video processed successfully in {total_time:.1f}s!")

        with open(out_path, "rb") as f:
            video_bytes = f.read()

        st.video(video_bytes)
        st.download_button(
            label="⬇️ Download Processed Video",
            data=video_bytes,
            file_name="telugu_broadcast_output.mp4",
            mime="video/mp4",
        )

    except subprocess.CalledProcessError as e:
        progress.progress(0)
        stderr_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
        st.error(f"❌ FFmpeg error (exit {e.returncode})")
        st.code(stderr_msg)
        import traceback
        st.code(traceback.format_exc())
    except Exception as e:
        progress.progress(0)
        st.error(f"❌ Error during processing: {e}")
        import traceback
        st.code(traceback.format_exc())


# ─── Info section ──────────────────────────────────────────────────────────

with st.expander("ℹ️ How to Use"):
    st.markdown("""
**Step-by-step:**
1. Upload your **main video** (required)
2. Upload an **intro video** (optional — will be prepended before main video)
3. Upload your **logo PNG** (optional watermark)
4. Type your **red box label** (left side of ticker, e.g. district name)
5. Type your **blue scrolling text** (news headlines, separated by `•`)
6. Adjust speed, size, and position settings
7. Click **Process & Export Video**

**Telugu text is rendered using:**
- `uharfbuzz` for accurate script shaping
- `freetype-py` for glyph rendering
- `NotoSans Telugu Regular` font

**Supported input formats:** MP4, AVI, MOV, MKV
""")



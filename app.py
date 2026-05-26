

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
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)
    text = re.sub(r'[\u2460-\u2473]', '', text)
    text = re.sub(r'[\u25a0-\u25ff]', '', text)
    text = re.sub(r'[\u2580-\u259f]', '', text)
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\r\n\t]+', ' ', text)
    # Do NOT collapse multiple spaces — user may use them as visual gaps
    return text.strip()


FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Ramabhadra-Regular.ttf")

st.set_page_config(
    page_title="Telugu Video Editor",
    page_icon="🎬",
    layout="wide",
)

if not os.path.exists(FONT_PATH):
    st.error(f"❌ Font not found at: {FONT_PATH}")
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Teko:wght@400;600;700&family=DM+Sans:wght@300;400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0d0d0d 0%, #1a0a00 50%, #0d0d0d 100%);
        border: 1px solid #ff4500;
        color: white;
        padding: 28px 32px;
        border-radius: 4px;
        text-align: center;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #ff4500, #ff8c00, #ff4500);
    }
    .main-header h1 {
        font-family: 'Teko', sans-serif;
        font-size: 2.6rem;
        font-weight: 700;
        letter-spacing: 2px;
        margin: 0;
        color: #fff;
    }
    .main-header p {
        color: #aaa;
        margin: 6px 0 0 0;
        font-size: 0.9rem;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #111;
        border-radius: 4px 4px 0 0;
        border-bottom: 2px solid #ff4500;
        padding: 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Teko', sans-serif;
        font-size: 1.1rem;
        letter-spacing: 1px;
        font-weight: 600;
        color: #666;
        background: transparent;
        border: none;
        padding: 12px 28px;
        border-radius: 0;
    }
    .stTabs [aria-selected="true"] {
        color: #ff4500 !important;
        background: #1a0a00 !important;
        border-bottom: 2px solid #ff4500 !important;
    }

    /* Segment card */
    .segment-card {
        background: #0f0f0f;
        border: 1px solid #222;
        border-top: 3px solid #ff4500;
        border-radius: 0 0 4px 4px;
        padding: 20px;
        margin-bottom: 16px;
    }

    .segment-label {
        font-family: 'Teko', sans-serif;
        font-size: 1.3rem;
        letter-spacing: 2px;
        color: #ff4500;
        text-transform: uppercase;
        margin-bottom: 16px;
        border-bottom: 1px solid #222;
        padding-bottom: 8px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0a0a0a;
        border-right: 1px solid #1f1f1f;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-family: 'Teko', sans-serif;
        letter-spacing: 1px;
        color: #ff4500;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stSlider [data-testid="stTickBar"] span {
        color: #aaaaaa !important;
    }

    /* Process button */
    .stButton > button {
        background: linear-gradient(135deg, #ff4500, #cc3700);
        color: white;
        border: none;
        border-radius: 3px;
        padding: 14px 28px;
        font-family: 'Teko', sans-serif;
        font-size: 1.3rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        width: 100%;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #cc3700, #992900);
        transform: translateY(-1px);
    }

    /* Progress */
    .stProgress > div > div {
        background: linear-gradient(90deg, #ff4500, #ff8c00) !important;
    }

    /* Video player */
    [data-testid="stVideo"] {
        padding: 0 !important;
        margin: 0 !important;
    }
    [data-testid="stVideo"] video {
        display: block !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
    }

    .section-divider {
        border: none;
        border-top: 1px solid #1f1f1f;
        margin: 20px 0;
    }

    /* Status badges */
    .badge-ready {
        display: inline-block;
        background: #0a2a0a;
        color: #4caf50;
        border: 1px solid #2a5a2a;
        border-radius: 3px;
        padding: 2px 10px;
        font-size: 0.78rem;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    .badge-missing {
        display: inline-block;
        background: #1a0a00;
        color: #ff6633;
        border: 1px solid #552200;
        border-radius: 3px;
        padding: 2px 10px;
        font-size: 0.78rem;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎬 Telugu Video Broadcaster</h1>
    <p>District · State · Nation — Three segments, one broadcast</p>
</div>
""", unsafe_allow_html=True)


# ─── Telugu rendering helpers (unchanged) ──────────────────────────────────

def render_telugu_line(text: str, font_size: int, color: tuple, padding_x: int = 12) -> np.ndarray:
    blob    = hb.Blob.from_file_path(FONT_PATH)
    face_hb = hb.Face(blob)
    hb_font = hb.Font(face_hb)
    upem    = face_hb.upem
    hb_font.scale = (upem, upem)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})

    infos     = buf.glyph_infos
    positions = buf.glyph_positions

    face_ft = freetype.Face(FONT_PATH)
    face_ft.set_pixel_sizes(0, font_size)
    scale = font_size / upem

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

        bm_rows  = int(bm.rows)
        bm_width = int(bm.width)
        bm_buf   = bytes(bm.buffer)
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

    shift_x  = padding_x - min(0, min_bx)
    baseline = max_top + 4
    total_h  = max(1, baseline + max_bot + 4)
    total_w  = max(1, int(max_right + shift_x + padding_x),
                   pen_x + shift_x + padding_x)

    canvas = np.zeros((total_h, total_w, 4), dtype=np.uint8)

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
        canvas[r1:r2, c1:c2, 3] = np.maximum(
            canvas[r1:r2, c1:c2, 3], alpha_slice)

    return canvas


def paste_rgba(canvas: np.ndarray, src: np.ndarray, y: int, x: int,
               clamp_w: int = None, clip_left: int = 0, clip_right: int = None):
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
        canvas[r1:r2, c1:c2, 3], src_crop[:, :, 3])


def make_ticker_frame_cached(
    red_img: np.ndarray, blue_img: np.ndarray,
    frame_w: int, bar_h: int,
    t: float, scroll_speed: float = 150
) -> np.ndarray:
    bar = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
    red_w = int(frame_w * 0.28)
    slant = int(bar_h * 0.6)

    bar[:, :, 0] = 8;  bar[:, :, 1] = 34;  bar[:, :, 2] = 94;  bar[:, :, 3] = 255

    for row in range(bar_h):
        slant_offset = int(slant * row / bar_h)
        end_x = min(frame_w, red_w + slant_offset)
        bar[row, :end_x, 0] = 186
        bar[row, :end_x, 1] = 48
        bar[row, :end_x, 2] = 36
        bar[row, :end_x, 3] = 255

    rh, rw = red_img.shape[:2]
    ry = max(0, (bar_h - rh) // 2)
    rx = max(4, (red_w - rw) // 2)
    paste_rgba(bar, red_img, ry, rx, clamp_w=red_w - 4)

    slant_x_per_row = np.array([
        min(frame_w, red_w + int(slant * row / bar_h))
        for row in range(bar_h)
    ], dtype=np.int32)

    bh, bw = blue_img.shape[:2]
    by = max(0, (bar_h - bh) // 2)
    blue_area_w = frame_w - red_w
    gap = 60
    tile_w = bw + gap
    scrolled = int(t * scroll_speed)
    # phase = how far the lead tile has moved from the right edge
    phase = scrolled % tile_w
    # enough tiles to always fill the full frame width
    num_tiles = (frame_w // tile_w) + 3

    blue_canvas = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
    # Anchor first tile at right edge, scroll left over time
    start_x = frame_w - (scrolled % tile_w)
    bx = start_x
    while bx > -bw:
        if bx + bw > red_w:
            paste_rgba(blue_canvas, blue_img, by, bx, clip_left=0, clip_right=frame_w)
        bx -= tile_w


    for row in range(bar_h):
        cutoff = slant_x_per_row[row] + 4
        blue_canvas[row, :cutoff, :] = 0

    alpha = blue_canvas[:, :, 3:4] / 255.0
    for c in range(3):
        bar[:, :, c] = (
            blue_canvas[:, :, c] * alpha[:, :, 0] +
            bar[:, :, c] * (1 - alpha[:, :, 0])
        ).astype(np.uint8)
    bar[:, :, 3] = np.maximum(bar[:, :, 3], blue_canvas[:, :, 3])

    return bar


def make_ticker_frame(
    red_text: str, blue_text: str, frame_w: int, bar_h: int,
    t: float, scroll_speed: float = 150, font_size: int = 28
) -> np.ndarray:
    bar = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
    red_w = int(frame_w * 0.28)
    slant = bar_h

    bar[:, :, 0] = 8;  bar[:, :, 1] = 34;  bar[:, :, 2] = 94;  bar[:, :, 3] = 255

    for row in range(bar_h):
        slant_offset = int(slant * row / bar_h)
        end_x = min(frame_w, red_w + slant_offset)
        bar[row, :end_x, 0] = 186
        bar[row, :end_x, 1] = 48
        bar[row, :end_x, 2] = 36
        bar[row, :end_x, 3] = 255

    if red_text.strip():
        r_img = render_telugu_line(_clean_ticker_text(red_text), font_size, (255, 255, 255))
        rh, rw = r_img.shape[:2]
        shrink_font = font_size
        while rw > red_w - 8 and shrink_font > 10:
            shrink_font -= 2
            r_img = render_telugu_line(red_text, shrink_font, (255, 255, 255))
            rh, rw = r_img.shape[:2]
        ry = max(0, (bar_h - rh) // 2)
        rx = max(4, (red_w - rw) // 2)
        paste_rgba(bar, r_img, ry, rx, clamp_w=red_w)

    if blue_text.strip():
        b_img = render_telugu_line(_clean_ticker_text(blue_text), font_size, (255, 255, 255))
        bh, bw = b_img.shape[:2]
        by = max(0, (bar_h - bh) // 2)
        blue_area_w = frame_w - red_w
        gap = 60
        tile_w = bw + gap
        scrolled = int(t * scroll_speed)
        phase = scrolled % tile_w
        num_tiles = (frame_w // tile_w) + 3

        blue_canvas = np.zeros((bar_h, frame_w, 4), dtype=np.uint8)
        start_x = frame_w - (scrolled % tile_w)
        bx = start_x
        while bx > -bw:
            if bx + bw > red_w:
                paste_rgba(blue_canvas, b_img, by, bx, clip_left=0, clip_right=frame_w)
            bx -= tile_w

        for row in range(bar_h):
            cutoff = min(frame_w, red_w + int(slant * row / bar_h)) + 4
            blue_canvas[row, :cutoff, :] = 0

        alpha_b = blue_canvas[:, :, 3:4] / 255.0
        for c in range(3):
            bar[:, :, c] = (
                blue_canvas[:, :, c] * alpha_b[:, :, 0] +
                bar[:, :, c] * (1 - alpha_b[:, :, 0])
            ).astype(np.uint8)
        bar[:, :, 3] = np.maximum(bar[:, :, 3], blue_canvas[:, :, 3])

    return bar


# ─── Sidebar: shared settings ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Shared Settings")
    scroll_speed   = st.slider("Scroll Speed (px/sec)", 50, 400, 150)
    ticker_height  = st.slider("Ticker Bar Height (px)", 40, 100, 60)
    ticker_font_size = st.slider("Ticker Font Size (px)", 10, 60, 28)
    logo_position  = st.selectbox("Logo Position", ["Top Right", "Top Left", "Bottom Right", "Bottom Left"])
    logo_scale     = st.slider("Logo Size (%)", 5, 30, 12)

    st.markdown("---")
    st.markdown("## 💾 Output")
    output_fps     = st.selectbox("Output FPS", [24, 25, 30], index=2)
    output_quality = st.selectbox("Output Quality", ["high", "medium", "low"], index=1)

    st.markdown("---")
    st.markdown("## 📺 Final Resolution")
    target_res = st.selectbox(
        "Target Resolution (for concat)",
        ["1920x1080", "1280x720", "854x480"],
        index=0,
        help="All 3 segments will be scaled to this resolution before combining."
    )
    TARGET_W, TARGET_H = map(int, target_res.split("x"))


# ─── Segment definitions ───────────────────────────────────────────────────

SEGMENT_NAMES = ["🏘️ District", "🏛️ State", "🌐 Nation"]
SEGMENT_KEYS  = ["district", "state", "nation"]

DEFAULT_RED   = [
    "నెల్లూరు జిల్లా వార్తలు",
    "ఆంధ్రప్రదేశ్ వార్తలు",
    "జాతీయ వార్తలు",
]
DEFAULT_BLUE  = [
    "రహాదారి విస్తరణ, మౌలిక వసతుల మెరుగుదల  •  నగర అభివృద్ధి పనుల ప్రారంభం",
    "రాష్ట్ర బడ్జెట్ సమావేశాలు ప్రారంభం  •  ముఖ్యమంత్రి పర్యటన కార్యక్రమాలు",
    "కేంద్ర బడ్జెట్ ప్రకటనలు  •  పార్లమెంట్ శీతాకాల సమావేశాలు ప్రారంభం",
]

# Store per-segment inputs
segments = []

tab_objects = st.tabs(SEGMENT_NAMES)

for i, (tab, key) in enumerate(zip(tab_objects, SEGMENT_KEYS)):
    with tab:
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown(f"#### 📁 Uploads — {SEGMENT_NAMES[i]}")
            main_vid  = st.file_uploader(f"Main Video",  type=["mp4","avi","mov","mkv"], key=f"{key}_main")
            intro_vid = st.file_uploader(f"Intro Video (optional)", type=["mp4","avi","mov","mkv"], key=f"{key}_intro")
            logo_f    = st.file_uploader(f"Logo / Watermark (PNG/GIF)", type=["png","jpg","jpeg","gif"], key=f"{key}_logo")

            if main_vid:
                st.markdown(f'<span class="badge-ready">✓ Main video ready</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="badge-missing">⚠ Main video missing</span>', unsafe_allow_html=True)

            if logo_f:
                logo_pil = Image.open(logo_f)
                if getattr(logo_pil, "is_animated", False) or logo_pil.format == "GIF":
                    logo_pil.seek(0)
                logo_pil = logo_pil.convert("RGBA")
                st.image(logo_pil, caption="Logo preview", width=100)

        with col_right:
            st.markdown(f"#### 📝 Ticker Text — {SEGMENT_NAMES[i]}")
            red_label  = st.text_area("🟥 Red Box Label", value=DEFAULT_RED[i],  height=80,  key=f"{key}_red")
            blue_scroll = st.text_area("🔵 Blue Scrolling Text", value=DEFAULT_BLUE[i], height=100, key=f"{key}_blue")

            st.markdown("#### 📋 Ticker Preview")
            try:
                prev_w, prev_h = 560, ticker_height * 2
                preview = make_ticker_frame(
                    red_label, blue_scroll, prev_w, prev_h,
                    t=0.5, scroll_speed=scroll_speed, font_size=ticker_font_size
                )
                preview_img = Image.fromarray(preview, "RGBA")
                bg = Image.new("RGB", preview_img.size, (20, 20, 20))
                bg.paste(preview_img, mask=preview_img.split()[3])
                st.image(bg, caption="Live ticker preview", width='stretch')
            except Exception as e:
                st.warning(f"Preview error: {e}")

        segments.append({
            "name":        SEGMENT_NAMES[i],
            "key":         key,
            "main_vid":    main_vid,
            "intro_vid":   intro_vid,
            "logo_file":   logo_f,
            "red_label":   red_label,
            "blue_scroll": blue_scroll,
        })

st.divider()

# ─── Readiness check ───────────────────────────────────────────────────────

all_ready = all(s["main_vid"] is not None for s in segments)
missing   = [s["name"] for s in segments if s["main_vid"] is None]

if not all_ready:
    st.warning(f"⚠️ Please upload main videos for: {', '.join(missing)}")

process_btn = st.button(
    "🚀 Process All 3 Segments & Export Combined Video",
    disabled=not all_ready
)


# ─── Processing pipeline ───────────────────────────────────────────────────

def process_segment(seg, tmp_dir, seg_idx, W, H, bar_h, ticker_font_size,
                    scroll_speed, output_fps, output_quality,
                    logo_position, logo_scale, progress_fn, status_fn):
    """Process one segment and return path to composited .mp4"""
    import subprocess, json, time

    def ffprobe_info(path):
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", path
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        vs = next(s for s in data["streams"] if s["codec_type"] == "video")
        return int(vs["width"]), int(vs["height"]), float(data["format"]["duration"])

    bitrate_map = {"high": "8000k", "medium": "4000k", "low": "2000k"}
    seg_dir = os.path.join(tmp_dir, f"seg_{seg_idx}")
    os.makedirs(seg_dir, exist_ok=True)

    # Save main video
    main_path = os.path.join(seg_dir, "main.mp4")
    with open(main_path, "wb") as f:
        f.write(seg["main_vid"].read())

    status_fn(f"[{seg['name']}] Reading video info…")
    vid_w, vid_h, main_duration = ffprobe_info(main_path)

    # Black bar removal
    status_fn(f"[{seg['name']}] Detecting black bars…")
    crop_result = subprocess.run([
        "ffmpeg", "-y", "-ss", "5", "-i", main_path,
        "-t", "5", "-vf", "cropdetect=24:16:0", "-f", "null", "-"
    ], capture_output=True, text=True)
    crop_params = None
    for line in reversed(crop_result.stderr.splitlines()):
        if "crop=" in line:
            m = re.search(r'crop=(\d+:\d+:\d+:\d+)', line)
            if m:
                crop_params = m.group(1)
                break
    if crop_params:
        cw, ch, cx, cy = map(int, crop_params.split(":"))
        if cw < vid_w * 0.98 or ch < vid_h * 0.98:
            status_fn(f"[{seg['name']}] Cropping black bars…")
            cropped = os.path.join(seg_dir, "main_cropped.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", main_path,
                "-vf", f"crop={crop_params},scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-c:a", "copy", cropped
            ], check=True, capture_output=True)
            main_path = cropped

    # Save intro
    intro_path = None
    intro_duration = 0.0
    if seg["intro_vid"]:
        intro_path = os.path.join(seg_dir, "intro.mp4")
        with open(intro_path, "wb") as f:
            f.write(seg["intro_vid"].read())
        _, _, intro_duration = ffprobe_info(intro_path)

    # Render ticker
    status_fn(f"[{seg['name']}] Rendering ticker…")
    TICKER_FPS = 10
    blue_text_img = render_telugu_line(seg["blue_scroll"], ticker_font_size, (255, 255, 255))
    text_w = blue_text_img.shape[1]
    blue_area_w = W - int(W * 0.28)
    tile_w = text_w + 60
    scroll_period = tile_w / scroll_speed
    total_ticker_frames = max(30, int(scroll_period * TICKER_FPS))

    ticker_W = W if W % 2 == 0 else W - 1
    ticker_H = bar_h if bar_h % 2 == 0 else bar_h + 1

    ticker_path = os.path.join(seg_dir, "ticker.mp4")
    ticker_log_path = os.path.join(seg_dir, "ticker.log")
    ticker_log = open(ticker_log_path, "wb")

    ffmpeg_ticker = subprocess.Popen([
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{ticker_W}x{ticker_H}",
        "-pix_fmt", "rgb24", "-r", str(TICKER_FPS), "-i", "pipe:0",
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "ultrafast", ticker_path
    ], stdin=subprocess.PIPE, stderr=ticker_log)

    red_img_cached = render_telugu_line(_clean_ticker_text(seg["red_label"]), ticker_font_size, (255, 255, 255))
    blue_img_cached = render_telugu_line(_clean_ticker_text(seg["blue_scroll"]), ticker_font_size, (255, 255, 255))

    red_w_box = int(ticker_W * 0.28)
    shrink_font = ticker_font_size
    rh, rw_r = red_img_cached.shape[:2]
    while rw_r > red_w_box - 8 and shrink_font > 10:
        shrink_font -= 2
        red_img_cached = render_telugu_line(_clean_ticker_text(seg["red_label"]), shrink_font, (255, 255, 255))
        rh, rw_r = red_img_cached.shape[:2]

    pipe_ok = True
    for i in range(total_ticker_frames):
        t_sample = i / TICKER_FPS
        frame = make_ticker_frame_cached(
            red_img_cached, blue_img_cached,
            ticker_W, ticker_H, t_sample, scroll_speed
        )[:, :, :3]
        if frame.shape[0] != ticker_H or frame.shape[1] != ticker_W:
            frame = np.pad(frame,
                ((0, ticker_H - frame.shape[0]),
                 (0, ticker_W - frame.shape[1]),
                 (0, 0)), mode='edge')
        try:
            ffmpeg_ticker.stdin.write(frame.tobytes())
        except OSError:
            pipe_ok = False
            break

    ffmpeg_ticker.stdin.close()
    ret = ffmpeg_ticker.wait()
    ticker_log.close()

    if ret != 0 or not pipe_ok:
        with open(ticker_log_path, "r", errors="replace") as f:
            raise RuntimeError(f"Ticker encode failed for {seg['name']}:\n{f.read()[-2000:]}")

    # Logo setup
    logo_input_args = []
    is_gif = False
    logo_w_target = logo_h_target = lx = ly = 0

    if seg["logo_file"]:
        status_fn(f"[{seg['name']}] Preparing logo…")
        seg["logo_file"].seek(0)
        logo_pil = Image.open(seg["logo_file"])
        is_gif = getattr(logo_pil, "is_animated", False) or seg["logo_file"].name.lower().endswith(".gif")
        logo_pil.seek(0)
        logo_frame = logo_pil.convert("RGBA")
        logo_w_target = int(W * logo_scale / 100)
        ratio = logo_w_target / logo_frame.width
        logo_h_target = int(logo_frame.height * ratio)

        pos_map = {
            "Top Right":    (W - logo_w_target - 10, 10),
            "Top Left":     (10, 10),
            "Bottom Right": (W - logo_w_target - 10, H - bar_h - logo_h_target - 10),
            "Bottom Left":  (10, H - bar_h - logo_h_target - 10),
        }
        lx, ly = pos_map[logo_position]

        if is_gif:
            logo_gif_path = os.path.join(seg_dir, "logo_anim.gif")
            seg["logo_file"].seek(0)
            with open(logo_gif_path, "wb") as gf:
                gf.write(seg["logo_file"].read())
            logo_input_args = ["-stream_loop", "-1", "-i", logo_gif_path]
        else:
            logo_frame = logo_frame.resize((logo_w_target, logo_h_target), Image.LANCZOS)
            logo_png_path = os.path.join(seg_dir, "logo.png")
            logo_frame.save(logo_png_path)
            logo_input_args = ["-i", logo_png_path]

    # FFmpeg composite — scale everything to TARGET_W x TARGET_H
    status_fn(f"[{seg['name']}] Compositing…")
    out_path = os.path.join(seg_dir, "segment.mp4")
    ticker_start = intro_duration

    scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    if seg["logo_file"]:
        gif_logo_filter = (
            f"scale={logo_w_target}:{logo_h_target},format=rgba,setpts=PTS-STARTPTS"
            if is_gif else "setpts=PTS-STARTPTS"
        )
        if intro_path:
            filter_complex = (
                f"[0:v]{scale_filter},setsar=1[iv];"
                f"[1:v]{scale_filter},setsar=1[mv];"
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
                "-i", intro_path, "-i", main_path, "-i", ticker_path,
                *logo_input_args,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "ultrafast", out_path
            ]
        else:
            filter_complex = (
                f"[0:v]{scale_filter}[scaled];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[scaled][ticker]overlay=0:H-{ticker_H}[v1];"
                f"[2:v]{gif_logo_filter}[logo];"
                f"[v1][logo]overlay={lx}:{ly}:shortest=1[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", main_path, "-i", ticker_path,
                *logo_input_args,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "ultrafast", out_path
            ]
    else:
        if intro_path:
            filter_complex = (
                f"[0:v]{scale_filter},setsar=1[iv];"
                f"[1:v]{scale_filter},setsar=1[mv];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ia];"
                f"[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ma];"
                f"[iv][ia][mv][ma]concat=n=2:v=1:a=1[cv][ca];"
                f"[2:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[cv][ticker]overlay=0:H-{ticker_H}:enable='gte(t,{ticker_start})'[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", intro_path, "-i", main_path, "-i", ticker_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "fast", out_path
            ]
        else:
            filter_complex = (
                f"[0:v]{scale_filter}[scaled];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[scaled][ticker]overlay=0:H-{bar_h}[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", main_path, "-i", ticker_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "fast", out_path
            ]

    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    return out_path


def pre_save_segments(segments, tmp_dir):
    """
    Save all uploaded file buffers to disk BEFORE spawning threads.
    Streamlit's UploadedFile objects are not thread-safe — reading them
    from multiple threads simultaneously causes corruption or empty reads.
    Returns a new list of segment dicts with file paths instead of buffers.
    """
    import io
    saved = []
    for idx, seg in enumerate(segments):
        seg_dir = os.path.join(tmp_dir, f"seg_{idx}")
        os.makedirs(seg_dir, exist_ok=True)

        # Main video — always present (button disabled otherwise)
        main_path = os.path.join(seg_dir, "main.mp4")
        seg["main_vid"].seek(0)
        with open(main_path, "wb") as f:
            f.write(seg["main_vid"].read())

        # Intro video — optional
        intro_path = None
        if seg["intro_vid"]:
            intro_path = os.path.join(seg_dir, "intro.mp4")
            seg["intro_vid"].seek(0)
            with open(intro_path, "wb") as f:
                f.write(seg["intro_vid"].read())

        # Logo — optional; save raw bytes + filename for type detection
        logo_path = None
        logo_name = None
        if seg["logo_file"]:
            seg["logo_file"].seek(0)
            logo_name = seg["logo_file"].name
            ext = os.path.splitext(logo_name)[1].lower() or ".png"
            logo_path = os.path.join(seg_dir, f"logo_src{ext}")
            with open(logo_path, "wb") as f:
                f.write(seg["logo_file"].read())

        saved.append({
            "name":        seg["name"],
            "key":         seg["key"],
            "main_path":   main_path,
            "intro_path":  intro_path,
            "logo_path":   logo_path,
            "logo_name":   logo_name,
            "red_label":   seg["red_label"],
            "blue_scroll": seg["blue_scroll"],
            "seg_dir":     seg_dir,
        })
    return saved


def process_segment_from_paths(seg, tmp_dir, seg_idx, W, H, bar_h,
                                ticker_font_size, scroll_speed,
                                output_fps, output_quality,
                                logo_position, logo_scale,
                                status_dict):
    """
    Same pipeline as process_segment() but operates entirely on file paths
    (no Streamlit UploadedFile objects) — safe to call from worker threads.
    Writes status messages into status_dict[seg_idx] instead of calling st.*
    """
    import subprocess, json

    def _status(msg):
        status_dict[seg_idx] = msg

    def ffprobe_info(path):
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", path
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        vs = next(s for s in data["streams"] if s["codec_type"] == "video")
        return int(vs["width"]), int(vs["height"]), float(data["format"]["duration"])

    bitrate_map = {"high": "8000k", "medium": "4000k", "low": "2000k"}
    seg_dir    = seg["seg_dir"]
    main_path  = seg["main_path"]
    intro_path = seg["intro_path"]

    _status(f"[{seg['name']}] Reading video info…")
    vid_w, vid_h, main_duration = ffprobe_info(main_path)

    # ── Black bar removal ──────────────────────────────────────────
    _status(f"[{seg['name']}] Detecting black bars…")
    crop_result = subprocess.run([
        "ffmpeg", "-y", "-ss", "5", "-i", main_path,
        "-t", "5", "-vf", "cropdetect=24:16:0", "-f", "null", "-"
    ], capture_output=True, text=True)
    crop_params = None
    for line in reversed(crop_result.stderr.splitlines()):
        if "crop=" in line:
            m = re.search(r'crop=(\d+:\d+:\d+:\d+)', line)
            if m:
                crop_params = m.group(1)
                break
    if crop_params:
        cw, ch, cx, cy = map(int, crop_params.split(":"))
        if cw < vid_w * 0.98 or ch < vid_h * 0.98:
            _status(f"[{seg['name']}] Removing black bars…")
            cropped = os.path.join(seg_dir, "main_cropped.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", main_path,
                "-vf", f"crop={crop_params},scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-c:a", "copy", cropped
            ], check=True, capture_output=True)
            main_path = cropped

    # ── Intro duration ─────────────────────────────────────────────
    intro_duration = 0.0
    if intro_path:
        _, _, intro_duration = ffprobe_info(intro_path)

    # ── Ticker render ──────────────────────────────────────────────
    _status(f"[{seg['name']}] Rendering ticker…")
    TICKER_FPS = 10
    blue_text_img = render_telugu_line(seg["blue_scroll"], ticker_font_size, (255, 255, 255))
    text_w = blue_text_img.shape[1]
    tile_w = text_w + 60
    scroll_period = tile_w / scroll_speed
    total_ticker_frames = max(30, int(scroll_period * TICKER_FPS))

    ticker_W = W if W % 2 == 0 else W - 1
    ticker_H = bar_h if bar_h % 2 == 0 else bar_h + 1

    ticker_path    = os.path.join(seg_dir, "ticker.mp4")
    ticker_log_path = os.path.join(seg_dir, "ticker.log")
    ticker_log     = open(ticker_log_path, "wb")

    ffmpeg_ticker = subprocess.Popen([
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{ticker_W}x{ticker_H}",
        "-pix_fmt", "rgb24", "-r", str(TICKER_FPS), "-i", "pipe:0",
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "ultrafast", ticker_path
    ], stdin=subprocess.PIPE, stderr=ticker_log)

    red_img_cached  = render_telugu_line(_clean_ticker_text(seg["red_label"]),   ticker_font_size, (255, 255, 255))
    blue_img_cached = render_telugu_line(_clean_ticker_text(seg["blue_scroll"]), ticker_font_size, (255, 255, 255))

    red_w_box = int(ticker_W * 0.28)
    shrink_font = ticker_font_size
    rh, rw_r = red_img_cached.shape[:2]
    while rw_r > red_w_box - 8 and shrink_font > 10:
        shrink_font -= 2
        red_img_cached = render_telugu_line(_clean_ticker_text(seg["red_label"]), shrink_font, (255, 255, 255))
        rh, rw_r = red_img_cached.shape[:2]

    pipe_ok = True
    for i in range(total_ticker_frames):
        t_sample = i / TICKER_FPS
        frame = make_ticker_frame_cached(
            red_img_cached, blue_img_cached,
            ticker_W, ticker_H, t_sample, scroll_speed
        )[:, :, :3]
        if frame.shape[0] != ticker_H or frame.shape[1] != ticker_W:
            frame = np.pad(frame,
                ((0, ticker_H - frame.shape[0]),
                 (0, ticker_W - frame.shape[1]),
                 (0, 0)), mode='edge')
        try:
            ffmpeg_ticker.stdin.write(frame.tobytes())
        except OSError:
            pipe_ok = False
            break

    ffmpeg_ticker.stdin.close()
    ret = ffmpeg_ticker.wait()
    ticker_log.close()

    if ret != 0 or not pipe_ok:
        with open(ticker_log_path, "r", errors="replace") as f:
            raise RuntimeError(f"Ticker encode failed for {seg['name']}:\n{f.read()[-2000:]}")

    # ── Logo setup ─────────────────────────────────────────────────
    logo_input_args = []
    is_gif = False
    logo_w_target = logo_h_target = lx = ly = 0

    if seg["logo_path"]:
        _status(f"[{seg['name']}] Preparing logo…")
        logo_name = seg["logo_name"] or ""
        is_gif = logo_name.lower().endswith(".gif")
        logo_pil = Image.open(seg["logo_path"])
        logo_pil.seek(0)
        logo_frame = logo_pil.convert("RGBA")
        logo_w_target = int(W * logo_scale / 100)
        ratio = logo_w_target / logo_frame.width
        logo_h_target = int(logo_frame.height * ratio)

        pos_map = {
            "Top Right":    (W - logo_w_target - 10, 10),
            "Top Left":     (10, 10),
            "Bottom Right": (W - logo_w_target - 10, H - bar_h - logo_h_target - 10),
            "Bottom Left":  (10, H - bar_h - logo_h_target - 10),
        }
        lx, ly = pos_map[logo_position]

        if is_gif:
            logo_input_args = ["-stream_loop", "-1", "-i", seg["logo_path"]]
        else:
            logo_frame = logo_frame.resize((logo_w_target, logo_h_target), Image.LANCZOS)
            logo_png_path = os.path.join(seg_dir, "logo.png")
            logo_frame.save(logo_png_path)
            logo_input_args = ["-i", logo_png_path]

    # ── FFmpeg composite ───────────────────────────────────────────
    _status(f"[{seg['name']}] Compositing…")
    out_path     = os.path.join(seg_dir, "segment.mp4")
    ticker_start = intro_duration
    scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    if seg["logo_path"]:
        gif_logo_filter = (
            f"scale={logo_w_target}:{logo_h_target},format=rgba,setpts=PTS-STARTPTS"
            if is_gif else "setpts=PTS-STARTPTS"
        )
        if intro_path:
            filter_complex = (
                f"[0:v]{scale_filter},setsar=1[iv];"
                f"[1:v]{scale_filter},setsar=1[mv];"
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
                "-i", intro_path, "-i", main_path, "-i", ticker_path,
                *logo_input_args,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "ultrafast", out_path
            ]
        else:
            filter_complex = (
                f"[0:v]{scale_filter}[scaled];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[scaled][ticker]overlay=0:H-{ticker_H}[v1];"
                f"[2:v]{gif_logo_filter}[logo];"
                f"[v1][logo]overlay={lx}:{ly}:shortest=1[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", main_path, "-i", ticker_path,
                *logo_input_args,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "ultrafast", out_path
            ]
    else:
        if intro_path:
            filter_complex = (
                f"[0:v]{scale_filter},setsar=1[iv];"
                f"[1:v]{scale_filter},setsar=1[mv];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ia];"
                f"[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ma];"
                f"[iv][ia][mv][ma]concat=n=2:v=1:a=1[cv][ca];"
                f"[2:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[cv][ticker]overlay=0:H-{ticker_H}:enable='gte(t,{ticker_start})'[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", intro_path, "-i", main_path, "-i", ticker_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "fast", out_path
            ]
        else:
            filter_complex = (
                f"[0:v]{scale_filter}[scaled];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[ca];"
                f"[1:v]loop=loop=-1:size={total_ticker_frames}:start=0[looped];"
                f"[looped]trim=duration={main_duration},setpts=PTS-STARTPTS[ticker];"
                f"[scaled][ticker]overlay=0:H-{bar_h}[vout]"
            )
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", main_path, "-i", ticker_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[ca]",
                "-c:v", "libx264", "-b:v", bitrate_map[output_quality],
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                "-r", str(output_fps), "-preset", "fast", out_path
            ]

    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    _status(f"[{seg['name']}] ✅ Done")
    return out_path


if process_btn and all_ready:
    import subprocess, time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    progress  = st.progress(0, text="Saving uploaded files…")
    status    = st.empty()

    # Per-segment live status placeholders — one row each
    st.markdown("**Segment progress:**")
    seg_status_placeholders = [st.empty() for _ in segments]
    for i, seg in enumerate(segments):
        seg_status_placeholders[i].info(f"⏳ {seg['name']} — waiting to start")

    t_start = time.time()
    tmp_dir = tempfile.mkdtemp()

    try:
        # ── Step 0: Save all file buffers to disk (main thread, safe) ──
        status.info("Saving uploaded files to disk…")
        saved_segments = pre_save_segments(segments, tmp_dir)
        progress.progress(5, text="Files saved — launching parallel processing…")

        # ── Step 1: Launch all 3 segments in parallel ───────────────
        # shared dict: seg_idx → latest status string (written by threads)
        status_dict   = {i: f"⏳ {seg['name']} — queued" for i, seg in enumerate(segments)}
        results       = {}   # seg_idx → output path
        errors        = {}   # seg_idx → exception

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_idx = {
                executor.submit(
                    process_segment_from_paths,
                    seg            = saved_segments[idx],
                    tmp_dir        = tmp_dir,
                    seg_idx        = idx,
                    W              = TARGET_W,
                    H              = TARGET_H,
                    bar_h          = ticker_height,
                    ticker_font_size = ticker_font_size,
                    scroll_speed   = scroll_speed,
                    output_fps     = output_fps,
                    output_quality = output_quality,
                    logo_position  = logo_position,
                    logo_scale     = logo_scale,
                    status_dict    = status_dict,
                ): idx
                for idx in range(len(saved_segments))
            }

            # Poll until all futures complete, updating UI every 0.5s
            done_count = 0
            while done_count < len(future_to_idx):
                done_count = 0
                for future, idx in future_to_idx.items():
                    if future.done():
                        done_count += 1
                        if idx not in results and idx not in errors:
                            exc = future.exception()
                            if exc:
                                errors[idx] = exc
                                seg_status_placeholders[idx].error(
                                    f"❌ {saved_segments[idx]['name']} — failed: {exc}"
                                )
                            else:
                                results[idx] = future.result()
                                seg_status_placeholders[idx].success(
                                    f"✅ {saved_segments[idx]['name']} — complete"
                                )
                    else:
                        # Still running — show latest status from thread
                        seg_status_placeholders[idx].info(status_dict[idx])

                overall_pct = 5 + int((done_count / len(future_to_idx)) * 80)
                progress.progress(overall_pct, text=f"Processing… {done_count}/{len(future_to_idx)} segments done")
                time.sleep(0.5)

        # ── Step 2: Raise if any segment failed ─────────────────────
        if errors:
            for idx, exc in errors.items():
                st.error(f"❌ Segment {saved_segments[idx]['name']} failed: {exc}")
            st.stop()

        # ── Step 3: Concatenate in original order ───────────────────
        status.info("All segments done — concatenating…")
        progress.progress(88, text="Combining District → State → Nation…")

        concat_list_path = os.path.join(tmp_dir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for idx in range(len(saved_segments)):   # preserve order 0→1→2
                f.write(f"file '{results[idx]}'\n")

        final_path = os.path.join(tmp_dir, "final_broadcast.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264", "-b:v", "6000k",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            "-r", str(output_fps),
            "-preset", "fast",
            final_path
        ], check=True, capture_output=True)

        progress.progress(100, text="Done!")
        total_time = time.time() - t_start
        status.success(f"✅ Combined broadcast ready in {total_time:.1f}s!")

        with open(final_path, "rb") as f:
            video_bytes = f.read()

        st.video(video_bytes)
        st.download_button(
            label="⬇️ Download Combined Broadcast Video",
            data=video_bytes,
            file_name="telugu_broadcast_combined.mp4",
            mime="video/mp4",
        )

    except subprocess.CalledProcessError as e:
        progress.progress(0)
        stderr_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
        st.error(f"❌ FFmpeg error (exit {e.returncode})")
        st.code(stderr_msg[-3000:])
        import traceback; st.code(traceback.format_exc())
    except Exception as e:
        progress.progress(0)
        st.error(f"❌ Error: {e}")
        import traceback; st.code(traceback.format_exc())


# ─── How to use ────────────────────────────────────────────────────────────

with st.expander("ℹ️ How to Use"):
    st.markdown("""
**Step-by-step:**
1. Open each tab (**District**, **State**, **Nation**) and upload:
   - Main video (required)
   - Intro video (optional — prepended before main)
   - Logo PNG/GIF (optional watermark)
2. Type the **red box label** and **blue scrolling text** for each segment
3. Adjust **shared settings** in the sidebar (speed, font size, resolution, quality)
4. Click **Process All 3 Segments & Export Combined Video**

**Output:** All 3 segments are rendered and joined into a single MP4, playing District → State → Nation back to back.

**Telugu text is rendered using:** `uharfbuzz` + `freetype-py` + Ramabhadra font

**Supported input formats:** MP4, AVI, MOV, MKV
""")
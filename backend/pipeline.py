import os
import sys
import platform
import subprocess
import urllib.request
import uuid
import time
import shutil
import logging
import json
import re
import zipfile
from pathlib import Path
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List
from pydantic import BaseModel, Field

import yt_dlp

logger = logging.getLogger("clipforge.pipeline")
logger.setLevel(logging.INFO)

# ==========================================
# 1. HARDWARE PROBE
# ==========================================
cuda_available = False
gpu_name = "CPU"
try:
    import torch
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        gpu_name = torch.cuda.get_device_name(0)
except Exception:
    try:
        from ctranslate2 import get_cuda_device_count
        cuda_available = get_cuda_device_count() > 0
        if cuda_available:
            gpu_name = "NVIDIA CUDA GPU"
    except Exception:
        cuda_available = False

print(f"🚀 Compute Hardware Detected: {gpu_name} (CUDA Acceleration: {cuda_available})")

# ==========================================
# 2. SYSTEM PATHS & DIRECTORY SETUP
# ==========================================
if os.path.exists("/content") or platform.system() == "Linux":
    BASE_DIR = Path("/content")
else:
    BASE_DIR = Path.cwd() / "content"

DOWNLOADS_DIR = BASE_DIR / "downloads"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
CLIPS_DIR = BASE_DIR / "clips"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MASKS_DIR = ASSETS_DIR / "masks"
MUSIC_DIR = ASSETS_DIR / "music"
EXPORT_DIR = BASE_DIR / "exports"
PERSISTENT_COOKIE_FILE = BASE_DIR / "cookies.txt"

for d in [DOWNLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR, FONTS_DIR, MASKS_DIR, MUSIC_DIR, EXPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print(f"📁 Local directories initialized successfully under {BASE_DIR}")

def mount_gdrive():
    """Mount Google Drive for persistent shorts export."""
    try:
        from google.colab import drive
        drive.mount('/content/drive', force_remount=False)
        drive_path = Path('/content/drive/MyDrive/ClipForge_Shorts')
        drive_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Google Drive mounted! Export directory: {drive_path}")
        return drive_path
    except Exception as e:
        print(f"ℹ️ Google Drive mount skipped or unavailable: {e}")
        return None

# ==========================================
# 3. ASSETS & FONT DOWNLOADER
# ==========================================
_GF = "https://raw.githubusercontent.com/google/fonts/main"

_CORE_FONTS = {
    "Roboto-Regular.ttf": "https://github.com/googlefonts/roboto-2/raw/main/src/hinted/Roboto-Regular.ttf",
    "Roboto-Bold.ttf": "https://github.com/googlefonts/roboto-2/raw/main/src/hinted/Roboto-Bold.ttf",
}

TRENDING_FONTS = {
    "Anton": ("Anton-Regular.ttf", f"{_GF}/ofl/anton/Anton-Regular.ttf"),
    "Bebas Neue": ("BebasNeue-Regular.ttf", f"{_GF}/ofl/bebasneue/BebasNeue-Regular.ttf"),
    "Poppins": ("Poppins-Bold.ttf", f"{_GF}/ofl/poppins/Poppins-Bold.ttf"),
    "Montserrat": ("Montserrat.ttf", f"{_GF}/ofl/montserrat/Montserrat%5Bwght%5D.ttf"),
    "Oswald": ("Oswald.ttf", f"{_GF}/ofl/oswald/Oswald%5Bwght%5D.ttf"),
    "Bangers": ("Bangers-Regular.ttf", f"{_GF}/ofl/bangers/Bangers-Regular.ttf"),
    "Luckiest Guy": ("LuckiestGuy-Regular.ttf", f"{_GF}/luckiestguy/LuckiestGuy-Regular.ttf"),
    "Permanent Marker": ("PermanentMarker-Regular.ttf", f"{_GF}/permanentmarker/PermanentMarker-Regular.ttf"),
    "Alfa Slab One": ("AlfaSlabOne-Regular.ttf", f"{_GF}/ofl/alfaslabone/AlfaSlabOne-Regular.ttf"),
    "DM Serif Display": ("DMSerifDisplay-Regular.ttf", f"{_GF}/ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf"),
}

def download_asset_file(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp, open(dest, 'wb') as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"⚠️ Warning downloading font {dest.name}: {e}")
        return False

def ensure_fonts():
    print("🔤 Downloading core & trending creator fonts...")
    for filename, url in _CORE_FONTS.items():
        download_asset_file(url, FONTS_DIR / filename)
    for family, (fname, url) in TRENDING_FONTS.items():
        download_asset_file(url, FONTS_DIR / fname)

ensure_fonts()

def ensure_rounded_mask(size: int = 1020, radius: int = 60) -> Path:
    path = MASKS_DIR / f"rounded_{size}_{radius}.png"
    if path.exists() and path.stat().st_size > 0:
        return path
    MASKS_DIR.mkdir(parents=True, exist_ok=True)
    
    if radius <= 0:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=white:s={size}x{size}:d=0.1", "-frames:v", "1", str(path)]
    else:
        edge = size - 1 - radius
        expr = f"255*clip(0.5+({radius}-hypot(max(0\\\\,{radius}-X)+max(0\\\\,X-{edge})\\\\,max(0\\\\,{radius}-Y)+max(0\\\\,Y-{edge})))/1.5\\\\,0\\\\,1)"
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={size}x{size}:d=0.1", "-vf", f"geq=lum='{expr}':cb=128:cr=128", "-frames:v", "1", str(path)]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        print(f"⚠️ Mask generation warning: {e}")
    return path

ensure_rounded_mask()
print("🎨 Rounded-corner video mask initialized.")

# ==========================================
# 4. DATA MODELS & CAPTION PRESETS
# ==========================================
class AspectRatio(str, Enum):
    NINE_16 = "9:16"
    SIXTEEN_9 = "16:9"

class FitMode(str, Enum):
    CROP = "crop"
    SQUARE = "square"

class Device(str, Enum):
    AUTO = "auto"
    CUDA = "cuda"
    CPU = "cpu"

_BASE_PRESET = {
    "font_family": "Roboto",
    "bold": True,
    "font_size": 90,
    "primary_color": "#FFFFFF",
    "highlight_color": "#FFD400",
    "outline_color": "#000000",
    "outline": 5,
    "shadow": 1,
    "position": "bottom",
    "karaoke": False,
    "uppercase": True,
    "animation": "none",
    "max_lines": 2,
    "max_chars": 22,
    "background_enabled": False,
    "background_color": "#000000",
}

def _P(label: str, **kw) -> dict:
    d = dict(_BASE_PRESET)
    d["label"] = label
    d.update(kw)
    return d

STYLE_PRESETS: Dict[str, dict] = {
    "bold_white": _P("Bold White", highlight_color="#FFFFFF", font_size=96, max_chars=20),
    "karaoke_yellow": _P("Karaoke Yellow", karaoke=True, font_size=92, highlight_color="#FFE600"),
    "minimal": _P("Minimal", bold=False, uppercase=False, font_size=64, outline=1, shadow=2, highlight_color="#FFFFFF", max_chars=28),
    "hormozi_green": _P("Hormozi Green", font_family="Montserrat", animation="highlight", highlight_color="#27E36B", font_size=94, outline=6, position="center", max_lines=2, max_chars=16),
    "hormozi_yellow": _P("Hormozi Yellow", font_family="Montserrat", animation="highlight", highlight_color="#FFD400", font_size=94, outline=6, position="center", max_lines=2, max_chars=16),
    "beast_red": _P("Beast Pop", font_family="Anton", bold=False, animation="highlight", highlight_color="#FF3B30", font_size=108, outline=7, position="center", max_lines=2, max_chars=15),
    "one_word_punch": _P("One-Word Punch", font_family="Anton", bold=False, animation="one_word", font_size=132, outline=8, position="center"),
    "word_reveal": _P("Word Reveal", font_family="Montserrat", animation="word_reveal", highlight_color="#FFFFFF", font_size=90, outline=5),
    "bebas_clean": _P("Bebas Clean", font_family="Bebas Neue", bold=False, font_size=110, outline=4, highlight_color="#FFFFFF", max_chars=22),
    "comic_bangers": _P("Comic Punch", font_family="Bangers", bold=False, primary_color="#FFE600", highlight_color="#FFFFFF", font_size=104, outline=6, max_chars=20),
    "slab_impact": _P("Slab Impact", font_family="Alfa Slab One", bold=False, animation="highlight", highlight_color="#FFD400", font_size=84, outline=6),
    "serif_elegant": _P("Serif Elegant", font_family="DM Serif Display", bold=False, uppercase=False, highlight_color="#FFD400", font_size=88, outline=2, shadow=3, max_chars=30),
    "boxed_tiktok": _P("Boxed", font_family="Roboto", background_enabled=True, background_color="#000000", highlight_color="#FFFFFF", font_size=78, outline=6, shadow=0, max_chars=24),
}

def get_preset(preset_id: str) -> dict:
    return STYLE_PRESETS.get(preset_id, STYLE_PRESETS["bold_white"])

print(f"🎭 Registered {len(STYLE_PRESETS)} creator caption presets.")

# ==========================================
# 5. ASS SUBTITLE & CAPTION BUILDER
# ==========================================
def hex_to_ass(hex_color: str, alpha_hex: str = "00") -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR color format."""
    c = hex_color.lstrip("#")
    if len(c) == 6:
        r, g, b = c[0:2], c[2:4], c[4:6]
        return f"&H{alpha_hex}{b}{g}{r}"
    return "&H00FFFFFF"

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS time format H:MM:SS.cs"""
    s = max(0.0, float(seconds))
    hrs = int(s // 3600)
    mins = int((s % 3600) // 60)
    secs = int(s % 60)
    cs = int(round((s - int(s)) * 100))
    if cs >= 100:
        secs += 1
        cs = 0
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"

def build_ass_subtitles(words: list[dict], preset_id: str, output_path: Path, frame_w: int = 1080, frame_h: int = 1920) -> Path:
    preset = get_preset(preset_id)
    
    font_name = preset.get("font_family", "Roboto")
    font_size = preset.get("font_size", 90)
    primary_color = hex_to_ass(preset.get("primary_color", "#FFFFFF"))
    highlight_color = hex_to_ass(preset.get("highlight_color", "#FFD400"))
    outline_color = hex_to_ass(preset.get("outline_color", "#000000"))
    back_color = hex_to_ass(preset.get("background_color", "#000000"), "80" if preset.get("background_enabled") else "00")
    
    bold = -1 if preset.get("bold", True) else 0
    outline = preset.get("outline", 5)
    shadow = preset.get("shadow", 1)
    alignment = 2 if preset.get("position") == "bottom" else (5 if preset.get("position") == "center" else 8)
    
    scaled_font_size = max(16, int(round(font_size * (frame_h / 1920.0))))
    margin_v = int(frame_h * 0.15) if alignment == 2 else 10
    
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {frame_w}
PlayResY: {frame_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{scaled_font_size},{primary_color},{highlight_color},{outline_color},{back_color},{bold},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    events = []
    if not words:
        output_path.write_text(header, encoding="utf-8")
        return output_path

    max_chars = preset.get("max_chars", 22)
    animation = preset.get("animation", "none")
    is_karaoke = preset.get("karaoke", False)
    uppercase = preset.get("uppercase", True)
    
    groups = []
    curr_group = []
    curr_len = 0
    
    for w in words:
        text = w["word"].upper() if uppercase else w["word"]
        w_item = {**w, "text": text}
        if curr_group and (curr_len + len(text) > max_chars):
            groups.append(curr_group)
            curr_group = [w_item]
            curr_len = len(text)
        else:
            curr_group.append(w_item)
            curr_len += len(text) + 1
    if curr_group:
        groups.append(curr_group)
        
    for grp in groups:
        start_t = format_ass_time(grp[0]["start"])
        end_t = format_ass_time(grp[-1]["end"])
        
        if is_karaoke or animation == "highlight":
            line_parts = []
            for item in grp:
                dur_cs = int(round((item["end"] - item["start"]) * 100))
                dur_cs = max(1, dur_cs)
                line_parts.append(f"{{\\k{dur_cs}}}{item['text']}")
            text_str = " ".join(line_parts)
        else:
            text_str = " ".join(item["text"] for item in grp)
            
        events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text_str}")

    full_content = header + "\n".join(events)
    output_path.write_text(full_content, encoding="utf-8")
    return output_path

# ==========================================
# 6. YOUTUBE DOWNLOADER & CLIENT ROTATION
# ==========================================
class InvalidVideoURLError(Exception):
    """Raised when a video URL is invalid or download fails."""
    pass

def _is_auth_error(reason: str) -> bool:
    """True when a failure reason looks like a sign-in / bot / cookie wall."""
    r = (reason or "").lower()
    return any(k in r for k in (
        "sign in", "not a bot", "cookie", "log in", "login", "consent",
        "age", "members-only", "account", "authentication",
    ))

def _is_terminal(reason: str) -> bool:
    """True when no retry (other client) can possibly help, so we stop
    early instead of grinding through every fallback for a dead/blocked link.
    """
    r = (reason or "").lower()
    return any(k in r for k in (
        "unavailable", "been removed", "does not exist", "no longer",
        "unsupported url", "not available in your", "is not a valid",
        "deleted", "terminated",
    ))

_PLAYER_CLIENTS = ["android", "ios", "mweb", "tv", "web_creator"]

def _download_attempts(base_opts: dict) -> list[tuple[str, dict]]:
    """Ordered (label, ydl_opts) attempts without any cookies fallback."""
    attempts: list[tuple[str, dict]] = [("default", dict(base_opts))]
    for client in _PLAYER_CLIENTS:
        attempts.append((
            f"{client} client",
            {**base_opts, "extractor_args": {"youtube": {"player_client": [client]}}},
        ))
    return attempts

def _clean_ydl_error(raw: str) -> str:
    """Turn a raw yt-dlp DownloadError string into one short, readable line."""
    text = _ANSI_RE.sub("", raw or "").strip()
    line = text.splitlines()[0] if text else ""
    line = re.sub(r"^ERROR:\s*", "", line).strip()
    line = re.split(r";\s*(please report|you might want)", line, maxsplit=1)[0].strip()
    line = re.sub(r"^\[[^\]]+\]\s*[^:]*:\s*", "", line)
    return line[:300]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def probe_source_info(filepath: Path) -> dict:
    """Probe video file once and return key stream metadata."""
    import json, subprocess
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(filepath)
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            v = next((s for s in streams if s.get("codec_type") == "video"), {})
            a = next((s for s in streams if s.get("codec_type") == "audio"), {})
            size_mb = filepath.stat().st_size / (1024 * 1024) if filepath.exists() else 0
            info = {
                "width": int(v.get("width", 0)),
                "height": int(v.get("height", 0)),
                "codec": v.get("codec_name", "unknown"),
                "fps": v.get("r_frame_rate", "30/1"),
                "bitrate_kbps": int(fmt.get("bit_rate", 0)) // 1000 if fmt.get("bit_rate") else 0,
                "audio_codec": a.get("codec_name", "none"),
                "size_mb": round(size_mb, 1),
                "duration": float(fmt.get("duration", 0)),
            }
            logger.info(
                "📹 Source Video Probed: %dx%d | Codec=%s | FPS=%s | Audio=%s | Size=%.1fMB | Dur=%.1fs",
                info["width"], info["height"], info["codec"], info["fps"],
                info["audio_codec"], info["size_mb"], info["duration"]
            )
            return info
    except Exception as exc:
        logger.warning("Could not probe source metadata for %s: %s", filepath, exc)
    return {}

def _is_temp_file(path: Path) -> bool:
    """True if path points to a temporary download file (.part, .ytdl, etc.)."""
    name_lower = path.name.lower()
    return (
        name_lower.endswith((".part", ".ytdl", ".temp", ".tmp"))
        or ".part-frag" in name_lower
        or ".part." in name_lower
    )

def _find_completed_path(clip_uuid: str) -> Optional[Path]:
    """Find the non-temporary, completed output file for clip_uuid in DOWNLOADS_DIR."""
    expected_path = DOWNLOADS_DIR / f"{clip_uuid}.mp4"
    if expected_path.exists() and expected_path.stat().st_size > 0 and not _is_temp_file(expected_path):
        return expected_path

    candidates = [
        p for p in DOWNLOADS_DIR.glob(f"{clip_uuid}.*")
        if p.is_file() and p.stat().st_size > 0 and not _is_temp_file(p)
    ]
    if candidates:
        mp4_candidates = [p for p in candidates if p.suffix.lower() == ".mp4"]
        return mp4_candidates[0] if mp4_candidates else candidates[0]

    return None

def download_video_url(
    url: str,
    output_dir: Path = DOWNLOADS_DIR,
    cookies_file: Optional[str] = None,
    max_retries: int = 2
) -> Tuple[Path, str]:
    """Download `url` to downloads/<uuid>.mp4 and return path and title."""
    if not url or not url.strip():
        raise InvalidVideoURLError("No video URL was provided.")

    clip_uuid = uuid.uuid4().hex
    out_template = str(DOWNLOADS_DIR / f"{clip_uuid}.%(ext)s")

    preferred_format = (
        "bestvideo[height<=1080][vcodec^=avc1]+bestaudio/"
        "bestvideo[height<=1080]+bestaudio/"
        "best[height<=1080]/"
        "bestvideo+bestaudio/"
        "best"
    )

    base_opts = {
        "format": preferred_format,
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 15,
        "continuedl": True,
        "nocheckcertificate": True,
    }

    # Extract video title first
    title = "Video"
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            title = info.get("title", "Video")
    except Exception:
        pass

    last_reason = ""
    last_exc: Optional[Exception] = None
    ok = False
    for label, opts in _download_attempts(base_opts):
        logger.info(
            "[DOWNLOAD]\nClient: %s\nFormat selector: %s",
            label, opts.get("format")
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url.strip()])
            ok = True
            logger.info("[DOWNLOAD ATTEMPT SUCCESS] Client: %s", label)
            break
        except Exception as exc:  # noqa: BLE001
            last_reason = _clean_ydl_error(str(exc))
            last_exc = exc
            logger.warning("[DOWNLOAD ATTEMPT FAILED] Client: %s | Reason: %s", label, last_reason)
            if _is_terminal(last_reason):
                break

    if not ok:
        msg = ("Could not download that video. Check the URL is correct, public, "
               "and reachable from this machine.")
        if last_reason:
            msg += f"\nReason: {last_reason}"
        if _is_auth_error(last_reason):
            msg += (
                "\n\nThis video requires YouTube authentication or a bot/sign-in verification, "
                "which is not supported by the cookie-free downloader."
            )
        raise InvalidVideoURLError(msg) from last_exc

    final_path = None
    for _ in range(15):
        final_path = _find_completed_path(clip_uuid)
        if final_path:
            break
        time.sleep(0.2)

    if not final_path or _is_temp_file(final_path):
        raise InvalidVideoURLError(
            "The download completed but no valid output file was produced or the file remained incomplete (.part)."
        )

    info = probe_source_info(final_path)
    if not info or info.get("width", 0) == 0:
        raise InvalidVideoURLError(
            "The downloaded video file is invalid or corrupt (ffprobe failed to validate streams)."
        )

    return final_path, title

# ==========================================
# 7. WHISPER TRANSCRIBER
# ==========================================
from faster_whisper import WhisperModel

_cached_models: dict[str, WhisperModel] = {}

def get_whisper_model(model_size: str = "medium", device: str = "auto") -> tuple[WhisperModel, str]:
    target_device = "cuda" if (device in ("auto", "cuda") and cuda_available) else "cpu"
    compute_type = "float16" if target_device == "cuda" else "int8"
    cache_key = f"{model_size}_{target_device}_{compute_type}"
    
    if cache_key in _cached_models:
        return _cached_models[cache_key], target_device
        
    print(f"⚡ Loading Whisper model '{model_size}' on {target_device.upper()} ({compute_type})...")
    model = WhisperModel(model_size, device=target_device, compute_type=compute_type)
    _cached_models[cache_key] = model
    return model, target_device

def transcribe_video(video_path: Path, model_size: str = "medium", device: str = "auto") -> dict:
    model, used_device = get_whisper_model(model_size, device)
    
    print(f"🎙️ Transcribing {video_path.name} with word-level timestamps...")
    segments, info = model.transcribe(
        str(video_path),
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )
    
    segment_list = []
    all_words = []
    
    for seg in segments:
        seg_words = []
        if seg.words:
            for w in seg.words:
                w_dict = {"word": w.word.strip(), "start": w.start, "end": w.end, "probability": w.probability}
                seg_words.append(w_dict)
                all_words.append(w_dict)
                
        segment_list.append({
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": seg_words
        })
        
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": segment_list,
        "words": all_words,
        "device": used_device,
    }

# ==========================================
# 8. LOCAL CLIP SELECTOR
# ==========================================
STRONG_WORDS = {
    "how", "why", "what", "when", "who", "where", "best", "worst", "never",
    "always", "secret", "mistake", "biggest", "important", "actually", "truth",
    "realize", "realise", "amazing", "incredible", "stop", "avoid", "must",
    "everyone", "nobody", "money", "free", "new", "first", "tip", "tips",
}

def select_clips(transcript: dict, num_clips: int = 3, target_duration: float = 30.0) -> list[dict]:
    segments = transcript.get("segments") or []
    if not segments:
        duration = transcript.get("duration", 60.0)
        step = duration / (num_clips + 1)
        return [{"start": i * step, "end": min(duration, i * step + target_duration), "title": f"Clip {i+1}"} for i in range(num_clips)]
    
    total_duration = transcript.get("duration", segments[-1]["end"])
    
    candidates = []
    for i, start_seg in enumerate(segments):
        start_t = start_seg["start"]
        end_t = start_t + target_duration
        if end_t > total_duration:
            end_t = total_duration
            
        if end_t - start_t < 10.0:
            continue
            
        window_text = []
        word_count = 0
        hook_score = 0
        
        for seg in segments:
            if seg["end"] >= start_t and seg["start"] <= end_t:
                window_text.append(seg["text"])
                for w in seg.get("words", []):
                    word_count += 1
                    if w["word"].lower().strip(".,!?") in STRONG_WORDS:
                        hook_score += 1.5
                        
        combined_text = " ".join(window_text)
        density = word_count / max(1.0, (end_t - start_t))
        score = (hook_score * 2.0) + (density * 1.5)
        
        title = combined_text[:40].strip() + "..." if len(combined_text) > 40 else combined_text
        if not title:
            title = f"Highlight {len(candidates)+1}"
            
        candidates.append({
            "start": start_t,
            "end": end_t,
            "score": score,
            "title": title
        })
        
    candidates.sort(key=lambda x: x["score"], reverse=True)
    
    selected = []
    for cand in candidates:
        overlap = False
        for sel in selected:
            if not (cand["end"] <= sel["start"] or cand["start"] >= sel["end"]):
                overlap = True
                break
        if not overlap:
            selected.append(cand)
            if len(selected) >= num_clips:
                break
                
    selected.sort(key=lambda x: x["start"])
    return selected

# ==========================================
# 9. FFMPEG REFRAMING & SUBTITLE BURNING
# ==========================================
def probe_media_streams(media_path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(media_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed to inspect file: {res.stderr}")
    return json.loads(res.stdout)

def render_clip(
    source_video: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    ass_path: Path,
    aspect_ratio: AspectRatio = AspectRatio.NINE_16,
    fit_mode: FitMode = FitMode.CROP,
    bar_text: str = None
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clip_dur = max(0.1, float(end_time - start_time))

    probe_data = probe_media_streams(source_video)
    streams = probe_data.get("streams", [])
    format_info = probe_data.get("format", {})
    
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        err_msg = f"❌ Cannot render clip: Source media file '{source_video.name}' contains NO video stream. Stopping render."
        print(err_msg)
        raise RuntimeError(err_msg)

    src_w = int(video_stream.get("width", 1080))
    src_h = int(video_stream.get("height", 1920))
    src_vcodec = video_stream.get("codec_name", "h264")
    src_acodec = audio_stream.get("codec_name", "aac") if audio_stream else "N/A"
    pix_fmt = video_stream.get("pix_fmt", "yuv420p")
    color_transfer = video_stream.get("color_transfer", "bt709")
    
    src_bitrate_bps = int(video_stream.get("bit_rate") or format_info.get("bit_rate") or 0)
    src_bitrate_kbps = f"{src_bitrate_bps // 1000} kbps" if src_bitrate_bps > 0 else "Dynamic/Variable"
    src_fps = video_stream.get("r_frame_rate", "30/1")

    print("==================================================")
    print(f"🎬 [QUALITY INSPECTION - RENDER SOURCE]: {source_video.name}")
    print(f"   • Source Resolution: {src_w}x{src_h}")
    print(f"   • Source Bitrate: {src_bitrate_kbps}")
    print(f"   • Source Codec: Video ({src_vcodec}) | Audio ({src_acodec})")
    print(f"   • Pixel Format: {pix_fmt} | Transfer: {color_transfer}")
    print(f"   • Source Frame Rate: {src_fps} fps")

    if aspect_ratio == AspectRatio.NINE_16:
        target_h = max(1920, src_h if src_h % 2 == 0 else src_h - 1)
        target_w = int(round(target_h * 9 / 16))
        if target_w % 2 != 0:
            target_w -= 1
    else:
        target_w = max(1920, src_w if src_w % 2 == 0 else src_w - 1)
        target_h = int(round(target_w * 9 / 16))
        if target_h % 2 != 0:
            target_h -= 1

    if fit_mode == FitMode.SQUARE:
        sq_size = min(target_w, target_h)
        mask_path = ensure_rounded_mask(sq_size, int(sq_size * 0.06))
        filtergraph = (
            f"[0:v]scale={sq_size}:{sq_size}:force_original_aspect_ratio=increase:flags=lanczos,crop={sq_size}:{sq_size}[fg];"
            f"movie='{mask_path}'[mask];"
            f"[fg][mask]alphamerge[rounded];"
            f"color=c=black:s={target_w}x{target_h}:d={clip_dur}[bg];"
            f"[bg][rounded]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]ass='{ass_path}':fontsdir='{FONTS_DIR}'[outv]"
        )
    else:
        filtergraph = (
            f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={target_w}:{target_h},"
            f"ass='{ass_path}':fontsdir='{FONTS_DIR}'[outv]"
        )

    stream_mapping = ["[outv]", "0:a?"]
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_time:.3f}",
        "-to", f"{end_time:.3f}",
        "-i", str(source_video),
        "-filter_complex", filtergraph,
        "-map", stream_mapping[0],
        "-map", stream_mapping[1],
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-c:a", "aac",
        "-b:a", "320k",
        str(output_path)
    ]

    cmd_str = " ".join(cmd)
    print(f"⚡ [FFMPEG COMMAND]:\n   {cmd_str}")

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg render failed:\n{res.stderr[-800:]}")

    out_probe = probe_media_streams(output_path)
    out_v_stream = next((s for s in out_probe.get("streams", []) if s.get("codec_type") == "video"), {})
    out_a_stream = next((s for s in out_probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    out_fmt = out_probe.get("format", {})

    out_w = out_v_stream.get("width", 0)
    out_h = out_v_stream.get("height", 0)
    out_vcodec = out_v_stream.get("codec_name", "h264")
    out_acodec = out_a_stream.get("codec_name", "aac")
    
    out_bitrate_bps = int(out_v_stream.get("bit_rate") or out_fmt.get("bit_rate") or 0)
    out_bitrate_kbps = f"{out_bitrate_bps // 1000} kbps" if out_bitrate_bps > 0 else "Dynamic (CRF 18 High Quality)"

    print(f"🎬 [QUALITY INSPECTION - RENDER OUTPUT]: {output_path.name}")
    print(f"   • Output Resolution: {out_w}x{out_h}")
    print(f"   • Output Bitrate: {out_bitrate_kbps}")
    print(f"   • Output Codec: Video ({out_vcodec}) | Audio ({out_acodec})")
    print(f"   • Output File Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
    print("==================================================")

    return output_path

# ==========================================
# 10. MAIN PIPELINE & ZIP EXPORTER
# ==========================================
def process_video_pipeline(
    video_url: str = None,
    uploaded_file: str = None,
    cookies_file: str = None,
    num_clips: int = 3,
    aspect_ratio: str = "9:16",
    fit_mode: str = "crop",
    caption_style: str = "bold_white",
    compute_device: str = "auto",
    whisper_model: str = "medium",
    clip_duration: float = 30.0,
    save_to_drive: bool = False,
    progress_callback = None
) -> tuple[list[str], str, str]:
    
    def log(msg, pct):
        print(f"[{int(pct*100)}%] {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    job_id = uuid.uuid4().hex[:8]
    job_clip_dir = CLIPS_DIR / job_id
    job_clip_dir.mkdir(parents=True, exist_ok=True)
    
    log("📥 Downloading / processing source video...", 0.05)
    if uploaded_file and os.path.exists(uploaded_file):
        source_path = Path(uploaded_file)
        source_title = source_path.stem
    elif video_url and video_url.strip():
        source_path, source_title = download_video_url(
            url=video_url.strip(), 
            output_dir=DOWNLOADS_DIR, 
            cookies_file=None
        )
    else:
        raise ValueError("Please provide either a valid YouTube URL or upload a video file.")

    log("🎙️ Transcribing audio with Whisper...", 0.25)
    transcript = transcribe_video(source_path, model_size=whisper_model, device=compute_device)
    
    log("🧠 Selecting best viral clip windows...", 0.60)
    selected_clips = select_clips(transcript, num_clips=num_clips, target_duration=clip_duration)
    
    rendered_video_paths = []
    total_clips = len(selected_clips)
    for idx, clip in enumerate(selected_clips):
        pct = 0.70 + (0.25 * (idx / max(1, total_clips)))
        log(f"✂️ Rendering short clip {idx+1}/{total_clips}: '{clip['title']}'...", pct)
        
        clip_words = [
            {"word": w["word"], "start": w["start"] - clip["start"], "end": w["end"] - clip["start"]}
            for w in transcript["words"]
            if w["start"] >= clip["start"] and w["end"] <= clip["end"]
        ]
        
        ass_path = job_clip_dir / f"sub_{idx}.ass"
        ar_enum = AspectRatio.NINE_16 if aspect_ratio == "9:16" else AspectRatio.SIXTEEN_9
        fit_enum = FitMode.SQUARE if fit_mode == "square" else FitMode.CROP
        
        w_dim, h_dim = (1080, 1920) if ar_enum == AspectRatio.NINE_16 or fit_enum == FitMode.SQUARE else (1920, 1080)
        build_ass_subtitles(clip_words, caption_style, ass_path, frame_w=w_dim, frame_h=h_dim)
        
        out_path = job_clip_dir / f"clip_{idx+1}.mp4"
        render_clip(
            source_video=source_path,
            start_time=clip["start"],
            end_time=clip["end"],
            output_path=out_path,
            ass_path=ass_path,
            aspect_ratio=ar_enum,
            fit_mode=fit_enum
        )
        rendered_video_paths.append(str(out_path))

    log("📦 Packaging clips into ZIP download...", 0.95)
    zip_path = EXPORT_DIR / f"ClipForge_Shorts_{job_id}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for vp in rendered_video_paths:
            p = Path(vp)
            zipf.write(p, arcname=p.name)
            
    drive_msg = ""
    if save_to_drive:
        gdrive_dir = mount_gdrive()
        if gdrive_dir:
            dest_job = gdrive_dir / f"Shorts_{job_id}"
            dest_job.mkdir(parents=True, exist_ok=True)
            for vp in rendered_video_paths:
                shutil.copy(vp, dest_job / Path(vp).name)
            shutil.copy(zip_path, dest_job / zip_path.name)
            drive_msg = f" (Saved to Google Drive: {dest_job})"

    log(f"🎉 Complete! Generated {len(rendered_video_paths)} shorts successfully.{drive_msg}", 1.0)
    status_summary = f"### ✅ Successfully generated {len(rendered_video_paths)} clips!\n- **Source**: {source_title}\n- **Whisper Model**: {whisper_model} ({transcript['device'].upper()})\n- **Caption Style**: {caption_style}\n{drive_msg}"
    return rendered_video_paths, str(zip_path), status_summary

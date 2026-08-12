# Clipper-IO

Clipper-IO is a Google Colab-based AI video clipping tool designed to transform long-form content into engaging, viral, styled shorts. It wraps a high-performance Python processing engine inside a premium, CapCut-style 3-column web interface.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/itxunknown39-web/Clipper-IO/blob/main/clipforge_colab(1).ipynb)

---

## Features

- **AI-Powered Video Clipping**: Intelligent hook and speech-density scanning to automatically identify the most engaging parts of a video.
- **YouTube Video Downloading**: Production-grade client-rotating download engine with automatic fallbacks for maximum compatibility.
- **Automatic Transcription**: Fast, word-level audio transcription powered by `faster-whisper`.
- **Vertical 9:16 Shorts**: Automatic cropping or centered layout optimization for reels, TikTok, and YouTube Shorts.
- **Creator Caption Styles**: Burn styled ASS subtitles directly onto the video with support for 13 custom visual presets (including MrBeast, Hormozi, Karaoke, Boxed, and more).
- **GPU Acceleration**: Fully optimized for Google Colab GPU runtimes for fast rendering.
- **Custom Web UI**: Premium 3-column editor interface with interactive iPhone 17 Pro Max simulator, live player controls, caption studio, and timeline gallery.

---

## How It Works

```
[ YouTube URL / Local Upload ]
              ↓
  [ Client-Rotated Downloader ]
              ↓
    [ downloads/<uuid>.mp4 ]
              ↓
    [ faster-whisper Audio ]
              ↓
 [ Hook Selection & Transcripts ]
              ↓
 [ ASS Captions & Presets Render ]
              ↓
       [ FFmpeg Export ]
```

---

## Google Colab Setup

To run Clipper-IO in Google Colab:

1. Click the **Open in Colab** badge at the top of this file.
2. In Google Colab, open the files panel in the left sidebar.
3. Drag and drop the `frontend` and `backend` folders from your cloned repository into the Colab workspace root.
4. Execute cells 1 through 11 to install requirements and download necessary resources.
5. Execute the final cell (Section 12) to spin up the local server and start the public sharing tunnel.
6. Open the printed **Public Share URL** (e.g. `https://xxxx.gradio.live`) to access the video editor.

---

## Usage

1. **Upload / Input Video**: Paste a YouTube link or drag and drop your local video file.
2. **Configure Settings**: Select the number of clips, clip duration, and vertical layout styles (Crop Fill or Square Reel).
3. **Select Caption Presets**: Preview and apply typography themes in the Caption Studio cards.
4. **Generate**: Click **Generate Viral Shorts** to start processing. The bottom timeline will show live generation progress.
5. **Preview & Download**: Play compiled shorts inside the iPhone simulator or click **Download All (ZIP)** to retrieve the outputs.

---

## Project Structure

```
Clipper-IO/
├── backend/
│   ├── __init__.py                # Package initializer
│   └── server.py                  # FastAPI route server bridge
├── frontend/
│   ├── index.html                 # Custom editor HTML structure
│   ├── style.css                  # Dark themes and visual styling
│   ├── app.js                     # Interactive event handlers and polling client
│   ├── downloader.py              # Local package downloader implementation
│   ├── models.py                  # Downloader data models
│   └── paths.py                   # Path config mapper
├── clipforge_colab(1).ipynb       # Google Colab notebook
├── downloader.py                  # Root package downloader implementation
├── requirements.txt               # Dependencies list
├── .gitignore                     # Git ignore rules
└── README.md                      # Documentation
```

---

## Requirements

The project dependencies are listed in `requirements.txt`:
- `yt-dlp`
- `faster-whisper`
- `indic-transliteration`
- `gradio`
- `requests`
- `pydantic>=2.0`
- `fastapi`
- `uvicorn`

---

## Notes / Limitations

- **Cookie-Free Downloading**: The downloader utilizes player client rotation (default web, Android, iOS, mobile web, TV, web creator) to bypass bot checking. It does not use browser cookies or cookie files.
- **Hardware Requirements**: Running locally requires NVIDIA CUDA drivers and a compatible GPU for optimal transcription and rendering speed. In Colab, make sure your runtime type is set to **L4 GPU** or **T4 GPU**.

---

## License

This project is licensed under the MIT License.
# Clipper-IO

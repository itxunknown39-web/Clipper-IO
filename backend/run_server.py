import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set current working directory to project root so relative paths work
os.chdir(project_root)

# Import pipeline and server
from backend.pipeline import (
    process_video_pipeline,
    STYLE_PRESETS,
    CLIPS_DIR,
    EXPORT_DIR,
    DOWNLOADS_DIR
)
import backend.server as cf_server
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Initialize FastAPI application
app = FastAPI(title="ClipForge Premium Backend")

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize backend bridge configuration
cf_server.init_backend(
    pipeline_fn=process_video_pipeline,
    presets=STYLE_PRESETS,
    clips_dir=CLIPS_DIR,
    exports_dir=EXPORT_DIR,
    downloads_dir=DOWNLOADS_DIR
)

# Inject routes into FastAPI app
cf_server.apply_routes_to_app(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🎬 Starting FastAPI Server on port {port}...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

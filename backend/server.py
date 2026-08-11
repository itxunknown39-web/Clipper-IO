# ==========================================================================
# CLIPFORGE FASTAPI BACKEND BRIDGE
# Bridge routes connecting the custom frontend UI to notebook processing logic.
# ==========================================================================

import os
import uuid
import threading
from pathlib import Path
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
from pydantic import BaseModel

# --- GLOBAL BACKEND STATE ---
_pipeline_fn = None
_presets = {}
_clips_dir = None
_exports_dir = None
_downloads_dir = None

# Active background jobs state
jobs: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=2)

def init_backend(pipeline_fn, presets, clips_dir, exports_dir, downloads_dir):
    '''Initialize backend globals from notebook context.'''
    global _pipeline_fn, _presets, _clips_dir, _exports_dir, _downloads_dir
    _pipeline_fn = pipeline_fn
    _presets = presets
    _clips_dir = Path(clips_dir)
    _exports_dir = Path(exports_dir)
    _downloads_dir = Path(downloads_dir)
    
    # Ensure directories exist
    _clips_dir.mkdir(parents=True, exist_ok=True)
    _exports_dir.mkdir(parents=True, exist_ok=True)
    _downloads_dir.mkdir(parents=True, exist_ok=True)
    print(f"⚡ Backend API bridge initialized. Static paths: {_clips_dir}, {_exports_dir}")

# --- DATA MODELS ---
class GenerateRequest(BaseModel):
    video_url: str = ""
    uploaded_file: str = ""
    cookies_file: str = ""
    num_clips: int = 3
    aspect_ratio: str = "9:16"
    fit_mode: str = "crop"
    caption_style: str = "bold_white"
    whisper_model: str = "medium"
    compute_device: str = "auto"
    clip_duration: float = 30.0
    save_to_drive: bool = False

# --- REQUEST HANDLERS ---
async def get_presets():
    '''Retrieve STYLE_PRESETS.'''
    return JSONResponse(_presets)

async def upload_file(file: UploadFile = File(...)):
    '''Handle uploading video files or cookies.txt.'''
    try:
        filename = file.filename
        # Save to downloads dir
        dest_path = _downloads_dir / filename
        with open(dest_path, "wb") as f:
            content = await file.read()
            f.write(content)
        return {"filename": filename, "filepath": str(dest_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

def background_job_worker(job_id: str, req: GenerateRequest):
    '''Worker running in a separate thread executing the video-processing pipeline.'''
    def progress_callback(pct: float, msg: str):
        # Update progress in active jobs mapping
        if job_id in jobs:
            jobs[job_id]["progress"] = pct
            jobs[job_id]["message"] = msg

    try:
        print(f"🎬 Starting background video generation job: {job_id}")
        
        # Prepare file names
        uploaded = req.uploaded_file if req.uploaded_file else None
        url = req.video_url if req.video_url else None
        cookies = req.cookies_file if req.cookies_file else None
        
        # Run existing pipeline function
        clips, zip_path, summary = _pipeline_fn(
            video_url=url,
            uploaded_file=uploaded,
            cookies_file=cookies,
            num_clips=req.num_clips,
            aspect_ratio=req.aspect_ratio,
            fit_mode=req.fit_mode,
            caption_style=req.caption_style,
            compute_device=req.compute_device,
            whisper_model=req.whisper_model,
            clip_duration=req.clip_duration,
            save_to_drive=req.save_to_drive,
            progress_callback=progress_callback
        )
        
        # Extract clip basenames (for frontend serving relative to /clips/{job_id}/)
        clip_filenames = []
        pipeline_job_id = job_id  # Fallback
        
        for c in clips:
            c_path = Path(c)
            clip_filenames.append(c_path.name)
            # The clip path is CLIPS_DIR / pipeline_job_id / clip_name.mp4
            pipeline_job_id = c_path.parent.name
            
        zip_filename = Path(zip_path).name

        jobs[job_id].update({
            "status": "completed",
            "progress": 1.0,
            "message": "Complete!",
            "clips": clip_filenames,
            "pipeline_job_id": pipeline_job_id,
            "zip_path": zip_filename,
            "summary": summary
        })
        print(f"✅ Background job completed: {job_id} (Pipeline Job ID: {pipeline_job_id})")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id].update({
            "status": "failed",
            "error": str(e),
            "message": f"Failed: {str(e)}"
        })
        print(f"❌ Background job failed: {job_id}. Reason: {e}")

async def generate_clips(req: GenerateRequest):
    '''Trigger background clipper generation.'''
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "message": "Initiating processing queue...",
        "clips": [],
        "zip_path": "",
        "error": ""
    }
    
    # Run in background executor thread so we don't block the FastAPI async event loop
    executor.submit(background_job_worker, job_id, req)
    return {"job_id": job_id}

async def get_status(job_id: str):
    '''Query job status.'''
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Map fields to custom format
    return JSONResponse({
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "clips": [f"{job.get('pipeline_job_id', job_id)}/{c}" for c in job["clips"]],
        "zip_path": job["zip_path"],
        "error": job.get("error", ""),
        "summary": job.get("summary", "")
    })

# --- ROUTE INJECTOR LAYER ---
def apply_routes_to_app(app: FastAPI):
    '''Inject custom endpoints and static folder mounts into the Gradio FastAPI application.'''
    
    # Mount files (for playing clips and downloading ZIP archives)
    app.mount("/static", StaticFiles(directory="frontend"), name="custom_static")
    app.mount("/clips", StaticFiles(directory=str(_clips_dir)), name="clips_static")
    app.mount("/exports", StaticFiles(directory=str(_exports_dir)), name="exports_static")
    
    # Register router API endpoints
    app.add_api_route("/api/presets", get_presets, methods=["GET"])
    app.add_api_route("/api/upload", upload_file, methods=["POST"])
    app.add_api_route("/api/generate", generate_clips, methods=["POST"])
    app.add_api_route("/api/status/{job_id}", get_status, methods=["GET"])
    
    # Override root "/" route to serve custom premium index.html.
    def home_endpoint():
        index_path = Path("frontend/index.html")
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        else:
            return HTMLResponse("<h2>Error: frontend/index.html not found.</h2>")
            
    route = APIRoute("/", home_endpoint, methods=["GET"])
    app.routes.insert(0, route)
    print("🚀 Custom routes injected into Gradio FastAPI application server!")

/* ==========================================================================
   CLIPFORGE INTERACTIVE FRONTEND JS
   Form handling, custom video player, file uploads, and async polling status.
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // --- STORES & APP STATE ---
    let appState = {
        activeTab: "yt-url-tab",
        uploadedVideoPath: "",
        uploadedCookiesPath: "",
        activePreset: "bold_white",
        activeJobId: null,
        pollingInterval: null,
        presets: {},
        currentLayout: "9:16" // Default vertical
    };

    // --- DOM ELEMENT CACHE ---
    const elements = {
        // Tabs
        tabBtns: document.querySelectorAll(".tab-btn"),
        tabPanes: document.querySelectorAll(".tab-pane"),
        
        // Collapsible Controls
        toggleAdvancedBtn: document.getElementById("toggle-advanced-btn"),
        advancedContent: document.getElementById("advanced-content"),
        
        // Input Fields
        ytUrlInput: document.getElementById("yt-url"),
        videoFileInput: document.getElementById("video-file"),
        videoFileLabel: document.getElementById("video-file-label"),
        videoDragZone: document.getElementById("video-drag-zone"),
        numClipsInput: document.getElementById("num-clips"),
        numClipsVal: document.getElementById("num-clips-val"),
        clipDurInput: document.getElementById("clip-dur"),
        clipDurVal: document.getElementById("clip-dur-val"),
        aspectRatioSelect: document.getElementById("aspect-ratio"),
        fitModeSelect: document.getElementById("fit-mode"),
        whisperModelSelect: document.getElementById("whisper-model"),
        computeDeviceSelect: document.getElementById("compute-device"),
        saveDriveCheckbox: document.getElementById("save-drive"),
        
        // Buttons & Loading
        generateBtn: document.getElementById("generate-btn"),
        generateSpinner: document.getElementById("generate-spinner"),
        downloadZipBtn: document.getElementById("download-zip-btn"),
        
        // Preview Frame (iPhone)
        phoneFrame: document.getElementById("phone-frame"),
        previewVideo: document.getElementById("preview-video"),
        playerPlaceholder: document.getElementById("player-placeholder"),
        subtitlePreviewBox: document.getElementById("subtitle-preview-box"),
        activePresetBadge: document.getElementById("active-preset-badge"),
        
        // Custom Player Controls
        playerControls: document.getElementById("player-controls"),
        playPauseBtn: document.getElementById("play-pause-btn"),
        centerPlayBtn: document.getElementById("center-play-btn"),
        timelineProgressFill: document.getElementById("timeline-progress-fill"),
        timelineProgressHandle: document.getElementById("timeline-progress-handle"),
        timelineScrubberContainer: document.getElementById("timeline-scrubber-container"),
        currentTimeLbl: document.getElementById("current-time"),
        durationTimeLbl: document.getElementById("duration-time"),
        volumeBtn: document.getElementById("volume-btn"),
        fullscreenBtn: document.getElementById("fullscreen-btn"),
        
        // Presets List Grid
        presetsGrid: document.getElementById("presets-grid"),
        
        // Timeline & Generated Outputs
        timelineEmpty: document.getElementById("timeline-empty"),
        generationProgressPanel: document.getElementById("generation-progress-panel"),
        progressStepMsg: document.getElementById("progress-step-msg"),
        progressPercentageLbl: document.getElementById("progress-percentage-lbl"),
        progressTimelineFill: document.getElementById("progress-timeline-fill"),
        clipsCountBadge: document.getElementById("clips-count-badge"),
        clipsGallery: document.getElementById("clips-gallery"),
        
        // Toast notifications
        toastCenter: document.getElementById("toast-center"),
        uploadProgressContainer: document.getElementById("upload-progress-container"),
        uploadProgressFill: document.getElementById("upload-progress-fill"),
        uploadProgressText: document.getElementById("upload-progress-text")
    };

    // --- TOAST NOTIFICATIONS ---
    function showToast(message, type = "info", duration = 4000) {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        
        // Icon selection based on type
        let icon = "";
        if (type === "success") {
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;
        } else if (type === "error") {
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
        } else {
            icon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
        }
        
        toast.innerHTML = `${icon}<span>${message}</span>`;
        elements.toastCenter.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add("toast-out");
            toast.addEventListener("animationend", () => toast.remove());
        }, duration);
    }

    // --- TAB CONTROLS ---
    elements.tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetPaneId = btn.getAttribute("data-tab");
            
            // Toggle active buttons
            elements.tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            // Toggle panes
            elements.tabPanes.forEach(pane => {
                if (pane.id === targetPaneId) {
                    pane.classList.add("active");
                } else {
                    pane.classList.remove("active");
                }
            });
            
            appState.activeTab = targetPaneId;
        });
    });

    // --- COLLAPSIBLES ---
    function registerCollapsible(trigger, container) {
        trigger.addEventListener("click", () => {
            const wrapper = trigger.parentElement;
            wrapper.classList.toggle("active");
            if (wrapper.classList.contains("active")) {
                container.style.display = "flex";
            } else {
                container.style.display = "none";
            }
        });
    }
    registerCollapsible(elements.toggleAdvancedBtn, elements.advancedContent);

    // --- RANGE SLIDERS SYNCRONIZATION ---
    elements.numClipsInput.addEventListener("input", (e) => {
        elements.numClipsVal.textContent = e.target.value;
    });

    elements.clipDurInput.addEventListener("input", (e) => {
        elements.clipDurVal.textContent = `${e.target.value}s`;
    });

    // --- LANDSCAPE vs VERTICAL PHONE ORIENTATION ---
    elements.aspectRatioSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        appState.currentLayout = val;
        
        if (val === "16:9") {
            elements.phoneFrame.classList.remove("vertical");
            elements.phoneFrame.classList.add("horizontal");
        } else {
            elements.phoneFrame.classList.remove("horizontal");
            elements.phoneFrame.classList.add("vertical");
        }
    });

    // --- FILE UPLOAD LOGIC ---
    function uploadFile(file, type) {
        const formData = new FormData();
        formData.append("file", file);

        // Show progress indicator if uploading video
        const isVideo = type === "video";
        if (isVideo) {
            elements.uploadProgressContainer.style.display = "block";
            elements.uploadProgressFill.style.width = "0%";
            elements.uploadProgressText.textContent = "Uploading: 0%";
        }

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload", true);

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && isVideo) {
                const pct = Math.round((e.loaded / e.total) * 100);
                elements.uploadProgressFill.style.width = `${pct}%`;
                elements.uploadProgressText.textContent = `Uploading: ${pct}%`;
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                const resp = JSON.parse(xhr.responseText);
                if (isVideo) {
                    appState.uploadedVideoPath = resp.filepath;
                    elements.videoFileLabel.textContent = `✓ ${file.name}`;
                    elements.videoFileLabel.style.color = "#10B981";
                    elements.uploadProgressContainer.style.display = "none";
                    showToast("Video uploaded successfully!", "success");
                } else {
                    appState.uploadedCookiesPath = resp.filepath;
                    elements.cookiesFileLabel.textContent = `✓ Cookies Active (${file.name})`;
                    elements.cookiesFileLabel.style.color = "#10B981";
                    showToast("Cookies.txt loaded!", "success");
                }
            } else {
                showToast("File upload failed.", "error");
                if (isVideo) elements.uploadProgressContainer.style.display = "none";
            }
        };

        xhr.onerror = () => {
            showToast("Network upload error.", "error");
            if (isVideo) elements.uploadProgressContainer.style.display = "none";
        };

        xhr.send(formData);
    }

    // Video selector
    elements.videoFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0], "video");
        }
    });



    // Drag-and-drop for video
    ["dragenter", "dragover"].forEach(eventName => {
        elements.videoDragZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            elements.videoDragZone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        elements.videoDragZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            elements.videoDragZone.classList.remove("dragover");
        }, false);
    });

    elements.videoDragZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0 && files[0].type.startsWith("video/")) {
            elements.videoFileInput.files = files;
            uploadFile(files[0], "video");
        } else {
            showToast("Invalid file. Please drop a valid video file.", "error");
        }
    });

    // --- RETRIEVE CAPTION STYLE PRESETS ---
    async function loadPresets() {
        try {
            const resp = await fetch("/api/presets");
            const presets = await resp.json();
            appState.presets = presets;
            
            // Clear grid
            elements.presetsGrid.innerHTML = "";
            
            // Loop through presets and render cards
            Object.keys(presets).forEach(key => {
                const p = presets[key];
                const card = document.createElement("div");
                card.className = `preset-card ${appState.activePreset === key ? "active" : ""}`;
                card.setAttribute("data-preset", key);
                
                // Style preview text according to style rules
                let previewStyleClass = `cf-style-${key}`;
                
                card.innerHTML = `
                    <div class="preset-card-preview">
                        <div class="subtitle-preview-container ${previewStyleClass}">
                            <span class="txt-primary">HELLO</span> <span class="txt-highlight">WORLD</span>
                        </div>
                    </div>
                    <div class="preset-card-info">
                        <span class="preset-name">${p.label || key}</span>
                        <span class="preset-style-lbl">${p.font_family || "Roboto"} • ${p.position || "bottom"}</span>
                    </div>
                `;
                
                card.addEventListener("click", () => {
                    // Remove active from others
                    document.querySelectorAll(".preset-card").forEach(c => c.classList.remove("active"));
                    card.classList.add("active");
                    
                    appState.activePreset = key;
                    elements.activePresetBadge.textContent = `Style: ${p.label || key}`;
                    
                    // Update preview style live
                    updateSubtitlePreviewStyle(key);
                });
                
                elements.presetsGrid.appendChild(card);
            });
        } catch (err) {
            console.error("Failed to load presets:", err);
            showToast("Failed to fetch caption style presets.", "error");
        }
    }

    // Live update of preview captions
    function updateSubtitlePreviewStyle(presetKey) {
        const p = appState.presets[presetKey];
        if (!p) return;
        
        // Remove existing style classes
        elements.subtitlePreviewBox.className = "subtitle-preview-container";
        
        // Set new position class
        if (p.position === "center") {
            elements.subtitlePreviewBox.classList.add("pos-center");
        } else if (p.position === "top") {
            elements.subtitlePreviewBox.classList.add("pos-top");
        } else {
            elements.subtitlePreviewBox.classList.add("pos-bottom");
        }
        
        // Add specific style class
        elements.subtitlePreviewBox.classList.add(`cf-style-${presetKey}`);
        
        // Format text (Uppercase or not)
        const word1 = document.getElementById("sub-word-1");
        const word2 = document.getElementById("sub-word-2");
        if (p.uppercase) {
            word1.textContent = "HELLO";
            word2.textContent = "WORLD!";
        } else {
            word1.textContent = "Hello";
            word2.textContent = "World!";
        }
    }

    // Initial load
    loadPresets();

    // --- CUSTOM VIDEO PLAYER ---
    const video = elements.previewVideo;
    
    function togglePlay() {
        if (video.paused) {
            video.play();
        } else {
            video.pause();
        }
    }

    elements.playPauseBtn.addEventListener("click", togglePlay);
    elements.centerPlayBtn.addEventListener("click", togglePlay);

    video.addEventListener("play", () => {
        // Toggle play/pause SVGs
        document.querySelectorAll(".play-svg").forEach(svg => svg.style.display = "none");
        document.querySelectorAll(".pause-svg").forEach(svg => svg.style.display = "block");
        
        // Hide big center button
        elements.centerPlayBtn.style.opacity = "0";
        setTimeout(() => {
            if (!video.paused) elements.centerPlayBtn.style.display = "none";
        }, 300);
        
        // Hide subtitle preview mockup once actual video is playing (video has burnt in subtitles)
        elements.subtitlePreviewBox.style.display = "none";
    });

    video.addEventListener("pause", () => {
        document.querySelectorAll(".play-svg").forEach(svg => svg.style.display = "block");
        document.querySelectorAll(".pause-svg").forEach(svg => svg.style.display = "none");
        
        // Show big center button
        elements.centerPlayBtn.style.display = "flex";
        setTimeout(() => {
            elements.centerPlayBtn.style.opacity = "1";
        }, 10);
        
        // Show mockup back if it is the start
        if (video.currentTime === 0) {
            elements.subtitlePreviewBox.style.display = "flex";
        }
    });

    // Duration and current time update
    function formatTime(secs) {
        const minutes = Math.floor(secs / 60);
        const seconds = Math.floor(secs % 60);
        return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
    }

    video.addEventListener("loadedmetadata", () => {
        elements.durationTimeLbl.textContent = formatTime(video.duration);
    });

    video.addEventListener("timeupdate", () => {
        elements.currentTimeLbl.textContent = formatTime(video.currentTime);
        const pct = (video.currentTime / video.duration) * 100;
        elements.timelineProgressFill.style.width = `${pct}%`;
        elements.timelineProgressHandle.style.left = `${pct}%`;
    });

    // Seeker scrubbing
    let isScrubbing = false;

    function scrub(e) {
        const rect = elements.timelineScrubberContainer.getBoundingClientRect();
        const pos = (e.clientX - rect.left) / rect.width;
        const boundedPos = Math.max(0, Math.min(1, pos));
        video.currentTime = boundedPos * video.duration;
    }

    elements.timelineScrubberContainer.addEventListener("mousedown", (e) => {
        isScrubbing = true;
        scrub(e);
    });

    document.addEventListener("mousemove", (e) => {
        if (isScrubbing) scrub(e);
    });

    document.addEventListener("mouseup", () => {
        isScrubbing = false;
    });

    // Volume button click (mute/unmute)
    elements.volumeBtn.addEventListener("click", () => {
        video.muted = !video.muted;
        if (video.muted) {
            elements.volumeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>`;
        } else {
            elements.volumeBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`;
        }
    });

    // Fullscreen toggling
    elements.fullscreenBtn.addEventListener("click", () => {
        if (!document.fullscreenElement) {
            elements.phoneFrame.requestFullscreen().catch(err => {
                showToast(`Error enabling fullscreen: ${err.message}`, "error");
            });
        } else {
            document.exitFullscreen();
        }
    });

    // --- GENERATE / PIPELINE LOGIC ---
    elements.generateBtn.addEventListener("click", async () => {
        if (appState.activeJobId) {
            showToast("A generation task is already running.", "info");
            return;
        }

        // Gather variables
        const payload = {
            video_url: appState.activeTab === "yt-url-tab" ? elements.ytUrlInput.value.trim() : "",
            uploaded_file: appState.activeTab === "upload-video-tab" ? appState.uploadedVideoPath : "",
            cookies_file: "",
            num_clips: parseInt(elements.numClipsInput.value),
            aspect_ratio: elements.aspectRatioSelect.value,
            fit_mode: elements.fitModeSelect.value,
            caption_style: appState.activePreset,
            whisper_model: elements.whisperModelSelect.value,
            compute_device: elements.computeDeviceSelect.value,
            clip_duration: parseFloat(elements.clipDurInput.value),
            save_to_drive: elements.saveDriveCheckbox.checked
        };

        // Validate input
        if (appState.activeTab === "yt-url-tab" && !payload.video_url) {
            showToast("Please enter a valid YouTube video link.", "error");
            return;
        }
        if (appState.activeTab === "upload-video-tab" && !payload.uploaded_file) {
            showToast("Please upload a local video file first.", "error");
            return;
        }

        // Set UI loading state
        elements.generateBtn.disabled = true;
        elements.generateSpinner.style.display = "block";
        elements.generateBtn.querySelector(".btn-text").textContent = "GENERATING CLIPS...";

        // Set Timeline States
        elements.timelineEmpty.style.display = "none";
        elements.clipsGallery.style.display = "none";
        elements.downloadZipBtn.style.display = "none";
        elements.generationProgressPanel.style.display = "flex";

        // Reset progress steps
        document.querySelectorAll(".stage-dot").forEach(dot => {
            dot.className = "stage-dot";
        });
        document.getElementById("stage-dl").classList.add("active");
        elements.progressTimelineFill.style.width = "0%";
        elements.progressPercentageLbl.textContent = "0%";
        elements.progressStepMsg.textContent = "Queuing pipeline task...";

        try {
            const resp = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (resp.status !== 200) {
                const errData = await resp.json();
                throw new Error(errData.detail || "Server error initiating pipeline.");
            }

            const data = await resp.json();
            appState.activeJobId = data.job_id;
            
            showToast("Pipeline started! Processing clips...", "info");
            
            // Start Polling
            startPollingStatus(data.job_id);

        } catch (err) {
            showToast(err.message, "error");
            resetGenerateBtn();
            elements.generationProgressPanel.style.display = "none";
            elements.timelineEmpty.style.display = "flex";
        }
    });

    function resetGenerateBtn() {
        appState.activeJobId = null;
        elements.generateBtn.disabled = false;
        elements.generateSpinner.style.display = "none";
        elements.generateBtn.querySelector(".btn-text").textContent = "🚀 GENERATE VIRAL SHORTS";
    }

    function startPollingStatus(jobId) {
        if (appState.pollingInterval) clearInterval(appState.pollingInterval);

        appState.pollingInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/status/${jobId}`);
                const data = await resp.json();

                if (data.status === "processing") {
                    // Update progress UI
                    const pct = Math.round(data.progress * 100);
                    elements.progressPercentageLbl.textContent = `${pct}%`;
                    elements.progressTimelineFill.style.width = `${pct}%`;
                    elements.progressStepMsg.textContent = data.message || "Running pipeline...";

                    // Map stages
                    updateProgressStages(data.progress, data.message);

                } else if (data.status === "completed") {
                    clearInterval(appState.pollingInterval);
                    showToast("Shorts generated successfully!", "success");
                    
                    // Display results
                    renderClipsTimeline(jobId, data.clips, data.zip_path);
                    
                    resetGenerateBtn();

                } else if (data.status === "failed") {
                    clearInterval(appState.pollingInterval);
                    showToast(`Error: ${data.error}`, "error", 8000);
                    
                    elements.generationProgressPanel.style.display = "none";
                    elements.timelineEmpty.style.display = "flex";
                    resetGenerateBtn();
                }

            } catch (err) {
                console.error("Error polling job status:", err);
            }
        }, 1500);
    }

    // Match pipeline logs to bottom timeline visual stages
    function updateProgressStages(progress, message) {
        const msg = (message || "").toLowerCase();
        
        // Remove active class from all dots
        document.querySelectorAll(".stage-dot").forEach(d => d.classList.remove("active"));

        const stageDl = document.getElementById("stage-dl");
        const stageTrans = document.getElementById("stage-trans");
        const stageSelect = document.getElementById("stage-select");
        const stageCaption = document.getElementById("stage-caption");
        const stageRender = document.getElementById("stage-render");

        // Helper to mark complete
        const setDone = (el) => { el.className = "stage-dot done"; };
        const setActive = (el) => { el.className = "stage-dot active"; };

        if (progress < 0.25 || msg.includes("download")) {
            setActive(stageDl);
        } else if (progress < 0.60 || msg.includes("transcrib")) {
            setDone(stageDl);
            setActive(stageTrans);
        } else if (progress < 0.70 || msg.includes("select") || msg.includes("windows")) {
            setDone(stageDl);
            setDone(stageTrans);
            setActive(stageSelect);
        } else if (progress < 0.80 || msg.includes("caption") || msg.includes("ass")) {
            setDone(stageDl);
            setDone(stageTrans);
            setDone(stageSelect);
            setActive(stageCaption);
        } else {
            setDone(stageDl);
            setDone(stageTrans);
            setDone(stageSelect);
            setDone(stageCaption);
            setActive(stageRender);
        }
    }

    // Populate gallery elements
    function renderClipsTimeline(jobId, clipsList, zipFilename) {
        elements.generationProgressPanel.style.display = "none";
        elements.clipsGallery.innerHTML = "";
        
        if (!clipsList || clipsList.length === 0) {
            elements.timelineEmpty.style.display = "flex";
            elements.clipsCountBadge.textContent = "0 Clips";
            return;
        }

        elements.clipsCountBadge.textContent = `${clipsList.length} Clips`;
        elements.clipsGallery.style.display = "flex";

        clipsList.forEach((clipName, idx) => {
            const card = document.createElement("div");
            card.className = "clip-card";
            const clipUrl = `/clips/${jobId}/${clipName}`;

            card.innerHTML = `
                <div class="clip-thumb-preview">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    <span class="clip-dur-badge">${elements.clipDurInput.value}s</span>
                </div>
                <div class="clip-details">
                    <div class="clip-title-info">
                        <span class="clip-number">Clip ${idx + 1}</span>
                        <span class="clip-desc">${clipName}</span>
                    </div>
                    <div class="clip-actions">
                        <button class="clip-card-btn play-btn" title="Preview Clip">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        </button>
                        <a href="${clipUrl}" download class="clip-card-btn download-btn" title="Download Clip">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        </a>
                    </div>
                </div>
            `;

            // Play clip action
            card.querySelector(".play-btn").addEventListener("click", (e) => {
                e.stopPropagation();
                loadVideoIntoPreview(clipUrl, `Clip ${idx + 1}`);
                
                // Set card active visual
                document.querySelectorAll(".clip-card").forEach(c => c.classList.remove("active"));
                card.classList.add("active");
            });

            // Card click plays
            card.addEventListener("click", () => {
                loadVideoIntoPreview(clipUrl, `Clip ${idx + 1}`);
                document.querySelectorAll(".clip-card").forEach(c => c.classList.remove("active"));
                card.classList.add("active");
            });

            elements.clipsGallery.appendChild(card);
        });

        // Set ZIP Download
        if (zipFilename) {
            elements.downloadZipBtn.style.display = "flex";
            // Remove old listeners to avoid multiple downloads
            const newZipBtn = elements.downloadZipBtn.cloneNode(true);
            elements.downloadZipBtn.parentNode.replaceChild(newZipBtn, elements.downloadZipBtn);
            elements.downloadZipBtn = newZipBtn;
            
            elements.downloadZipBtn.addEventListener("click", () => {
                window.open(`/exports/${zipFilename}`, "_blank");
            });
        }
    }

    function loadVideoIntoPreview(url, label) {
        // Stop playing current
        video.pause();
        
        // Hide placeholder, show video tag
        elements.playerPlaceholder.style.display = "none";
        video.style.display = "block";
        
        // Set source
        video.src = url;
        video.load();
        
        // Play
        video.play().catch(err => {
            console.log("Auto play prevented:", err);
        });
        
        // Hide overlay preview style (subtitles are burned in the file)
        elements.subtitlePreviewBox.style.display = "none";
        
        showToast(`Loaded ${label} into player.`, "info");
    }
});

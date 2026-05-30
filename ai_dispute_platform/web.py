from __future__ import annotations

import argparse
import queue
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from ai_dispute_platform.pipeline.dispute_pipeline import DisputePipeline

UPLOAD_BASE = Path(tempfile.gettempdir()) / "ai_dispute_platform_web"
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf"}

app = Flask(__name__)
job_queue: queue.Queue[str] = queue.Queue()
job_status: dict[str, dict] = {}
job_lock = threading.Lock()

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI Dispute Platform</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .page { max-width: 900px; margin: 24px auto; padding: 24px; background: #fff; border-radius: 10px; box-shadow: 0 2px 14px rgba(0,0,0,.08); }
        h1 { margin-top: 0; }
        .drop-area { padding: 36px; border: 2px dashed #0078d4; border-radius: 12px; text-align: center; color: #333; background: #f9fbff; cursor: pointer; }
        .drop-area.dragover { background: #e5f1ff; }
        .status { margin-top: 18px; }
        .downloads { margin-top: 18px; }
        .downloads a { display: inline-block; margin-right: 14px; margin-bottom: 8px; }
        .note { color: #555; margin-top: 12px; font-size: 0.95rem; }
        button { background: #0078d4; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; }
        button:disabled { background: #999; cursor: not-allowed; }
        input[type=file] { display: none; }
    </style>
</head>
<body>
<div class="page">
    <h1>AI Dispute Processing</h1>
    <p>Upload a PDF credit report to generate Metro 2 dispute output and review reports.</p>
    <div class="drop-area" id="dropArea">
        <p>Drag and drop a PDF file here, or click to select.</p>
        <button id="browseButton" type="button">Select PDF</button>
        <input id="fileInput" type="file" accept="application/pdf" />
    </div>
    <div class="status" id="statusArea"></div>
    <div class="downloads" id="downloads"></div>
    <div class="note">
        Note: This web interface is intended for local or private network use only. No authentication is enabled.
    </div>
</div>
<script>
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInput');
const browseButton = document.getElementById('browseButton');
const statusArea = document.getElementById('statusArea');
const downloads = document.getElementById('downloads');

browseButton.addEventListener('click', () => fileInput.click());

['dragenter', 'dragover'].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropArea.classList.add('dragover');
  }, false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropArea.classList.remove('dragover');
  }, false);
});

dropArea.addEventListener('drop', (e) => {
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    uploadFile(files[0]);
  }
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) {
    uploadFile(fileInput.files[0]);
  }
});

function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    statusArea.textContent = 'Only PDF files are supported.';
    return;
  }
  statusArea.textContent = 'Uploading...';
  downloads.innerHTML = '';

  const formData = new FormData();
  formData.append('file', file);

  fetch('/upload', { method: 'POST', body: formData })
    .then(response => response.json())
    .then(data => {
      if (data.job_id) {
        statusArea.textContent = 'Upload complete. Processing...';
        pollStatus(data.job_id);
      } else {
        statusArea.textContent = 'Upload failed.';
      }
    })
    .catch(() => {
      statusArea.textContent = 'Upload failed. Please try again.';
    });
}

function pollStatus(jobId) {
  fetch(`/status/${jobId}`)
    .then(response => response.json())
    .then(data => {
      statusArea.textContent = data.message;
      if (data.status === 'completed') {
        downloads.innerHTML = '';
        data.files.forEach(file => {
          const link = document.createElement('a');
          link.href = file.url;
          link.textContent = file.label;
          link.download = file.label;
          downloads.appendChild(link);
        });
      } else if (data.status === 'failed') {
        statusArea.textContent = `Processing failed: ${data.message}`;
      } else {
        setTimeout(() => pollStatus(jobId), 1200);
      }
    })
    .catch(() => {
      statusArea.textContent = 'Unable to get status. Retrying...';
      setTimeout(() => pollStatus(jobId), 2000);
    });
}
</script>
</body>
</html>
"""


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def create_job_dir(job_id: str) -> Path:
    path = UPLOAD_BASE / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_file_list(job_dir: Path, stem: str) -> list[dict[str, str]]:
    files = []
    candidates = [
        (job_dir / f"{stem}.dat", "Metro 2 File"),
        (job_dir / f"{stem}.csv", "CSV Output"),
        (job_dir / f"{stem}_report.txt", "TXT Report"),
        (job_dir / f"{stem}_report.html", "HTML Report"),
        (job_dir / f"{stem}_report.pdf", "PDF Report"),
    ]
    for path, label in candidates:
        if path.exists():
            files.append({"url": f"/download/{job_dir.name}/{path.name}", "label": label})
    return files


def start_worker() -> None:
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()


def worker_loop() -> None:
    pipeline = DisputePipeline()
    while True:
        job_id = job_queue.get()
        with job_lock:
            job_status[job_id]["status"] = "processing"
            job_status[job_id]["message"] = "Processing file"
        job_dir = UPLOAD_BASE / job_id
        upload_path = job_dir / "upload.pdf"
        stem = job_id
        try:
            output_dat = job_dir / f"{stem}.dat"
            output_csv = job_dir / f"{stem}.csv"
            letter_dir = job_dir / f"{stem}_letters"
            result = pipeline.run(upload_path, output_dat, output_csv, letter_dir)
            upload_path.unlink(missing_ok=True)
            with job_lock:
                job_status[job_id]["status"] = "completed"
                job_status[job_id]["message"] = "Processing complete"
                job_status[job_id]["files"] = build_file_list(job_dir, stem)
                job_status[job_id]["result"] = result
        except Exception as exc:
            with job_lock:
                job_status[job_id]["status"] = "failed"
                job_status[job_id]["message"] = str(exc)
                job_status[job_id]["error"] = traceback.format_exception(type(exc), exc, exc.__traceback__)
        finally:
            job_queue.task_done()


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    filename = secure_filename(file.filename)
    job_id = uuid.uuid4().hex
    job_dir = create_job_dir(job_id)
    upload_path = job_dir / "upload.pdf"
    file.save(upload_path)

    with job_lock:
        job_status[job_id] = {
            "status": "queued",
            "message": "Waiting to process",
            "files": [],
        }

    job_queue.put(job_id)
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id: str):
    with job_lock:
        status_info = job_status.get(job_id)
    if not status_info:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": status_info["status"],
        "message": status_info["message"],
        "files": status_info.get("files", []),
        "error": status_info.get("error", None),
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id: str, filename: str):
    with job_lock:
        status_info = job_status.get(job_id)
    if not status_info:
        return abort(404)

    job_dir = UPLOAD_BASE / job_id
    file_path = job_dir / filename
    if not file_path.exists() or not file_path.is_file():
        return abort(404)

    if not any(file_path.name == entry["url"].split('/')[-1] for entry in status_info.get("files", [])):
        return abort(403)

    return send_file(file_path, as_attachment=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI Dispute Platform Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args(argv)

    UPLOAD_BASE.mkdir(parents=True, exist_ok=True)
    start_worker()
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

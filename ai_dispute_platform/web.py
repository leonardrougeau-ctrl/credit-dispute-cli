from __future__ import annotations

import argparse
import logging
import os
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

# Configure audit logging
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_handler = logging.FileHandler('audit.log')
    audit_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    audit_logger.addHandler(audit_handler)

UPLOAD_BASE = Path(tempfile.gettempdir()) / "ai_dispute_platform_web"
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
MIN_FILE_SIZE = 1024  # 1KB minimum

app = Flask(__name__)
job_queue: queue.Queue[str] = queue.Queue()
job_status: dict[str, dict] = {}
job_lock = threading.Lock()


def secure_delete(file_path: str) -> None:
    """Overwrite a file three times with random data before deleting it."""
    abs_path = Path(file_path).resolve()
    if not abs_path.exists():
        return
    
    try:
        file_size = abs_path.stat().st_size
        if file_size == 0:
            abs_path.unlink()
            return
        
        # Three-pass overwrite with random data
        for _ in range(3):
            with open(abs_path, "wb") as f:
                f.write(os.urandom(file_size))
        
        abs_path.unlink()
    except Exception as e:
        audit_logger.warning(f"Failed to securely delete {file_path}: {e}")
        # Fall back to regular delete
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass


def log_audit(event: str, ip_address: str, filename: str = None, result: str = None, output_file: str = None) -> None:
    """Log audit events with timestamp, IP, filename, result, and output."""
    log_msg = f"Event={event} | IP={ip_address}"
    if filename:
        log_msg += f" | File={filename}"
    if result:
        log_msg += f" | Result={result}"
    if output_file:
        log_msg += f" | Output={output_file}"
    audit_logger.info(log_msg)


def verify_pdf_file(file_path: Path) -> tuple[bool, str]:
    """Verify that file is actually a PDF using magic numbers."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
        
        # Check PDF magic number
        if not header.startswith(b'%PDF'):
            return False, "File is not a valid PDF (invalid header)"
        
        return True, "Valid PDF"
    except Exception as e:
        return False, f"Error verifying PDF: {str(e)}"


def validate_upload_file(file) -> tuple[bool, str]:
    """Validate uploaded file before processing."""
    # Check filename
    if not file.filename:
        return False, "No filename provided"
    
    # Check extension
    if not allowed_file(file.filename):
        return False, "Only PDF files are allowed"
    
    # Check file size
    file_size = len(file.read())
    file.seek(0)
    
    if file_size < MIN_FILE_SIZE:
        return False, f"File too small (minimum {MIN_FILE_SIZE} bytes)"
    
    if file_size > MAX_FILE_SIZE:
        return False, f"File too large (maximum {MAX_FILE_SIZE} bytes)"
    
    return True, "Valid file"

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
        Note: This web interface is intended for local or private network use only. 
        <strong>All uploads and access are logged for audit and security purposes.</strong>
        See <code>audit.log</code> for activity records.
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


def cleanup_old_jobs(max_age_hours: int = 24) -> None:
    """Periodically remove job directories older than max_age_hours to prevent disk exhaustion."""
    import time
    from datetime import datetime, timedelta
    
    cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).timestamp()
    
    try:
        for job_dir in UPLOAD_BASE.iterdir():
            if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff_time:
                # Check if job is no longer in queue
                with job_lock:
                    if job_dir.name not in job_status or job_status[job_dir.name].get("status") == "completed":
                        shutil.rmtree(job_dir, ignore_errors=True)
                        audit_logger.info(f"Cleaned up old job directory: {job_dir.name}")
    except Exception as e:
        audit_logger.warning(f"Error during job cleanup: {e}")


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
            # Securely delete uploaded PDF
            secure_delete(str(upload_path))
            with job_lock:
                job_status[job_id]["status"] = "completed"
                job_status[job_id]["message"] = "Processing complete"
                job_status[job_id]["files"] = build_file_list(job_dir, stem)
                job_status[job_id]["result"] = result
            audit_logger.info(f"Event=PROCESS | Job={job_id} | Result=SUCCESS")
        except Exception as exc:
            error_msg = str(exc)[:200]
            with job_lock:
                job_status[job_id]["status"] = "failed"
                job_status[job_id]["message"] = "Processing failed. See server logs."
                # Don't expose full traceback to user
                job_status[job_id]["error"] = None
            audit_logger.error(f"Event=PROCESS | Job={job_id} | Result=FAILED | Error={error_msg}")
            audit_logger.exception(f"Full traceback for job {job_id}")
        finally:
            job_queue.task_done()


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/upload", methods=["POST"])
def upload():
    client_ip = request.remote_addr
    
    if "file" not in request.files:
        log_audit("UPLOAD", client_ip, result="FAILED - No file uploaded")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        log_audit("UPLOAD", client_ip, result="FAILED - Empty filename")
        return jsonify({"error": "No selected file"}), 400

    # Validate file
    is_valid, validation_msg = validate_upload_file(file)
    if not is_valid:
        log_audit("UPLOAD", client_ip, file.filename, result=f"FAILED - {validation_msg}")
        return jsonify({"error": validation_msg}), 400

    filename = secure_filename(file.filename)
    job_id = uuid.uuid4().hex
    job_dir = create_job_dir(job_id)
    upload_path = job_dir / "upload.pdf"
    file.save(upload_path)
    
    # Verify PDF file integrity
    is_pdf_valid, pdf_msg = verify_pdf_file(upload_path)
    if not is_pdf_valid:
        secure_delete(str(upload_path))
        log_audit("UPLOAD", client_ip, filename, result=f"FAILED - {pdf_msg}")
        return jsonify({"error": pdf_msg}), 400
    
    log_audit("UPLOAD", client_ip, filename, result="SUCCESS", output_file=str(job_id))

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
    client_ip = request.remote_addr
    
    with job_lock:
        status_info = job_status.get(job_id)
    if not status_info:
        log_audit("STATUS", client_ip, result="FAILED - Job not found")
        return jsonify({"error": "Job not found"}), 404
    
    log_audit("STATUS", client_ip, result=status_info.get("status", "unknown"))
    return jsonify({
        "status": status_info["status"],
        "message": status_info["message"],
        "files": status_info.get("files", []),
        "error": status_info.get("error", None),
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id: str, filename: str):
    client_ip = request.remote_addr
    
    with job_lock:
        status_info = job_status.get(job_id)
    if not status_info:
        log_audit("DOWNLOAD", client_ip, filename, result="FAILED - Job not found")
        return abort(404)

    job_dir = UPLOAD_BASE / job_id
    file_path = job_dir / filename
    
    # Prevent directory traversal attacks
    try:
        file_path = file_path.resolve()
        job_dir_resolved = job_dir.resolve()
        if not str(file_path).startswith(str(job_dir_resolved)):
            log_audit("DOWNLOAD", client_ip, filename, result="FAILED - Path traversal attempt")
            return abort(403)
    except Exception:
        log_audit("DOWNLOAD", client_ip, filename, result="FAILED - Invalid path")
        return abort(403)
    
    if not file_path.exists() or not file_path.is_file():
        log_audit("DOWNLOAD", client_ip, filename, result="FAILED - File not found")
        return abort(404)

    if not any(file_path.name == entry["url"].split('/')[-1] for entry in status_info.get("files", [])):
        log_audit("DOWNLOAD", client_ip, filename, result="FAILED - Unauthorized access")
        return abort(403)

    log_audit("DOWNLOAD", client_ip, filename, result="SUCCESS", output_file=str(file_path.stat().st_size))
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

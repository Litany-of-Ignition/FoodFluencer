r"""FoodFluencer: one local page that runs the whole pipeline.

Usage (PowerShell, from the project folder):
    python app.py

Opens http://127.0.0.1:5000 in your browser. It runs the same scripts as the
command line, one video per folder in output\jobs, and remembers your character
sheets so the same photo is not paid for twice.
Uses the COMFY_API_KEY environment variable if it is set; otherwise the page asks for the key.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

PROJECT = Path(__file__).resolve().parent
OUTPUT = PROJECT / "output"
JOBS_DIR = OUTPUT / "jobs"
CHAR_DIR = OUTPUT / "characters"
SCRIPTS = PROJECT / "scripts"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
COST_VIDEO = 2.00        # 15 seconds of H3 plus the small text steps
COST_NEW_CHARACTER = 0.35  # character sheet and close-up sheet, worst case

STEPS = [
    ("sheet", "Meeting the reviewer (making your character sheet)"),
    ("detail", "Checking your hands and teeth for the mess ahead"),
    ("food", "Reading the menu"),
    ("script", "Writing the review in the parking lot"),
    ("video", "Setting up the dash camera (about 6 minutes)"),
]

app = Flask(__name__, static_folder=str(PROJECT / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024

JOBS = {}
RUN_LOCK = threading.Lock()  # one video at a time, so spending stays predictable


def new_steps():
    return [{"key": k, "label": label, "state": "waiting"} for k, label in STEPS]


def set_step(job, key, state):
    for step in job["steps"]:
        if step["key"] == key:
            step["state"] = state


def save_upload(file, folder, stem):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_TYPES:
        raise ValueError("Use a PNG, JPG or WebP image.")
    path = folder / f"{stem}{suffix}"
    file.save(path)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("That image is over 10 MB. Use a smaller one.")
    return path


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@app.get("/api/config")
def config():
    return jsonify(has_key=bool(os.environ.get("COMFY_API_KEY")))


@app.post("/api/key")
def set_key():
    """Keep the pasted key in memory for this session only. It is never written to disk."""
    if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
        abort(403)
    if not request.is_json:  # a plain web page elsewhere cannot send this without our permission
        abort(415)
    key = str((request.get_json(silent=True) or {}).get("key", "")).strip()
    if len(key) < 12 or any(ch.isspace() for ch in key):
        return jsonify(error="That does not look like a Comfy API key. Copy the whole key from platform.comfy.org."), 400
    os.environ["COMFY_API_KEY"] = key
    return jsonify(ok=True)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/prepare")
def prepare():
    """Save the uploads, work out the price, and wait for the user to confirm."""
    if not os.environ.get("COMFY_API_KEY"):
        return jsonify(error="Add your Comfy API key first. Reload the page to see the box."), 400
    photo = request.files.get("photo")
    text = (request.form.get("food_text") or "").strip()
    food_photo = request.files.get("food_photo")
    if not photo or not photo.filename:
        return jsonify(error="Add a photo of the reviewer."), 400
    if not text and not (food_photo and food_photo.filename):
        return jsonify(error="Tell me the food: type it, add a photo, or both."), 400
    try:
        score = int(request.form.get("score", ""))
    except ValueError:
        score = 0
    if not 1 <= score <= 10:
        return jsonify(error="Pick a score from 1 to 10."), 400

    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    folder = JOBS_DIR / job_id
    inputs = folder / "in"
    inputs.mkdir(parents=True)
    try:
        photo_path = save_upload(photo, inputs, "photo")
        food_path = save_upload(food_photo, inputs, "food") if food_photo and food_photo.filename else None
    except ValueError as error:
        shutil.rmtree(folder, ignore_errors=True)
        return jsonify(error=str(error)), 400

    character_key = file_hash(photo_path)
    cached = (CHAR_DIR / character_key / "character.json").is_file()
    cost = COST_VIDEO + (0 if cached else COST_NEW_CHARACTER)
    JOBS[job_id] = {
        "id": job_id, "state": "ready", "steps": new_steps(), "log": [], "error": "", "folder": folder,
        "photo": photo_path, "food_text": text, "food_photo": food_path, "score": score,
        "note": (request.form.get("note") or "").strip(), "character_key": character_key,
        "cached": cached, "started": None,
    }
    return jsonify(job=job_id, cost=round(cost, 2), cached=cached)


@app.post("/api/run/<job_id>")
def run(job_id):
    job = JOBS.get(job_id)
    if not job or job["state"] != "ready":
        abort(404)
    if not RUN_LOCK.acquire(blocking=False):
        return jsonify(error="Another video is being made. Wait for it to finish."), 409
    job["state"] = "running"
    job["started"] = time.time()
    threading.Thread(target=worker, args=(job,), daemon=True).start()
    return jsonify(ok=True)


@app.get("/api/job/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    return jsonify(
        state=job["state"], steps=job["steps"], log=job["log"][-80:], error=job["error"],
        elapsed=int(time.time() - job["started"]) if job["started"] else 0,
        video=f"/video/{job_id}" if job["state"] == "done" else None,
    )


@app.get("/video/<job_id>")
def video(job_id):
    # Look on disk, so links keep working after the app restarts.
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{4}", job_id):
        abort(404)
    path = JOBS_DIR / job_id / "work" / "clips" / "shot_01.mp4"
    if not path.is_file():
        abort(404)
    if request.args.get("download"):
        return send_file(path, mimetype="video/mp4", as_attachment=True, download_name="foodfluencer-review.mp4")
    return send_file(path, mimetype="video/mp4", conditional=True)


def run_script(job, env, name, args):
    """Run one of the scripts, streaming its output into the job log."""
    command = [sys.executable, str(SCRIPTS / name), *map(str, args)]
    process = subprocess.Popen(
        command, cwd=str(PROJECT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    for line in process.stdout:
        job["log"].append(line.rstrip())
    return process.wait()


def friendly_error(job, work):
    """A short plain-English reason, taken from the photo check or the end of the log."""
    info_path = work / "character.json"
    if info_path.is_file():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            kind = info.get("image_type")
            if kind == "multiple_people":
                return "That photo shows more than one person. Use a photo of just one person."
            if kind == "no_person":
                return "I could not find a person in that photo."
            if info.get("status") != "ok":
                return info.get("note") or "That photo could not be used."
        except ValueError:
            pass
    for line in reversed(job["log"]):
        if line.startswith(("The call failed", "Needs a clarification", "Missing", "Could not")):
            return line
    return "Something went wrong. Open the details below, and send them to the developer."


def worker(job):
    folder = job["folder"]
    work = folder / "work"
    work.mkdir(exist_ok=True)
    env = {**os.environ, "FOODFLUENCER_OUTPUT": str(work), "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    cache = CHAR_DIR / job["character_key"]
    photo = job["photo"]
    try:
        if job["cached"]:
            for item in cache.iterdir():
                shutil.copy(item, work / item.name)
            job["log"].append("Using the character sheets saved from last time.")
            set_step(job, "sheet", "done")
            set_step(job, "detail", "done")
        else:
            set_step(job, "sheet", "running")
            if run_script(job, env, "make_sheet.py", [photo]) != 0:
                raise RuntimeError(friendly_error(job, work))
            set_step(job, "sheet", "done")
            set_step(job, "detail", "running")
            if run_script(job, env, "make_detail_sheet.py", [photo]) != 0:
                raise RuntimeError(friendly_error(job, work))
            set_step(job, "detail", "done")
            cache.mkdir(parents=True, exist_ok=True)
            for pattern in ("character.json", "sheet_*", "detail_sheet_*"):
                for item in work.glob(pattern):
                    shutil.copy(item, cache / item.name)

        set_step(job, "food", "running")
        args = []
        if job["food_text"]:
            args += ["--text", job["food_text"]]
        if job["food_photo"]:
            args += ["--image", job["food_photo"]]
        if run_script(job, env, "food_intake.py", args) != 0:
            raise RuntimeError(friendly_error(job, work))
        set_step(job, "food", "done")

        set_step(job, "script", "running")
        args = ["--score", job["score"]]
        if job["note"]:
            args += ["--note", job["note"]]
        if run_script(job, env, "shot_list.py", args) != 0:
            raise RuntimeError(friendly_error(job, work))
        set_step(job, "script", "done")

        set_step(job, "video", "running")
        if run_script(job, env, "make_videos.py", ["--upload", photo, "--yes"]) != 0:
            raise RuntimeError(friendly_error(job, work))
        if not (work / "clips" / "shot_01.mp4").is_file():
            raise RuntimeError("The video did not come back. Open the details below.")
        set_step(job, "video", "done")
        job["state"] = "done"
    except Exception as error:
        job["error"] = str(error)
        job["state"] = "error"
    finally:
        RUN_LOCK.release()


if __name__ == "__main__":
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("FOODFLUENCER_PORT") or 5000)
    address = f"http://127.0.0.1:{port}"
    print(f"FoodFluencer is running at {address}  (press Ctrl+C to stop)")
    threading.Timer(1.0, webbrowser.open, args=(address,)).start()
    app.run(host="127.0.0.1", port=port, threaded=True)

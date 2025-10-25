from io import StringIO
import os, sys
import sqlite3
import uuid
import webbrowser
import yaml
import subprocess
import signal
import time
import cv2
from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    render_template,
    Response,
)
import csv
from common_utils.resource_path import get_data_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PORT = 5000

app = Flask(
    __name__, static_folder=os.path.join(BASE_DIR, "static"), template_folder=BASE_DIR
)


def get_db_path():
    return get_data_path("plates.db")


def get_conn():
    return sqlite3.connect(get_db_path(), check_same_thread=False)


@app.route("/")
def index():
    return render_template("static/dashboard.html")


@app.route("/plate_image/<string:uuid>/<string:tag>")
def serve_out_files(uuid, tag):
    """
    Generic api to help the dashboard load images from disk
    """
    base_dir = get_data_path(f"out/{uuid}")
    paths = [f"{tag}.jpg", "failed_capture.jpg"]
    for p in paths:
        full_path = os.path.join(base_dir, p)
        if os.path.exists(full_path):
            return send_from_directory(base_dir, p)

    return "", 404


@app.route("/tiny_plate_image/<string:uuid>/<string:tag>")
def serve_out_tiny_plate(uuid, tag):
    """
    Generic api to help the dashboard load images from disk
    """
    base_dir = get_data_path(f"out/{uuid}")
    return send_from_directory(base_dir, f"{tag}.jpg")


@app.route("/traffic", methods=["GET"])
def list_plates():
    # pagination
    try:
        per_page = max(1, min(int(request.args.get("per_page", 5)), 200))
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        per_page, page = 5, 1
    offset = (page - 1) * per_page

    plate_text = request.args.get("plate_text", "").strip()
    start_ts = request.args.get("start_ts")
    end_ts = request.args.get("end_ts")

    query = """
    SELECT p.uuid, p.plate_text, t.timestamp,
        m.car_type, m.car_color, m.car_owner
    FROM traffic t
    JOIN plates p ON t.plate_uuid = p.uuid
    LEFT JOIN metadata m ON p.uuid = m.plate_uuid
    WHERE 1=1
    """
    params = []
    if plate_text:
        query += " AND p.plate_text LIKE ?"
        params.append(f"%{plate_text}%")
    if start_ts:
        query += " AND t.timestamp >= ?"
        params.append(start_ts)
    if end_ts:
        query += " AND t.timestamp <= ?"
        params.append(end_ts)

    query += " ORDER BY t.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        # total count for pagination
        count_q = """
            SELECT COUNT(*)
            FROM traffic t
            JOIN plates p ON t.plate_uuid = p.uuid
            WHERE 1=1
        """
        count_params = []
        if plate_text:
            count_q += " AND p.plate_text LIKE ?"
            count_params.append(f"%{plate_text}%")
        if start_ts:
            count_q += " AND t.timestamp >= ?"
            count_params.append(start_ts)
        if end_ts:
            count_q += " AND t.timestamp <= ?"
            count_params.append(end_ts)
        cur.execute(count_q, count_params)
        total = cur.fetchone()[0]

    return jsonify(
        {
            "items": [
                {
                    "uuid": r[0],
                    "plate_text": r[1],
                    "timestamp": r[2],
                    "car_type": r[3],
                    "car_color": r[4],
                    "car_owner": r[5],
                }
                for r in rows
            ],
            "meta": {"page": page, "per_page": per_page, "total": total},
        }
    )


@app.route("/traffic", methods=["POST"])
def create_plate():
    data = request.json
    plate_uuid = str(uuid.uuid4())
    plate_text = data.get("plate_text")

    # TODO validate input

    if not plate_text:
        return jsonify({"status": "error", "message": "Plate text is required"}), 400

    with get_conn() as conn:
        # check if plate already exists
        row = conn.execute(
            "SELECT uuid FROM plates WHERE plate_text = ?", (plate_text,)
        ).fetchone()

        if row:
            plate_uuid = row[0]
        else:
            plate_uuid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO plates (uuid, plate_text) VALUES (?, ?)",
                (plate_uuid, plate_text),
            )

        # upsert metadata
        conn.execute(
            """
                INSERT INTO metadata (plate_uuid, car_type, car_color, car_owner)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plate_uuid) DO UPDATE SET
                    car_type=excluded.car_type,
                    car_color=excluded.car_color,
                    car_owner=excluded.car_owner
            """,
            (
                plate_uuid,
                data.get("car_type"),
                data.get("car_color"),
                data.get("car_owner"),
            ),
        )

        # insert traffic record
        camera_location = data.get("camera_location")
        if camera_location:
            conn.execute(
                "INSERT INTO traffic (plate_uuid, location) VALUES (?, ?)",
                (plate_uuid, camera_location),
            )
        conn.commit()
    return jsonify({"status": "created", "uuid": plate_uuid})


@app.route("/update/<string:plate_uuid>", methods=["PUT"])
def update_plate(plate_uuid):
    try:
        data = request.json
        with get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO metadata (plate_uuid, car_type, car_color, car_owner)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(plate_uuid) DO UPDATE SET
                        car_type=excluded.car_type,
                        car_color=excluded.car_color,
                        car_owner=excluded.car_owner
                """,
                (
                    plate_uuid,
                    data.get("car_type"),
                    data.get("car_color"),
                    data.get("car_owner"),
                ),
            )
            # TODO in post MVP when the system supports multiple camera sources,
            # we should filter by traffic id to update camera location.
            camera_location = data.get("camera_location")
            if camera_location:
                conn.execute(
                    """
                        UPDATE traffic
                        SET camera_location = ?
                        WHERE plate_uuid = ?
                    """,
                    (plate_uuid, camera_location),
                )
            conn.commit()
    except Exception as e:
        return jsonify({"status": f"Error: {str(e)}"})
    return jsonify({"status": "updated"})


@app.route("/traffic/<string:plate_uuid>", methods=["DELETE"])
def delete_plate(plate_uuid):
    with get_conn() as conn:
        conn.execute("DELETE FROM traffic WHERE plate_uuid = ?", (str(plate_uuid),))
        conn.commit()
    return jsonify({"status": "deleted"})


# export CSV
@app.route("/plates/export", methods=["GET"])
def export_plates_csv():
    plate_text = request.args.get("plate_text", "").strip()
    start_ts = request.args.get("start_ts")
    end_ts = request.args.get("end_ts")

    query = "SELECT id, vehicle_id, plate_text, timestamp FROM plates WHERE 1=1"
    params = []
    if plate_text:
        query += " AND plate_text LIKE ?"
        params.append(f"%{plate_text}%")
    if start_ts:
        query += " AND timestamp >= ?"
        params.append(start_ts)
    if end_ts:
        query += " AND timestamp <= ?"
        params.append(end_ts)
    query += " ORDER BY timestamp DESC"

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["id", "vehicle_id", "plate_text", "timestamp"])
    for r in rows:
        writer.writerow(r)

    output = si.getvalue()
    headers = {
        "Content-Disposition": "attachment; filename=plates_export.csv",
        "Content-Type": "text/csv; charset=utf-8",
    }
    return Response(output, headers=headers)


backend_process = None


def get_config_path():
    return get_data_path("config.yaml")


def start_backend():
    global backend_process
    if backend_process is None or backend_process.poll() is not None:
        # TODO: in production use absolute paths
        backend_process = subprocess.Popen(
            [sys.executable, "main.py"], preexec_fn=os.setsid
        )


def stop_backend():
    global backend_process
    if backend_process and backend_process.poll() is None:
        os.killpg(os.getpgid(backend_process.pid), signal.SIGTERM)
        try:
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(backend_process.pid), signal.SIGKILL)
    backend_process = None


def restart_backend():
    stop_backend()
    # Give it a moment to release resources if needed
    time.sleep(5)
    start_backend()


@app.route("/settings", methods=["GET", "POST"])
def settings():
    config_path = get_config_path()
    if request.method == "POST":
        new_config = request.json or {}
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            config = {}

        config.update(new_config)

        with open(config_path, "w") as f:
            yaml.safe_dump(config, f)

        restart_backend()
        return jsonify({"status": "در حال اجرا با تنظیمات جدید"})

    # GET
    try:
        with open(config_path, "r") as f:
            return jsonify(yaml.safe_load(f) or {})
    except FileNotFoundError:
        return jsonify({"error": "تنظیمات یافت نشد -- شاهین را مجدد تمیز اجرا نمایید"})


def gen_frames(video_url):
    cap = cv2.VideoCapture(video_url)
    if not cap.isOpened():
        print(f"ویدئو یافت نشد {video_url}")
        return

    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode(".jpg", frame)
            frame = buffer.tobytes()
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    cap.release()


@app.route("/video_feed")
def video_feed():
    video_url = request.args.get("url")
    if not video_url:
        return "Error: no video URL provided", 400
    return Response(
        gen_frames(video_url), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/status")
def backend_status():
    if backend_process and backend_process.poll() is None:
        return jsonify({"status": "درحال اجرا"})
    return jsonify({"status": "غیرفعال"})


def run_app():
    app.run(port=PORT, debug=True)


if __name__ == "__main__":
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if not os.path.exists(db_path):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS plates (
                        uuid TEXT PRIMARY KEY,
                        plate_text TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """
            )
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plate_uuid TEXT NOT NULL UNIQUE,
                        car_type TEXT,
                        car_color TEXT,
                        car_owner TEXT,
                        FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
                    );
                """
            )
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS traffic (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plate_uuid TEXT NOT NULL,
                        location TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
                    );
                """
            )
            conn.commit()

    # Thread(target=run_app).start()
    try:
        start_backend()
        import atexit

        atexit.register(stop_backend)
    except Exception as e:
        print(f"Error starting backend: {e}")
    run_app()

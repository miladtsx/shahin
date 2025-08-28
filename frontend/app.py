from io import StringIO
import os
import sqlite3
import webbrowser
from flask import Flask, request, jsonify, send_from_directory, render_template, Response
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../res/db/plates.db")
PORT = 5000

app = Flask(
    __name__, static_folder=os.path.join(BASE_DIR, "static"), template_folder=BASE_DIR
)


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/out/<path:filename>")
def serve_out_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, "../out/"), filename)


@app.route("/plates", methods=["GET"])
def list_plates():
    # pagination
    try:
        per_page = int(request.args.get("per_page", 5))
    except ValueError:
        per_page = 5
    per_page = max(1, min(per_page, 200))  # clamp 1..200
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(1, page)
    offset = (page - 1) * per_page

    plate_text = request.args.get("plate_text", "").strip()
    start_ts = request.args.get("start_ts")
    end_ts = request.args.get("end_ts")

    query = (
        "SELECT id, vehicle_id, image_path, plate_text, timestamp FROM plates WHERE 1=1"
    )
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

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        # total count for pagination
        count_q = "SELECT COUNT(*) FROM plates WHERE 1=1"
        count_params = []
        if plate_text:
            count_q += " AND plate_text LIKE ?"
            count_params.append(f"%{plate_text}%")
        if start_ts:
            count_q += " AND timestamp >= ?"
            count_params.append(start_ts)
        if end_ts:
            count_q += " AND timestamp <= ?"
            count_params.append(end_ts)
        cur.execute(count_q, count_params)
        total = cur.fetchone()[0]

    return jsonify(
        {
            "items": [
                {
                    "id": r[0],
                    "vehicle_id": r[1],
                    "image_path": r[2] or "./static/plate_raw.jpg",
                    "plate_text": r[3],
                    "timestamp": r[4],
                }
                for r in rows
            ],
            "meta": {"page": page, "per_page": per_page, "total": total},
        }
    )


@app.route("/plates", methods=["POST"])
def create_plate():
    data = request.json
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO plates (vehicle_id, image_path, plate_text) VALUES (?, ?, ?)",
            (data["vehicle_id"], data["image_path"], data["plate_text"]),
        )
        conn.commit()
    return jsonify({"status": "created"})


@app.route("/plates/<int:pid>", methods=["PUT"])
def update_plate(pid):
    data = request.json
    with get_conn() as conn:
        conn.execute(
            "UPDATE plates SET plate_text = ? WHERE id = ?",
            (data["plate_text"], pid),
        )
        conn.commit()
    return jsonify({"status": "updated"})


@app.route("/plates/<int:pid>", methods=["DELETE"])
def delete_plate(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM plates WHERE id = ?", (pid,))
        conn.commit()
    return jsonify({"status": "deleted"})

# export CSV
@app.route("/plates/export", methods=["GET"])
def export_plates_csv():
    plate_text = request.args.get("plate_text", "").strip()
    start_ts = request.args.get("start_ts")
    end_ts = request.args.get("end_ts")

    query = "SELECT id, vehicle_id, image_path, plate_text, timestamp FROM plates WHERE 1=1"
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
    writer.writerow(["id", "vehicle_id", "image_path", "plate_text", "timestamp"])
    for r in rows:
        writer.writerow(r)

    output = si.getvalue()
    headers = {
        "Content-Disposition": "attachment; filename=plates_export.csv",
        "Content-Type": "text/csv; charset=utf-8",
    }
    return Response(output, headers=headers)


def run_app():
    app.run(port=PORT, debug=True, use_reloader=True)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id TEXT,
                    image_path TEXT,
                    plate_text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    # Thread(target=run_app).start()
    run_app()
    webbrowser.open(f"http://127.0.0.1:{PORT}")

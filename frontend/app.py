import os
import sqlite3
import webbrowser
from flask import Flask, request, jsonify, send_from_directory, render_template
from threading import Thread

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


@app.route('/out/<path:filename>')
def serve_out_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, '../out/'), filename)


@app.route("/plates", methods=["GET"])
def list_plates():
    limit = int(request.args.get("limit", 50))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, vehicle_id, image_path, plate_text, timestamp "
            "FROM plates ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    return jsonify(
        [
            {
                "id": r[0],
                "vehicle_id": r[1],
                "image_path": r[2],
                "plate_text": r[3],
                "timestamp": r[4],
            }
            for r in rows
        ]
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
            "UPDATE plates SET plate_text = ?, image_path = ? WHERE id = ?",
            (data["plate_text"], data["image_path"], pid),
        )
        conn.commit()
    return jsonify({"status": "updated"})


@app.route("/plates/<int:pid>", methods=["DELETE"])
def delete_plate(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM plates WHERE id = ?", (pid,))
        conn.commit()
    return jsonify({"status": "deleted"})


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

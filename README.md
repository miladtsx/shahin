
# Vehicle Plate Tracker - Extract Plate Image

Select the sharpest, best-quality frame of each unique license plate from a 120 FPS video stream.

## Features

- High frame-rate input (120 FPS).
- One output per unique plate (best frame).
- Accuracy > speed.
- Asynchronous-friendly pipeline.

## Requirements

- Python 3.10+
- CPU-only inference
- Low hardware footprint (no GPU needed)

## Setup

### Windows
```sh
 py -m venv .venv
 .\.venv\Scripts\Activate.ps1  
c:\users\user\desktop\shahin-dev\.venv\scripts\python.exe -m pip install --upgrade pip
pip install -r .\requirements.txt
```


### Linux
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Demo Setup

### Fake plates
```sh
$ make seed-db
$ make web
```

- Download [MediaMTX](https://github.com/bluenviron/mediamtx/releases)

```sh
$ ./mediamtx
```

In another terminal, stream the sample video (acting as the input camera):
```sh
$ ffmpeg -re -stream_loop -1 -i output_1080p_120fps.mp4 -c copy -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/live.stream
```
Then run:
```sh
$ ./main.py
```
# Logging
## Quickstart: Loki + Promtail + Grafana (Docker Compose)

Start a local stack that collects `logs/app.jsonl` and provides a Grafana UI:

```bash
docker-compose up -d
```

After the stack starts:
- Grafana: http://localhost:3000 (user: admin / password: admin)

Promtail is configured to read `./logs/*.jsonl` and push to Loki. Use the provided `docker/promtail-config.yaml` if you need to tweak parsing or labels.

## DB Schema

```sql
-- from traffic → plate → metadata

CREATE TABLE IF NOT EXISTS plates (
    uuid TEXT PRIMARY KEY,
    plate_text TEXT NOT NULL UNIQUE,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_uuid TEXT NOT NULL UNIQUE,
    car_type TEXT,
    car_color TEXT,
    driver_name TEXT,
    FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
);

CREATE TABLE IF NOT EXISTS traffic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_uuid TEXT NOT NULL,
    location TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
);

```


## Document
[link](https://docs.google.com/document/d/1_Q-legmeUw9Q5sP0G9K7ayoIYyhgSnebhKUnHNxscoQ/edit?tab=t.0#heading=h.z6ne0og04bp5)
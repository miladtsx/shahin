
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

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Demo Setup

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
## Document
[link](https://docs.google.com/document/d/1_Q-legmeUw9Q5sP0G9K7ayoIYyhgSnebhKUnHNxscoQ/edit?tab=t.0#heading=h.z6ne0og04bp5)
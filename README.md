
# Vehicle Plate Tracker - Extract Plate Image

A preprocessing pipeline to extract the best frame(s) per vehicle from high frame-rate gate entry videos. These frames can be used for accurate license plate recognition via a remote OCR service.

## Features

- YOLO-based vehicle detection
- Frame skipping to reduce compute
- Visual annotation of detected vehicles
- Output saved frames for downstream OCR

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


## Document
[link](https://docs.google.com/document/d/1_Q-legmeUw9Q5sP0G9K7ayoIYyhgSnebhKUnHNxscoQ/edit?tab=t.0#heading=h.z6ne0og04bp5)
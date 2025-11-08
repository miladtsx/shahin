#!/usr/bin/env python3
"""
Generate a signed Shahin license blob for an individual fingerprint.

Can be used via CLI flags or an interactive GUI that copies/saves the
resulting <payload_b64>.<signature_b64> string for activation.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_PATH = REPO_ROOT / ".keys" / "licensing_private.pem"


def _canonical_json(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def _load_private_key(path: Path):
    try:
        blob = path.read_bytes()
        return serialization.load_pem_private_key(blob, password=None)
    except FileNotFoundError as exc:  # pragma: no cover - tool script
        raise SystemExit(f"Private key not found at {path}") from exc
    except Exception as exc:  # pragma: no cover - tool script
        raise SystemExit(f"Failed to load private key {path}: {exc}")


def _build_payload(
    fingerprint: str,
    customer: str,
    features: List[str],
    expiry: str | None,
    license_id: str | None,
) -> dict:
    payload = {
        "fingerprint": fingerprint,
        "customer": customer,
        "features": features,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "license_id": license_id or str(uuid.uuid4()),
    }
    if expiry:
        payload["exp"] = expiry
    return payload


def generate_license_blob(
    fingerprint: str,
    customer: str,
    features_raw: str,
    expiry: str | None,
    license_id: str | None,
    key_path: Path,
) -> str:
    features = [f.strip() for f in (features_raw or "").split(",") if f.strip()]
    if not features:
        raise ValueError("At least one feature must be provided.")
    private_key = _load_private_key(key_path)
    payload = _build_payload(fingerprint, customer, features, expiry, license_id)
    payload_json = _canonical_json(payload)
    signature = private_key.sign(
        payload_json.encode("utf-8"), ec.ECDSA(hashes.SHA256())
    )
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
    signature_b64 = base64.b64encode(signature).decode("ascii")
    return f"{payload_b64}.{signature_b64}"


GUI_EXPIRY_CHOICES = [
    ("No expiry", None),
    ("1 week", timedelta(weeks=1)),
    ("1 month", timedelta(days=30)),
    ("3 months", timedelta(days=90)),
    ("6 months", timedelta(days=182)),
    ("12 months", timedelta(days=365)),
    ("2 years", timedelta(days=730)),
    ("5 years", timedelta(days=1825)),
]


def _run_cli(args):
    missing = [
        name for name in ("fingerprint", "customer") if getattr(args, name) is None
    ]
    if missing:
        raise SystemExit(f"Missing required CLI arguments: {', '.join(missing)}")
    try:
        blob = generate_license_blob(
            fingerprint=args.fingerprint,
            customer=args.customer,
            features_raw=args.features,
            expiry=args.expiry,
            license_id=args.license_id,
            key_path=args.key,
        )
    except Exception as exc:  # pragma: no cover - tool script
        raise SystemExit(str(exc))

    if args.output:
        args.output.write_text(blob, encoding="utf-8")
        print(f"License written to {args.output}")
    else:
        print(blob)


def _run_gui(args):
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("Shahin License Generator")
    root.resizable(False, False)

    def _labeled_entry(row, label, default=""):
        tk.Label(root, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
        entry = tk.Entry(root, width=50)
        entry.insert(0, default)
        entry.grid(row=row, column=1, padx=10, pady=5)
        return entry

    fingerprint_entry = _labeled_entry(0, "Fingerprint:")
    customer_entry = _labeled_entry(1, "Customer:")
    features_entry = _labeled_entry(2, "Features:", "backend,dashboard")

    tk.Label(root, text="Expiry:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
    expiry_var = tk.StringVar(value=GUI_EXPIRY_CHOICES[4][0])
    expiry_menu = tk.OptionMenu(
        root, expiry_var, *[label for label, _ in GUI_EXPIRY_CHOICES]
    )
    expiry_menu.grid(row=3, column=1, padx=10, pady=5, sticky="w")

    license_id_entry = _labeled_entry(4, "License ID (optional):")
    key_entry = _labeled_entry(5, "Key path:", str(args.key))

    def browse_key():
        path = filedialog.askopenfilename(
            title="Select licensing private key",
            initialdir=str(args.key.parent if args.key else "."),
            filetypes=[("PEM files", "*.pem"), ("All files", "*.*")],
        )
        if path:
            key_entry.delete(0, tk.END)
            key_entry.insert(0, path)

    tk.Button(root, text="Browse…", command=browse_key).grid(
        row=5, column=2, padx=5, pady=5
    )

    output_label = tk.Label(root, text="Generated license:")
    output_label.grid(row=6, column=0, padx=10, pady=(10, 0), sticky="nw")

    output_text = tk.Text(root, width=60, height=5, wrap="word")
    output_text.grid(row=6, column=1, columnspan=2, padx=10, pady=(10, 5))

    def copy_blob():
        blob = output_text.get("1.0", "end").strip()
        if not blob:
            messagebox.showwarning("Nothing to copy", "Generate a license first.")
            return
        root.clipboard_clear()
        root.clipboard_append(blob)
        messagebox.showinfo("Copied", "License blob copied to clipboard.")

    def save_blob():
        blob = output_text.get("1.0", "end").strip()
        if not blob:
            messagebox.showwarning("Nothing to save", "Generate a license first.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save license blob",
        )
        if file_path:
            Path(file_path).write_text(blob, encoding="utf-8")
            messagebox.showinfo("Saved", f"License written to {file_path}")

    def generate():
        selected_label = expiry_var.get()
        expiry_delta = next(
            (delta for label, delta in GUI_EXPIRY_CHOICES if label == selected_label),
            None,
        )
        expiry_value = None
        if expiry_delta:
            expiry_value = (datetime.now(timezone.utc) + expiry_delta).isoformat()
        try:
            blob = generate_license_blob(
                fingerprint=fingerprint_entry.get().strip(),
                customer=customer_entry.get().strip(),
                features_raw=features_entry.get().strip(),
                expiry=expiry_value,
                license_id=license_id_entry.get().strip() or None,
                key_path=Path(key_entry.get().strip()),
            )
        except Exception as exc:
            messagebox.showerror("Generation failed", str(exc))
            return
        output_text.delete("1.0", "end")
        output_text.insert("1.0", blob)
        root.clipboard_clear()
        root.clipboard_append(blob)
        messagebox.showinfo("Success", "License generated and copied to clipboard.")

    button_frame = tk.Frame(root)
    button_frame.grid(row=7, column=1, columnspan=2, pady=10)
    tk.Button(button_frame, text="Generate", command=generate).grid(
        row=0, column=0, padx=5
    )
    tk.Button(button_frame, text="Copy", command=copy_blob).grid(
        row=0, column=1, padx=5
    )
    tk.Button(button_frame, text="Save…", command=save_blob).grid(
        row=0, column=2, padx=5
    )
    tk.Button(button_frame, text="Close", command=root.destroy).grid(
        row=0, column=3, padx=5
    )

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description="Generate a signed Shahin license blob."
    )
    parser.add_argument(
        "--fingerprint", help="Machine fingerprint (from tray activation dialog)."
    )
    parser.add_argument("--customer", help="Customer or deployment name.")
    parser.add_argument(
        "--features",
        default="backend,dashboard",
        help="Comma-separated feature flags to embed (default: backend,dashboard).",
    )
    parser.add_argument(
        "--expiry",
        help="ISO8601 expiry timestamp, e.g. 2025-12-31T23:59:59Z. Leave empty for no expiry.",
    )
    parser.add_argument("--license-id", help="Override license UUID.")
    parser.add_argument(
        "--key",
        type=Path,
        default=DEFAULT_KEY_PATH,
        help=f"Path to licensing private key (default: {DEFAULT_KEY_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file to write the license blob to (CLI mode only).",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force CLI mode even if GUI inputs are missing.",
    )
    parser.add_argument("--gui", action="store_true", help="Force GUI mode.")
    args = parser.parse_args()

    use_gui = args.gui or (not args.cli and not (args.fingerprint and args.customer))
    if use_gui:
        _run_gui(args)
    else:
        _run_cli(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Recompute manifest.json (SHA256 of every package file) after the annotation run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

files = {}
for path in sorted(PKG.rglob("*")):
    if path.is_dir() or path.name == "manifest.json":
        continue
    rel = path.relative_to(PKG).as_posix()
    files[rel] = {
        "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }

manifest = {
    "package": "AgentDB annotation package",
    "generated_at": "2026-11-17",
    "annotation_status": "DONE (3 annotators, calibrated, arbitrated)",
    "n_queries": 30,
    "files": files,
}
(PKG / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"manifest.json: {len(files)} files")

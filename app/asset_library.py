"""Minimal, local-only B-roll registry. Uploads require explicit license evidence."""
from __future__ import annotations
import json
import os
import shutil
import uuid
from pathlib import Path
from .core import get_duration
from .store import ROOT


def register_asset(file_obj, filename: str, description: str, license_note: str) -> dict:
    if not description.strip() or not license_note.strip():
        raise ValueError("Descrição e referência de licença são obrigatórias")
    ext = Path(filename).suffix.lower()
    if ext not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ValueError("Formato de vídeo não suportado")
    directory = ROOT / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    ident = "asset_" + uuid.uuid4().hex[:12]
    path = directory / (ident + ext)
    try:
        with path.open("wb") as destination:
            shutil.copyfileobj(file_obj, destination)
        if path.stat().st_size > 300_000_000:
            raise ValueError("Asset excede 300 MB")
        duration = round(get_duration(path), 2)
        if not 2 <= duration <= 7200:
            raise ValueError("Asset deve ter entre 2 segundos e 2 horas")
        catalog = directory / "catalog.json"
        current = json.loads(catalog.read_text(encoding="utf-8")) if catalog.exists() else {"assets": []}
        record = {"asset_id": ident, "file": path.name, "description": description.strip()[:150],
                  "license_note": license_note.strip()[:500], "duration": duration}
        current["assets"].append(record)
        tmp = directory / ("catalog_" + ident + ".tmp")
        try:
            tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, catalog)
        finally:
            tmp.unlink(missing_ok=True)
        return record
    except Exception:
        path.unlink(missing_ok=True)
        raise

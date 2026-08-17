"""Download route — serves the packaged source zip from a stable /api URL.

Regenerates the zip on-demand if missing (excluding node_modules, .git, caches).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/download", tags=["download"])

APP_ROOT = Path("/app")
ZIP_PATH = APP_ROOT / "frontend" / "public" / "medflow-source.zip"


def _rebuild_zip() -> None:
    """Rebuild the source zip, excluding heavy/irrelevant paths."""
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    cmd = [
        "zip", "-rq", str(ZIP_PATH), ".",
        "-x", "*/node_modules/*", "node_modules/*",
        "-x", "*/.git/*", ".git/*",
        "-x", "*/__pycache__/*", "*/.ruff_cache/*",
        "-x", "*/build/*", "*/dist/*", "*.pyc",
        "-x", "frontend/public/medflow-source.zip",
    ]
    subprocess.run(cmd, cwd=str(APP_ROOT), check=True, timeout=180)


@router.get("/source")
async def download_source():
    """Download the packaged source code as a zip."""
    if not ZIP_PATH.exists() or ZIP_PATH.stat().st_size < 1024:
        try:
            _rebuild_zip()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao gerar zip: {exc}")
    if not ZIP_PATH.exists():
        raise HTTPException(status_code=404, detail="Arquivo indisponível")
    return FileResponse(
        path=str(ZIP_PATH),
        media_type="application/zip",
        filename="medflow-source.zip",
    )


@router.post("/source/rebuild")
async def rebuild_source():
    """Force a rebuild of the zip. Returns new size in bytes."""
    try:
        _rebuild_zip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar zip: {exc}")
    return {"ok": True, "size_bytes": ZIP_PATH.stat().st_size}

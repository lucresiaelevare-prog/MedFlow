"""Tests for the /api/download/source endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://medflow-pre-beta.preview.emergentagent.com").rstrip("/")


class TestDownloadSource:
    def test_get_source_returns_zip(self):
        r = requests.get(f"{BASE_URL}/api/download/source", timeout=180, stream=True)
        assert r.status_code == 200, f"Status {r.status_code}, body: {r.text[:300]}"
        ctype = r.headers.get("content-type", "")
        assert "application/zip" in ctype, f"Unexpected content-type: {ctype}"
        # Read fully to measure size (content-length may be absent)
        total = 0
        for chunk in r.iter_content(chunk_size=65536):
            total += len(chunk)
        assert total > 1_000_000, f"Zip too small: {total} bytes"

    def test_rebuild_endpoint(self):
        r = requests.post(f"{BASE_URL}/api/download/source/rebuild", timeout=240)
        assert r.status_code == 200, f"Status {r.status_code}, body: {r.text[:300]}"
        data = r.json()
        assert data.get("ok") is True
        assert isinstance(data.get("size_bytes"), int)
        assert data["size_bytes"] > 1_000_000, f"Rebuilt zip too small: {data['size_bytes']}"

    def test_get_after_rebuild_still_valid(self):
        # Force a rebuild then GET
        rb = requests.post(f"{BASE_URL}/api/download/source/rebuild", timeout=240)
        assert rb.status_code == 200
        r = requests.get(f"{BASE_URL}/api/download/source", timeout=180, stream=True)
        assert r.status_code == 200
        assert "application/zip" in r.headers.get("content-type", "")
        # First bytes should be PK zip signature
        first = next(r.iter_content(chunk_size=4))
        assert first[:2] == b"PK", f"Not a zip file, first bytes: {first!r}"

    def test_public_no_auth_required(self):
        # No Authorization header — should still work
        s = requests.Session()
        s.headers.clear()
        r = s.get(f"{BASE_URL}/api/download/source", timeout=180, stream=True, allow_redirects=True)
        assert r.status_code == 200, f"Expected 200 without auth, got {r.status_code}"

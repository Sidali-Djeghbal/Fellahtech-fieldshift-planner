"""Deterministic Google Drive export folder and file verification utilities for Field Shift."""

import hashlib
import io
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def _get_drive_service(ee):
    """Build Drive v3 client reusing GEE OAuth credentials without GCP quota-project header."""
    last_exc = None
    for attempt in range(4):
        try:
            state = getattr(ee.data, "_get_state", None)
            base_creds = getattr(state(), "credentials", None) if callable(state) else None
            if base_creds is None:
                base_creds = ee.data.get_persistent_credentials()
            creds = base_creds.with_quota_project(None)
            return build("drive", "v3", credentials=creds)
        except Exception as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise last_exc


def ensure_single_drive_folder(ee, folder_name: str) -> str:
    """Resolve an existing Drive folder in My Drive root or create exactly one before parallel tasks start."""
    drive = _get_drive_service(ee)
    resp = (
        drive.files()
        .list(
            q=(
                f"name = '{folder_name}' and "
                "mimeType = 'application/vnd.google-apps.folder' and "
                "'root' in parents and trashed = false"
            ),
            fields="files(id, name, createdTime)",
            orderBy="createdTime asc",
            pageSize=10,
        )
        .execute()
    )
    existing = resp.get("files", [])
    if existing:
        return existing[0]["id"]

    created = (
        drive.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            },
            fields="id, name",
        )
        .execute()
    )
    return created["id"]


def extract_folder_id_from_destination_uris(destination_uris: Optional[List[str]]) -> Optional[str]:
    """Extract canonical Google Drive folder ID from GEE task destination_uris metadata."""
    if not destination_uris:
        return None
    for uri in destination_uris:
        m = re.search(r"#folders/([A-Za-z0-9_-]+)", uri)
        if m:
            return m.group(1)
    return None


def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_verify_task_outputs(
    ee,
    completed_tasks: List[Dict],
    output_dir: Path,
    fallback_folder_id: Optional[str] = None,
) -> Dict[str, Dict]:
    """Deterministically resolve, download, and verify size + MD5 checksum for each completed GEE Drive task."""
    output_dir.mkdir(parents=True, exist_ok=True)
    drive = _get_drive_service(ee)
    verified: Dict[str, Dict] = {}

    for t in completed_tasks:
        prefix = t.get("file_prefix") or t["name"]
        expected_ext = ".csv" if t["kind"] == "table" else ".tif"
        folder_id = extract_folder_id_from_destination_uris(t.get("destination_uris")) or fallback_folder_id
        if not folder_id:
            raise RuntimeError(f"Could not determine Drive folder ID for task {t['name']}")

        files = None
        last_exc = None
        for attempt in range(5):
            try:
                files = (
                    drive.files()
                    .list(
                        q=f"'{folder_id}' in parents and name contains '{prefix}' and trashed = false",
                        fields="files(id, name, size, md5Checksum, createdTime)",
                        orderBy="createdTime desc",
                        pageSize=20,
                    )
                    .execute(num_retries=3)
                    .get("files", [])
                )
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
                drive = _get_drive_service(ee)
        if files is None:
            raise last_exc
        # Prefer exact match `<prefix>.csv` or `<prefix>.tif`, else matching prefix with expected ext
        matched = [
            f
            for f in files
            if f["name"] == f"{prefix}{expected_ext}" or (f["name"].startswith(prefix) and f["name"].endswith(expected_ext))
        ]
        if not matched:
            raise FileNotFoundError(
                f"Expected file matching '{prefix}*{expected_ext}' not found in Drive folder {folder_id}"
            )

        fmeta = matched[0]
        local_path = output_dir / fmeta["name"]
        remote_size = int(fmeta.get("size") or 0)
        remote_md5 = fmeta.get("md5Checksum")

        need_download = True
        if local_path.exists() and remote_size > 0 and local_path.stat().st_size == remote_size:
            if not remote_md5 or _md5_file(local_path) == remote_md5:
                need_download = False

        if need_download:
            for attempt in range(5):
                try:
                    request = drive.files().get_media(fileId=fmeta["id"])
                    with io.FileIO(local_path, "wb") as fh:
                        downloader = MediaIoBaseDownload(fh, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk(num_retries=3)
                    break
                except Exception as exc:
                    if attempt == 4:
                        raise exc
                    time.sleep(2 * (attempt + 1))
                    drive = _get_drive_service(ee)

        local_size = local_path.stat().st_size
        local_md5 = _md5_file(local_path)
        size_ok = (remote_size == 0) or (local_size == remote_size)
        md5_ok = (not remote_md5) or (local_md5 == remote_md5)
        if not (size_ok and md5_ok):
            raise RuntimeError(
                f"Checksum/size mismatch for {local_path.name}: "
                f"local=({local_size}, {local_md5}) vs drive=({remote_size}, {remote_md5})"
            )

        verified[fmeta["name"]] = {
            "task_name": t["name"],
            "drive_folder_id": folder_id,
            "drive_file_id": fmeta["id"],
            "path": str(local_path),
            "size_bytes": local_size,
            "size_mb": round(local_size / (1024 * 1024), 4),
            "md5_checksum": local_md5,
            "checksum_verified": bool(remote_md5 and md5_ok),
        }

    return verified

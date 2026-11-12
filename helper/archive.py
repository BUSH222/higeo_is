"""Getting a file from a link or the disk, and packing the uploaded files (static/uploads) into one archive."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from helper.db.settings import TransferError

UPLOAD_DIR = "static/uploads"  # relative to the project, and stored in the database in this form
CHUNK = 1024 * 1024
RELEASE_ASSET_LIMIT = 2 * 1024**3


def fetch(source: str, directory: Path) -> Path:
    """Return the file at a path on the disk, or download the https link into `directory` and return that."""
    source = source.strip().strip("'\"")
    if not source.lower().startswith(("http://", "https://")):
        path = Path(source).expanduser()
        if not path.is_file():
            raise TransferError(f"There is no file {path}.")
        return path
    if not source.lower().startswith("https://"):
        raise TransferError("Only https links are accepted: the file is going to be loaded into your database.")

    name = Path(unquote(urlparse(source).path)).name or "download"
    target = directory / name
    request = urllib.request.Request(source, headers={"User-Agent": "higeo-manager"})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while chunk := response.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                _progress(name, done, total)
    except OSError as error:  # URLError and HTTPError are OSErrors
        raise TransferError(f"Could not download {source}: {error}") from error
    print(f"\nDownloaded {name}, sha256 {digest.hexdigest()} (compare it with the one in the release notes).")
    return target


def _progress(name: str, done: int, total: int) -> None:
    if sys.stderr.isatty():
        of = f" of {total / 1024**2:.0f}" if total else ""
        print(f"\r{name}: {done / 1024**2:.0f}{of} MiB", end="", file=sys.stderr, flush=True)


def pack_uploads(upload_dir: Path, output: Path) -> Path:
    """Put the files of the upload folder into a .tar.gz, without any folder in front of their names."""
    if not upload_dir.is_dir():
        raise TransferError(f"There is no upload folder {upload_dir}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(output, "w:gz") as archive:
        for entry in sorted(upload_dir.iterdir()):
            if entry.is_file():
                archive.add(entry, arcname=entry.name)
                count += 1
    size = output.stat().st_size
    print(f"Packed {count} file(s) into {output} ({size / 1024**2:.1f} MiB)")
    if size >= RELEASE_ASSET_LIMIT:
        print("Warning: this is 2 GiB or more, which is too big for a GitHub release asset.")
    return output


def unpack_uploads(archive_path: Path, upload_dir: Path, *, overwrite: bool = False) -> None:
    """Extract an archive made by `pack_uploads` into the upload folder. Files that are already there are kept
    unless `overwrite` is given. Only plain files are extracted, and only directly into the folder."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if name.parts[:2] == tuple(UPLOAD_DIR.split("/")):  # also accept an archive of the whole folder
                    name = PurePosixPath(*name.parts[2:])
                if member.isdir() or not name.parts:
                    continue
                if not member.isfile() or len(name.parts) != 1 or name.name in ("", ".", ".."):
                    raise TransferError(f"Refusing to unpack {member.name!r}: only plain files are expected.")
                target = upload_dir / name.name
                if target.exists() and not overwrite:
                    skipped += 1
                    continue
                with archive.extractfile(member) as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out, CHUNK)
                added += 1
    except tarfile.TarError as error:
        raise TransferError(f"{archive_path} is not a usable tar archive: {error}") from error
    print(f"Unpacked {added} file(s) into {upload_dir}; kept {skipped} that were already there.")

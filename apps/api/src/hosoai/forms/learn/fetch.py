"""Get an official form file and turn it into a PDF.

Only files linked from an official procedure page, on a .gov.vn host (also after
redirects), and only real Word/PDF files (some portals answer with an HTML viewer or an
"Access Denied" page instead of the file).
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pymupdf

MAGIC = {b"\xd0\xcf\x11\xe0": ".doc", b"PK\x03\x04": ".docx", b"%PDF": ".pdf"}


class FetchError(Exception):
    pass


def _official(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return urlparse(url).scheme == "https" and host.endswith(".gov.vn")


def download(url: str, dest_dir: Path, stem: str) -> Path:
    if not _official(url):
        raise FetchError(f"not an official https .gov.vn URL: {url}")
    with httpx.Client(
        follow_redirects=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"}
    ) as c:
        r = c.get(url)
    if not _official(str(r.url)):
        raise FetchError(f"redirected outside .gov.vn: {r.url}")
    if r.status_code != 200:
        raise FetchError(f"HTTP {r.status_code} for {url}")
    ext = next((e for m, e in MAGIC.items() if r.content.startswith(m)), None)
    if ext is None:
        raise FetchError("the portal did not return a Word or PDF file (viewer or error page)")
    path = dest_dir / f"{stem}-official{ext}"
    path.write_bytes(r.content)
    return path


def to_pdf(src: Path, dest: Path) -> Path:
    if src.suffix == ".pdf":
        shutil.copy(src, dest)
        return dest
    soffice = shutil.which("soffice")
    if soffice is None:
        raise FetchError("LibreOffice (soffice) is needed to convert Word forms to PDF")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
            check=True,
            capture_output=True,
            timeout=180,
        )
        out = Path(tmp) / f"{src.stem}.pdf"
        if not out.exists():
            raise FetchError("conversion to PDF failed")
        shutil.move(out, dest)
    return dest


def form_code(doc: pymupdf.Document) -> str | None:
    """'Mẫu TK05', 'Mẫu (Form) NA5', 'Mẫu CT01' -> the code printed on the form."""
    m = re.search(
        r"Mẫu\s*(?:\(Form\)\s*)?(?:số\s*)?([A-Z]{1,4}\s?\d{1,3}[a-z]?)\b", doc[0].get_text()
    )
    if not m:
        return None
    # some official files misprint the zero as a letter O ("Mẫu CCO1")
    return re.sub(r"O(?=\d)", "0", m.group(1).replace(" ", ""))


def form_title(doc: pymupdf.Document) -> str | None:
    """The first all-capitals line that is not the national motto, in sentence case."""
    for line in doc[0].get_text().splitlines()[:40]:
        t = re.sub(r"\(\d+\)|\s+", " ", line).strip()
        letters = [ch for ch in t if ch.isalpha()]
        if len(letters) < 10 or not all(ch.isupper() for ch in letters):
            continue
        if t.startswith(("CỘNG HÒA", "CỘNG HOÀ", "ĐỘC LẬP")):
            continue
        return t[0] + t[1:].lower()
    return None

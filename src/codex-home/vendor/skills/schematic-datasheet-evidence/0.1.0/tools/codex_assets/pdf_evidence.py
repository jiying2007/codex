"""Read-only PDF word locations; deliberately never infer connectivity."""
import argparse
from collections import namedtuple
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 64 * 1024
MAX_QUERIES = 32
MAX_MATCHES = 200
BackendResult = namedtuple("BackendResult", "returncode stdout stderr")


class EvidenceError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo arbitrary argument contents into an error receipt.
        raise EvidenceError("invalid-arguments", "invalid or missing CLI arguments; see --help")


def run_backend(command, stdout_limit=MAX_XML_BYTES,
                stderr_limit=MAX_DIAGNOSTIC_BYTES, timeout=30):
    """Drain both pipes with byte limits; never buffer unbounded child output."""
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        selector = selectors.DefaultSelector()
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {"stdout": stdout_limit, "stderr": stderr_limit}
        deadline = time.monotonic() + timeout
        try:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise EvidenceError("backend-timeout", "PDF backend exceeded its time limit")
                for key, _ in selector.select(min(remaining, 0.1)):
                    name = key.data
                    chunk = os.read(key.fileobj.fileno(),
                                    min(65536, limits[name] - len(buffers[name]) + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if len(buffers[name]) + len(chunk) > limits[name]:
                        raise EvidenceError("backend-output-limit", "PDF backend output exceeded its byte limit")
                    buffers[name].extend(chunk)
            try:
                code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise EvidenceError("backend-timeout", "PDF backend exceeded its time limit") from None
            return BackendResult(code, bytes(buffers["stdout"]), bytes(buffers["stderr"]))
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait()


def backend_warnings(stderr):
    """Retain diagnostic presence/classes without exposing PDF text or paths."""
    categories = set()
    for line in stderr.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        lower = line.lower()
        if "font" in lower or "unicode" in lower or "encoding" in lower:
            categories.add("font-or-text-mapping")
        elif "syntax" in lower:
            categories.add("pdf-syntax")
        else:
            categories.add("unclassified-backend-diagnostic")
    return [{"category": category, "message": "Backend diagnostic requires extraction review; raw text omitted."}
            for category in sorted(categories)]


def backend_identity():
    version = run_backend(["pdftotext", "-v"], stdout_limit=4096,
                          stderr_limit=4096, timeout=5)
    match = re.search(rb"(?m)^pdftotext version ([A-Za-z0-9.+~\-]{1,64})(?:\s|$)",
                      version.stdout + b"\n" + version.stderr)
    return {"name": "pdftotext", "version": match.group(1).decode("ascii")
            if version.returncode == 0 and match else "unknown"}


def file_digest(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        first = stream.read(5)
        if first != b"%PDF-":
            raise EvidenceError("invalid-pdf", "input does not start with a PDF header")
        digest.update(first)
        size += len(first)
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_PDF_BYTES:
                raise EvidenceError("input-limit", "PDF exceeds the 100 MiB input limit")
            digest.update(chunk)
    return digest.hexdigest()


def numbers(node, attributes):
    try:
        values = [float(node.attrib[key]) for key in attributes]
    except (KeyError, ValueError, OverflowError):
        raise EvidenceError("invalid-bbox", "PDF backend returned missing or invalid numeric fields") from None
    if not all(math.isfinite(value) for value in values):
        raise EvidenceError("invalid-bbox", "PDF backend returned non-finite numeric fields")
    return values


def extract_locations(xml_bytes, queries, limit=40):
    if not 1 <= limit <= MAX_MATCHES:
        raise EvidenceError("invalid-limit", "max-matches must be between 1 and 200")
    if not 1 <= len(queries) <= MAX_QUERIES or any(not q or len(q) > 256 for q in queries):
        raise EvidenceError("invalid-queries", "supply 1 to 32 nonempty queries of at most 256 characters")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise EvidenceError("backend-output-limit", "PDF backend XML exceeded its byte limit")
    if b"<!ENTITY" in xml_bytes:
        raise EvidenceError("invalid-xml", "XML entity declarations are not accepted")
    root = ET.fromstring(xml_bytes)
    pages = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "page"]
    if len(pages) != 1:
        raise EvidenceError("invalid-page-count", "expected exactly one extracted page")
    page = pages[0]
    page_size = numbers(page, ("width", "height"))
    if any(value <= 0 for value in page_size):
        raise EvidenceError("invalid-bbox", "PDF page dimensions must be positive")
    queries = list(dict.fromkeys(queries))
    matches = {q: [] for q in queries}
    counts = {q: 0 for q in queries}
    for node in page.iter():
        if node.tag.rsplit("}", 1)[-1] != "word":
            continue
        bbox = numbers(node, ("xMin", "yMin", "xMax", "yMax"))
        if bbox[0] > bbox[2] or bbox[1] > bbox[3]:
            raise EvidenceError("invalid-bbox", "PDF backend returned reversed word coordinates")
        word = "".join(node.itertext())
        if word in counts:
            counts[word] += 1
            if len(matches[word]) < limit:
                matches[word].append({"text": word, "bbox": bbox})
    return {"page_size": page_size,
            "coordinate_system": "poppler-bbox-page-coordinates",
            "match_mode": "exact-case-sensitive-whole-extracted-word",
            "results": [{"query": q, "count": counts[q],
                         "status": "located-only" if counts[q] else "not-found",
                         "truncated": counts[q] > limit, "matches": matches[q]} for q in queries],
            "connectivity_verified": False,
            "limitations": ["No pin pairing or wire tracing is performed.",
                            "A word may be split or absent despite visible content.",
                            "Coordinate proximity does not establish electrical connectivity."]}


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True, help="1-based physical PDF page")
    parser.add_argument("--text", action="append", required=True, help="exact extracted word; repeatable")
    parser.add_argument("--max-matches", type=int, default=40)
    backend = None
    warnings = []
    try:
        args = parser.parse_args(argv)
        if args.page < 1 or not 1 <= args.max_matches <= MAX_MATCHES:
            raise EvidenceError("invalid-arguments", "page must be positive; max-matches must be between 1 and 200")
        if not 1 <= len(args.text) <= MAX_QUERIES or any(not q or len(q) > 256 for q in args.text):
            raise EvidenceError("invalid-queries", "supply 1 to 32 nonempty queries of at most 256 characters")
        path = args.pdf.resolve(strict=True)
        if not path.is_file() or path.stat().st_size > MAX_PDF_BYTES:
            raise EvidenceError("invalid-input", "input must be a regular PDF no larger than 100 MiB")
        digest = file_digest(path)
        backend = backend_identity()
        completed = run_backend(["pdftotext", "-f", str(args.page), "-l", str(args.page),
                                 "-bbox", str(path), "-"])
        warnings = backend_warnings(completed.stderr)
        if completed.returncode:
            raise EvidenceError("backend-failed", "pdftotext failed; no extraction claimed")
        if file_digest(path) != digest:
            raise EvidenceError("source-changed", "PDF changed during extraction")
        result = extract_locations(completed.stdout, args.text, args.max_matches)
        if backend["version"] == "unknown":
            warnings.append({"category": "backend-version-unknown", "message": "Backend version could not be verified."})
        incomplete = any(r["truncated"] or not r["count"] for r in result["results"])
        needs_review = incomplete or bool(warnings)
        result.update({"source_sha256": digest, "physical_page": args.page,
                       "backend": backend, "backend_warnings": warnings,
                       "raw_diagnostics_included": False,
                       "extraction_status": "warning" if warnings else "no-diagnostics",
                       "status": "needs-review" if needs_review else "locations-returned"})
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if needs_review else 0
    except (OSError, ValueError, ET.ParseError) as error:
        code = error.code if isinstance(error, EvidenceError) else (
            "invalid-xml" if isinstance(error, ET.ParseError) else "input-or-backend-error")
        message = str(error) if isinstance(error, EvidenceError) else "input or backend data could not be read safely"
        print(json.dumps({"status": "error", "error_type": type(error).__name__,
                          "error_code": code, "message": message,
                          "backend": backend, "backend_warnings": warnings,
                          "raw_diagnostics_included": False,
                          "connectivity_verified": False}, allow_nan=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())

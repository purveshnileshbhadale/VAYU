import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def pdf_tools(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[PDF] {action}")

    try:
        if action in ("merge", "combine", "join"):
            files = params.get("files", [])
            if not files:
                return "List of PDF file paths is required for merging."

            output = params.get("output", "")
            if not output:
                output = str(_get_base_dir() / "merged.pdf")

            return _merge_pdfs(files, output)

        elif action in ("split", "separate"):
            path = params.get("path", "").strip()
            if not path:
                return "PDF file path is required for splitting."

            output_dir = params.get("output_dir", "")
            if not output_dir:
                output_dir = str(Path(path).parent / f"{Path(path).stem}_pages")

            return _split_pdf(path, output_dir)

        elif action in ("info", "metadata", "details"):
            path = params.get("path", "").strip()
            if not path:
                return "PDF file path is required."

            return _pdf_info(path)

        elif action in ("compress", "optimize"):
            path = params.get("path", "").strip()
            if not path:
                return "PDF file path is required."

            output = params.get("output", "")
            if not output:
                output = str(Path(path).parent / f"{Path(path).stem}_compressed.pdf")

            return _compress_pdf(path, output)

        elif action in ("pages", "count"):
            path = params.get("path", "").strip()
            if not path:
                return "PDF file path is required."

            return _page_count(path)

        elif action in ("extract", "extract_pages", "select"):
            path = params.get("path", "").strip()
            if not path:
                return "PDF file path is required."

            pages = params.get("pages", "")
            output = params.get("output", "")
            if not output:
                output = str(Path(path).parent / f"{Path(path).stem}_extracted.pdf")

            return _extract_pages(path, pages, output)

        return (
            f"Unknown action: '{action}'. "
            f"Available: merge, split, info, compress, pages, extract"
        )

    except ImportError as e:
        if "PyPDF2" in str(e):
            return "PyPDF2 is not installed. Run: pip install PyPDF2"
        return f"Missing dependency: {e}"
    except Exception as e:
        return f"PDF tool failed: {e}"


def _try_pypdf2():
    try:
        import PyPDF2
        return PyPDF2
    except ImportError:
        raise ImportError("PyPDF2")


def _merge_pdfs(files: list, output: str) -> str:
    PyPDF2 = _try_pypdf2()
    merger = PyPDF2.PdfMerger()

    valid_paths = []
    for f in files:
        fp = Path(f.strip())
        if fp.exists() and fp.suffix.lower() == ".pdf":
            valid_paths.append(str(fp))
        else:
            return f"File not found or not a PDF: {f}"

    if len(valid_paths) < 2:
        return "At least 2 PDF files are required for merging."

    for fp in valid_paths:
        merger.append(fp)

    merger.write(output)
    merger.close()

    return f"Merged {len(valid_paths)} PDFs into: {output}"


def _split_pdf(path: str, output_dir: str) -> str:
    PyPDF2 = _try_pypdf2()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)

        for i, page in enumerate(reader.pages):
            writer = PyPDF2.PdfWriter()
            writer.add_page(page)
            page_path = out_path / f"page_{i+1:03d}.pdf"
            with open(page_path, "wb") as pf:
                writer.write(pf)

    return f"Split {total} pages into: {out_path}"


def _pdf_info(path: str) -> str:
    PyPDF2 = _try_pypdf2()
    fp = Path(path)
    if not fp.exists():
        return f"File not found: {path}"

    size_mb = fp.stat().st_size / (1024 * 1024)

    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)
        meta = reader.metadata or {}

        info = [
            f"PDF: {fp.name}",
            f"Pages: {total}",
            f"Size: {size_mb:.2f} MB",
        ]

        if meta.get("/Title"):
            info.append(f"Title: {meta['/Title']}")
        if meta.get("/Author"):
            info.append(f"Author: {meta['/Author']}")
        if meta.get("/Subject"):
            info.append(f"Subject: {meta['/Subject']}")

        return "\n".join(info)


def _compress_pdf(path: str, output: str) -> str:
    PyPDF2 = _try_pypdf2()
    fp = Path(path)
    if not fp.exists():
        return f"File not found: {path}"

    original_size = fp.stat().st_size

    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        writer = PyPDF2.PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        with open(output, "wb") as of:
            writer.write(of)

    compressed_size = Path(output).stat().st_size
    saved_pct = (1 - compressed_size / original_size) * 100

    return (
        f"Compressed PDF: {original_size / 1024:.1f} KB → {compressed_size / 1024:.1f} KB "
        f"({saved_pct:.1f}% reduction). Saved to: {output}"
    )


def _page_count(path: str) -> str:
    PyPDF2 = _try_pypdf2()
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)
    return f"{path} has {total} page{'s' if total != 1 else ''}."


def _extract_pages(path: str, pages: str, output: str) -> str:
    PyPDF2 = _try_pypdf2()
    fp = Path(path)
    if not fp.exists():
        return f"File not found: {path}"

    try:
        page_nums = []
        parts = pages.replace(" ", "").split(",")
        for part in parts:
            if "-" in part:
                start, end = part.split("-")
                page_nums.extend(range(int(start), int(end) + 1))
            else:
                page_nums.append(int(part))
    except ValueError:
        return "Invalid page range. Use format like '1-5,6,8,10-12'"

    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total = len(reader.pages)
        valid = [p for p in page_nums if 1 <= p <= total]

        if not valid:
            return f"No valid pages in range (1-{total})."

        writer = PyPDF2.PdfWriter()
        for p in valid:
            writer.add_page(reader.pages[p - 1])

        with open(output, "wb") as of:
            writer.write(of)

    return f"Extracted {len(valid)} page(s): {output}"

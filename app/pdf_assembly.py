"""Lossless PDF assembly, including large image streams, with atomic output."""
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile


def merge_pdfs(paths, target: Path, *, strip_annotations=False, number_from_page=None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, suffix=".assembling.pdf", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        try:
            pikepdf = _load_pikepdf()
        except (ImportError, OSError):
            _merge_pdfs_with_pypdf(
                paths,
                temporary,
                strip_annotations=strip_annotations,
                number_from_page=number_from_page,
            )
        else:
            _merge_pdfs_with_pikepdf(
                pikepdf,
                paths,
                temporary,
                strip_annotations=strip_annotations,
                number_from_page=number_from_page,
            )
        try:
            temporary.replace(target)
        except PermissionError:
            target = target.with_name(target.stem + "_updated.pdf")
            temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def pdf_page_count(path: Path) -> int:
    try:
        pikepdf = _load_pikepdf()
    except (ImportError, OSError):
        try:
            from pypdf import PdfReader  # type: ignore
        except ModuleNotFoundError as exc:
            raise SystemExit("Missing pypdf for PDF page counting.") from exc
        try:
            return len(PdfReader(str(path)).pages)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Cannot read PDF page count for {Path(path).name}: {exc}") from exc
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def _load_pikepdf():
    import pikepdf  # type: ignore

    return pikepdf


def _merge_pdfs_with_pikepdf(
    pikepdf,
    paths,
    target: Path,
    *,
    strip_annotations: bool,
    number_from_page: int | None,
) -> None:
    with ExitStack() as stack:
        output = stack.enter_context(pikepdf.Pdf.new())
        version = output.pdf_version
        for path in paths:
            try:
                source = stack.enter_context(pikepdf.open(path))
                version = max(version, source.pdf_version)
                output.add_pages_from(source, forms="strip")
            except pikepdf.PdfError as exc:
                raise ValueError(f"Cannot assemble PDF {Path(path).name}: {exc}") from exc
        for index, page in enumerate(output.pages, start=1):
            if strip_annotations and "/Annots" in page.obj:
                del page.obj["/Annots"]
            if number_from_page is not None and index >= number_from_page:
                from reportlab.pdfgen import canvas

                box = page.mediabox
                width, height = float(box[2]) - float(box[0]), float(box[3]) - float(box[1])
                buffer = BytesIO()
                overlay = canvas.Canvas(buffer, pagesize=(width, height))
                overlay.setFont("Times-Roman", 9)
                overlay.drawString(36, 18, str(index))
                overlay.save()
                buffer.seek(0)
                with pikepdf.open(buffer) as stamp:
                    page.add_overlay(stamp.pages[0], pikepdf.Rectangle(box))
        output.save(target, min_version=version, compress_streams=True)


def _merge_pdfs_with_pypdf(
    paths,
    target: Path,
    *,
    strip_annotations: bool,
    number_from_page: int | None,
) -> None:
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
        from pypdf.generic import NameObject  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pikepdf is unavailable or blocked, and pypdf is not installed for fallback PDF assembly."
        ) from exc
    writer = PdfWriter()
    page_index = 0
    for path in paths:
        try:
            reader = PdfReader(str(path))
            for page in reader.pages:
                page_index += 1
                if strip_annotations and "/Annots" in page:
                    page.pop(NameObject("/Annots"), None)
                if number_from_page is not None and page_index >= number_from_page:
                    _stamp_page_with_pypdf(page, PdfReader, page_index)
                if strip_annotations and "/Annots" in page:
                    page.pop(NameObject("/Annots"), None)
                writer.add_page(page)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Cannot assemble PDF {Path(path).name}: {exc}") from exc
    with target.open("wb") as handle:
        writer.write(handle)


def _stamp_page_with_pypdf(page: object, PdfReader: object, page_number: int) -> None:
    from reportlab.pdfgen import canvas  # type: ignore

    width = float(page.mediabox.width)  # type: ignore[attr-defined]
    height = float(page.mediabox.height)  # type: ignore[attr-defined]
    buffer = BytesIO()
    overlay = canvas.Canvas(buffer, pagesize=(width, height))
    overlay.setFont("Times-Roman", 9)
    overlay.drawString(36, 18, str(page_number))
    overlay.save()
    buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])  # type: ignore[attr-defined,operator]

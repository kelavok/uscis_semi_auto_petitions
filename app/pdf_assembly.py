"""Lossless PDF assembly, including large image streams, with atomic output."""
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile


def merge_pdfs(paths, target: Path, *, strip_annotations=False, number_from_page=None) -> Path:
    import pikepdf

    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, suffix=".assembling.pdf", delete=False) as handle:
        temporary = Path(handle.name)
    try:
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
            output.save(temporary, min_version=version, compress_streams=True)
        try:
            temporary.replace(target)
        except PermissionError:
            target = target.with_name(target.stem + "_updated.pdf")
            temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)

import pytest


@pytest.mark.asyncio
async def test_artifact_download_pdf_smoke(tmp_path) -> None:
    """
    Smoke test that WeasyPrint PDF generation works without crashing.

    This guards against WeasyPrint dependency mismatches (eg pydyf>=0.11 with weasyprint 62.x).
    """
    # WeasyPrint is sync; run it in the event loop thread anyway.
    from weasyprint import HTML

    html_body = "<h1>Test</h1><p>Hello</p>"
    pdf_bytes = HTML(string=html_body).write_pdf()
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 500  # basic sanity check for a real PDF


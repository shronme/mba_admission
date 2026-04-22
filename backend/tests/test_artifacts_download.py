import pytest


@pytest.mark.asyncio
async def test_artifact_download_pdf_smoke(tmp_path) -> None:
    """
    Smoke test that WeasyPrint PDF generation works without crashing.

    This guards against WeasyPrint dependency mismatches (eg pydyf>=0.11 with weasyprint 62.x).
    Skips when WeasyPrint's native libs (gobject/pango/cairo) are unavailable on the host
    (e.g. macOS dev machines without Homebrew pango). CI/Docker installs them per CLAUDE.md.
    """
    html_body = "<h1>Test</h1><p>Hello</p>"
    try:
        # NB: importing weasyprint triggers cffi dlopen of gobject/pango/cairo,
        # so both ImportError and OSError are expected on hosts without the
        # native libs. `pytest.importorskip` only handles ImportError.
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_body).write_pdf()
    except ImportError as exc:
        pytest.skip(f"weasyprint not installed: {exc}")
    except OSError as exc:
        pytest.skip(f"WeasyPrint native libraries unavailable on host: {exc}")
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 500  # basic sanity check for a real PDF


"""
Document processing pipeline — triggered after a file is uploaded.

Steps:
1. Load the UploadedFile record from the DB.
2. Fetch raw bytes from storage.
3. Extract text (PDF or plain text).
4. Classify document type via DSPy (or keyword heuristics in mock mode).
5. Embed text chunks via OpenAI and upsert into pgvector (skipped if no API key).
6. Persist document_type + extracted text back to uploaded_files.
7. Post an assistant chat message to the candidate's most-recent active thread.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
import zipfile
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.sync_db import sync_session_scope
from app.db.enums import DocumentType, FileStatus
from app.db.models.files import UploadedFile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Human-readable labels for the chat notification
# ---------------------------------------------------------------------------
_TYPE_LABELS: dict[DocumentType, str] = {
    DocumentType.CV: "CV / résumé",
    DocumentType.LIFE_STORY: "life story / personal narrative",
    DocumentType.RECOMMENDATION_LETTER: "recommendation letter",
    DocumentType.GRADE_SHEET: "grade sheet / transcript",
    DocumentType.IRRELEVANT: "document (doesn't appear to be related to your application)",
    DocumentType.UNCLASSIFIED: "document",
}

# Maximum characters fed to the classifier (keep LLM cost low)
_CLASSIFY_MAX_CHARS = 4_000


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif")
_IMAGE_MIMES = frozenset(
    ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"]
)
_DOCX_MIMES = frozenset(
    [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ]
)

_EXTRACT_PROMPT = (
    "Extract all readable text from this document. "
    "Preserve structure (headings, bullet points, sections). "
    "Return only the extracted text — no commentary or explanation."
)


def _docx_plain_text(*, data: bytes, filename: str) -> str | None:
    """
    Extract text from DOCX bytes without an LLM.

    We prefer this over prompting the raw XML because:
    - it avoids truncating the XML (which would drop later CV sections)
    - it preserves all paragraphs deterministically
    """
    def _docx_xml_text() -> str | None:
        """
        Zip-level fallback: extract all visible text runs from Word XML.

        Important: many CV templates use text boxes / shapes that `python-docx`
        won't surface via `Document(...).paragraphs`. Those still appear in
        the underlying XML as `<w:t>...</w:t>` runs, often inside `<w:txbxContent>`.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Collect across main doc + headers/footers (some CVs place contact info there).
                xml_names = [
                    n
                    for n in zf.namelist()
                    if n.startswith("word/")
                    and n.endswith(".xml")
                    and (
                        n == "word/document.xml"
                        or n.startswith("word/header")
                        or n.startswith("word/footer")
                    )
                ]
                if not xml_names:
                    return None

                parts: list[str] = []
                # Very lightweight conversion:
                # - turn paragraph boundaries into newlines
                # - extract text runs
                for name in xml_names:
                    try:
                        xml = zf.read(name).decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    xml = re.sub(r"</w:p\s*>", "\n", xml)
                    # Capture text runs; Word sometimes uses xml:space="preserve".
                    runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL)
                    if not runs:
                        continue
                    text = "".join(runs)
                    text = re.sub(r"\s+\n", "\n", text)
                    parts.append(text)

                joined = "\n".join(parts)
                # Unescape common entities produced in WordprocessingML.
                joined = (
                    joined.replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&quot;", '"')
                    .replace("&apos;", "'")
                )
                cleaned = re.sub(r"[ \t]+", " ", joined)
                cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
                return cleaned or None
        except Exception:
            logger.exception("doc_processing docx_xml_extract_failed filename=%s", filename)
            return None

    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        parts: list[str] = []

        # Paragraphs
        for p in doc.paragraphs:
            t = (p.text or "").strip()
            if t:
                parts.append(t)

        # Tables (common for CV layouts)
        for table in doc.tables:
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    ct = (cell.text or "").strip()
                    if ct:
                        cells.append(ct)
                if cells:
                    parts.append(" | ".join(cells))

        text = "\n".join(parts).strip()
        # If python-docx yields very little (common with text boxes), fall back to XML run extraction.
        if not text or len(text) < 200:
            return _docx_xml_text()
        return text or None
    except Exception:
        logger.exception("doc_processing docx_plain_extract_failed filename=%s", filename)
        return _docx_xml_text()


def _pdf_plain_text(*, data: bytes, filename: str) -> str | None:
    """Extract text from PDF bytes (no LLM). Used for PDFs and as fallback."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        return text or None
    except Exception:
        logger.exception("doc_processing pdf_plain_extract_failed filename=%s", filename)
        return None


def _image_mime(filename: str, content_type: str | None) -> str:
    fn_l = filename.lower()
    if fn_l.endswith(".png"):
        return "image/png"
    if fn_l.endswith(".gif"):
        return "image/gif"
    if fn_l.endswith(".webp"):
        return "image/webp"
    if fn_l.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    ct = (content_type or "").lower()
    return ct if ct in _IMAGE_MIMES else "image/jpeg"


def _llm_extract(*, data: bytes, filename: str, content_type: str | None) -> str | None:
    """
    LLM-based extraction via OpenAI.

    Vision: images as base64 in image_url. PDFs are not accepted there (image-only
    MIME types); we extract text with pypdf first, then run the same text prompt
    as for plain-text uploads. DOCX is unpacked to XML before prompting.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    fn_l = filename.lower()
    ct_l = (content_type or "").lower()

    is_image = any(fn_l.endswith(e) for e in _IMAGE_EXTS) or ct_l in _IMAGE_MIMES
    is_pdf = ct_l == "application/pdf" or fn_l.endswith(".pdf")

    # ── PDFs → pypdf then text model (chat image_url rejects application/pdf) ─
    if is_pdf:
        raw = _pdf_plain_text(data=data, filename=filename)
        if not raw or not raw.strip():
            return None
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": _EXTRACT_PROMPT + "\n\n" + raw[:30_000]}],
            max_tokens=4096,
        )
        return resp.choices[0].message.content

    # ── Images → vision ───────────────────────────────────────────────────────
    if is_image:
        mime = _image_mime(filename, content_type)
        b64 = base64.b64encode(data).decode()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {"type": "text", "text": _EXTRACT_PROMPT},
                    ],
                }
            ],
            max_tokens=4096,
        )
        return resp.choices[0].message.content

    # ── DOCX / DOC → use deterministic extraction (avoid XML truncation) ──────
    if fn_l.endswith((".docx", ".doc")) or ct_l in _DOCX_MIMES:
        return _docx_plain_text(data=data, filename=filename)

    # ── Plain text → send directly ────────────────────────────────────────────
    if ct_l.startswith("text/") or fn_l.endswith((".txt", ".md", ".csv")):
        raw = data.decode("utf-8", errors="ignore").strip()
        if raw:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": _EXTRACT_PROMPT + "\n\n" + raw[:30_000]}],
                max_tokens=4096,
            )
            return resp.choices[0].message.content

    logger.info(
        "doc_processing unsupported_format filename=%s content_type=%s", filename, content_type
    )
    return None


def _code_extract(*, data: bytes, filename: str, content_type: str | None) -> str | None:
    """
    Fallback extraction without LLM (used when OPENAI_API_KEY is absent / mock mode).
    """
    ct_l = (content_type or "").lower()
    fn_l = filename.lower()

    if ct_l.startswith("text/") or fn_l.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", errors="ignore").strip() or None

    if ct_l == "application/pdf" or fn_l.endswith(".pdf"):
        return _pdf_plain_text(data=data, filename=filename)

    if fn_l.endswith(".docx") or ct_l in _DOCX_MIMES:
        return _docx_plain_text(data=data, filename=filename)

    logger.info(
        "doc_processing code_extract unsupported filename=%s content_type=%s",
        filename,
        content_type,
    )
    return None


def _extract_text(
    *, data: bytes, filename: str, content_type: str | None
) -> tuple[str | None, list[str] | None]:
    """
    Extract text and produce chunks. Prefers LLM extraction; falls back to
    code-based extraction when OPENAI_API_KEY is absent.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    extracted: str | None = None

    ct_l = (content_type or "").lower()
    fn_l = filename.lower()

    # DOCX: always prefer deterministic full extraction to avoid dropping tail content.
    if fn_l.endswith(".docx") or ct_l in _DOCX_MIMES:
        extracted = _docx_plain_text(data=data, filename=filename)

    if api_key and not extracted:
        try:
            extracted = _llm_extract(data=data, filename=filename, content_type=content_type)
        except Exception:
            logger.exception(
                "doc_processing llm_extract_failed filename=%s — falling back to code extraction",
                filename,
            )

    if not extracted:
        extracted = _code_extract(data=data, filename=filename, content_type=content_type)

    if not extracted or not extracted.strip():
        return None, None

    # Forward-only: cap the stored `extracted_text` at 200k characters per
    # FR-5. Existing rows are not backfilled; only new/reprocessed uploads
    # pick up the new cap. Older storage was 20k, which truncated long life
    # stories well before their conclusions.
    cleaned = extracted.strip()[:200_000]

    # Token-aware chunking aligned with `text-embedding-3-small`
    # (cl100k_base): 600 tokens/chunk, 50 overlap. The chunk list is hard-
    # capped at 200 as a safety ceiling (FR-5).
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=600,
        chunk_overlap=50,
    )
    raw_chunks = splitter.split_text(cleaned)
    chunks = [c.strip() for c in raw_chunks if c and c.strip()][:200]
    return cleaned, chunks


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_document(text: str) -> DocumentType:
    from app.core.dspy_runtime import openai_calls_enabled

    use_openai = openai_calls_enabled()

    snippet = text[:_CLASSIFY_MAX_CHARS]

    if use_openai:
        from app.core.dspy_runtime import run_dspy_module
        from app.dspy.document_classifier import OpenAIDocumentClassifier

        try:
            classifier = OpenAIDocumentClassifier()
            pred = run_dspy_module(classifier, document_text=snippet)
            raw = (getattr(pred, "document_type", "") or "").strip().lower()
            try:
                return DocumentType(raw)
            except ValueError:
                logger.warning(
                    "doc_classify unknown_type raw=%r — falling back to unclassified", raw
                )
                return DocumentType.UNCLASSIFIED
        except Exception:
            logger.exception("doc_classify openai_failed — falling back to static classifier")

    from app.dspy.document_classifier import StaticDocumentClassifier

    return StaticDocumentClassifier()(document_text=snippet)


# ---------------------------------------------------------------------------
# Embedding + vector upsert
# ---------------------------------------------------------------------------

def _embed_and_store(
    *,
    file_id: uuid.UUID,
    candidate_id: uuid.UUID,
    chunks: list[str],
) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("doc_processing embed_skipped reason=no_openai_api_key file_id=%s", file_id)
        return

    from openai import OpenAI
    from app.core.vector_store import upsert_chunks_sync

    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=chunks)
    embeddings = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]

    with sync_session_scope() as session:
        upsert_chunks_sync(
            session,
            file_id=file_id,
            candidate_id=candidate_id,
            chunks=chunks,
            embeddings=embeddings,
        )

    logger.info(
        "doc_processing embed_done file_id=%s chunks=%s", file_id, len(chunks)
    )


def _post_chat_notification(*, candidate_id: uuid.UUID, filename: str, doc_type: DocumentType) -> None:
    # Chat is deprecated/disabled. Keep as a no-op so older task code paths remain safe.
    label = _TYPE_LABELS.get(doc_type, "document")
    logger.info(
        "doc_processing chat_notification_skipped candidate_id=%s filename=%s doc_type=%s label=%s",
        candidate_id,
        filename,
        getattr(doc_type, "value", str(doc_type)),
        label,
    )


# ---------------------------------------------------------------------------
# In-process background job
# ---------------------------------------------------------------------------

def process_uploaded_document(file_id: str) -> dict:
    file_uuid = uuid.UUID(file_id)
    logger.info("doc_processing start file_id=%s", file_id)

    # --- 1. Load file record ---
    with sync_session_scope() as session:
        file_row = session.get(UploadedFile, file_uuid)
        if file_row is None:
            logger.error("doc_processing file_not_found file_id=%s", file_id)
            return {"status": "skipped", "reason": "not_found"}

        candidate_id: uuid.UUID = file_row.candidate_id
        original_filename: str = file_row.original_filename
        content_type: str | None = file_row.content_type
        storage_uri: str = file_row.storage_uri
        preset_doc_type: DocumentType | None = file_row.document_type

    try:
        # --- 2. Fetch raw bytes from storage ---
        from app.core.storage import get_storage_backend

        storage = get_storage_backend()
        stream, _ = storage.open_stream(storage_uri=storage_uri)
        data = stream.read()
        logger.info(
            "doc_processing bytes_fetched file_id=%s bytes=%s", file_id, len(data)
        )

        # --- 3. Extract text ---
        extracted_text, chunks = _extract_text(
            data=data,
            filename=original_filename,
            content_type=content_type,
        )
        logger.info(
            "doc_processing extracted file_id=%s chars=%s chunks=%s",
            file_id,
            len(extracted_text) if extracted_text else 0,
            len(chunks) if chunks else 0,
        )

        # --- 4. Classify (trust intake hint for CV / life story when preset on the row) ---
        if preset_doc_type in (DocumentType.CV, DocumentType.LIFE_STORY):
            doc_type = preset_doc_type
        elif extracted_text:
            doc_type = _classify_document(extracted_text)
        else:
            doc_type = DocumentType.UNCLASSIFIED
        logger.info("doc_processing classified file_id=%s doc_type=%s", file_id, doc_type)

        # --- 5. Embed and store in pgvector (no-op if OPENAI_API_KEY not set) ---
        if chunks:
            _embed_and_store(
                file_id=file_uuid,
                candidate_id=candidate_id,
                chunks=chunks,
            )

        # --- 6. Persist results to uploaded_files ---
        with sync_session_scope() as session:
            file_row = session.get(UploadedFile, file_uuid)
            if file_row is not None:
                file_row.document_type = doc_type
                file_row.status = FileStatus.REVIEWING
                file_row.extra = {
                    **(file_row.extra or {}),
                    "extracted_text": extracted_text,
                    "extracted_chunks": chunks,
                }

        # --- 7. Post chat notification (fires immediately so the candidate gets fast feedback) ---
        _post_chat_notification(
            candidate_id=candidate_id,
            filename=original_filename,
            doc_type=doc_type,
        )

        logger.info("doc_processing done file_id=%s doc_type=%s", file_id, doc_type)
        return {"status": "ok", "file_id": file_id, "document_type": doc_type.value}

    except Exception as exc:
        logger.exception("doc_processing failed file_id=%s", file_id)
        # Mark the file as FAILED so the UI can show an error state.
        try:
            with sync_session_scope() as session:
                file_row = session.get(UploadedFile, file_uuid)
                if file_row is not None and file_row.status == FileStatus.UPLOADING:
                    file_row.status = FileStatus.FAILED
                    file_row.extra = {**(file_row.extra or {}), "error": str(exc)}
        except Exception:
            logger.exception("doc_processing failed_persist file_id=%s", file_id)
        raise


def _process_uploaded_document_delay(file_id: str) -> None:
    from app.core.job_runner import JobType, job_runner

    job_runner.enqueue(JobType.PROCESS_UPLOADED_DOCUMENT, {"file_id": file_id})


process_uploaded_document.delay = _process_uploaded_document_delay  # type: ignore[attr-defined]

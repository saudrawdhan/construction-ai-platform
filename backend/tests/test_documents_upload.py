MARKER = "Zeta9UniqueMarker"
CONTENT = (
    f"Site safety audit. {MARKER} scaffold inspection completed on the north tower. "
    "Rebar delivery delayed by two days; concrete pour rescheduled."
).encode()


async def test_upload_text_document_indexes_and_is_searchable(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "1", "doc_type": "field_note", "title": "North Tower Audit"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["chunks_indexed"] >= 1
    assert body["characters"] > 0
    document_id = body["document_id"]

    fetched = await client.get(f"/api/v1/documents/{document_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "North Tower Audit"

    found = await client.get(
        f"/api/v1/documents/search?q={MARKER}", headers=admin_headers
    )
    assert found.status_code == 200
    hits = found.json()["results"]
    assert any(
        hit["source_type"] == "document" and hit["source_id"] == document_id for hit in hits
    )


async def test_upload_rejects_unsupported_type(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("payload.exe", b"MZ\x90\x00binary", "application/octet-stream")},
        data={"project_id": "1"},
    )
    assert response.status_code == 415


async def test_upload_rejects_pdf_extension_with_non_pdf_content(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("fake.pdf", b"not actually a pdf", "application/pdf")},
        data={"project_id": "1"},
    )
    assert response.status_code == 415
    assert "PDF" in response.json()["detail"]


async def test_upload_rejects_docx_extension_with_non_docx_content(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={
            "file": (
                "fake.docx",
                b"not actually a docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"project_id": "1"},
    )
    assert response.status_code == 415
    assert "Word document" in response.json()["detail"]


async def test_upload_rejects_empty_file(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"project_id": "1"},
    )
    assert response.status_code == 422


async def test_upload_supported_but_empty_text_returns_422(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("blank.txt", b"   \n\t  ", "text/plain")},
        data={"project_id": "1"},
    )
    assert response.status_code == 422


async def test_upload_unknown_project_returns_404(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "999999"},
    )
    assert response.status_code == 404


async def test_upload_forbidden_for_viewer(client, viewer_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=viewer_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    assert response.status_code == 403


async def test_upload_sets_has_file_and_original_filename(client, admin_headers):
    response = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    document_id = response.json()["document_id"]

    fetched = await client.get(f"/api/v1/documents/{document_id}", headers=admin_headers)
    body = fetched.json()
    assert body["has_file"] is True
    assert body["original_filename"] == "audit.txt"
    assert "storage_path" not in body


async def test_download_returns_the_original_bytes(client, admin_headers):
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    document_id = upload.json()["document_id"]

    response = await client.get(
        f"/api/v1/documents/{document_id}/download", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.content == CONTENT
    assert "audit.txt" in response.headers["content-disposition"]


async def test_download_allowed_for_viewer(client, admin_headers, viewer_headers):
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("audit.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    document_id = upload.json()["document_id"]

    response = await client.get(
        f"/api/v1/documents/{document_id}/download", headers=viewer_headers
    )
    assert response.status_code == 200
    assert response.content == CONTENT


async def test_download_unknown_document_returns_404(client, admin_headers):
    response = await client.get(
        "/api/v1/documents/999999/download", headers=admin_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


async def test_upload_and_download_roundtrip_arabic_filename(client, admin_headers):
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("تقرير_الموقع_اليومي.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    fetched = await client.get(f"/api/v1/documents/{document_id}", headers=admin_headers)
    assert fetched.json()["original_filename"] == "تقرير_الموقع_اليومي.txt"

    response = await client.get(
        f"/api/v1/documents/{document_id}/download", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.content == CONTENT


async def test_download_seeded_document_with_no_stored_file_returns_404(client, admin_headers):
    # Document #1 is from the ETL-imported seed corpus, uploaded long before this feature
    # existed — it has no original file on disk, only its extracted content_summary.
    response = await client.get("/api/v1/documents/1/download", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No original file was stored for this document"


async def test_download_when_storage_path_points_to_a_missing_file_returns_404(
    client, admin_headers, db_session
):
    # The third distinct 404 branch: a document that HAS a storage_path on record, but the file
    # is gone from disk (e.g. the volume was wiped or restored from a DB-only backup). The
    # endpoint must detect this and return a clean, specific 404 — not an unhandled FileResponse
    # error on a nonexistent path.
    from app.models import Document

    doc = Document(
        project_id=1, doc_type="uploaded", title="Ghost document",
        content_summary="placeholder", doc_date=None,
        storage_path="/uploads/definitely-does-not-exist-999999.txt",
        original_filename="ghost.txt",
    )
    db_session.add(doc)
    await db_session.flush()

    response = await client.get(f"/api/v1/documents/{doc.id}/download", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Stored file is missing"


async def test_delete_document_removes_row_chunks_and_file(client, admin_headers, db_session):
    from sqlalchemy import func, select

    from app.models import DocumentEmbedding

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("to-delete.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    document_id = upload.json()["document_id"]

    async def chunk_count() -> int:
        return await db_session.scalar(
            select(func.count())
            .select_from(DocumentEmbedding)
            .where(
                DocumentEmbedding.source_type == "document",
                DocumentEmbedding.source_id == document_id,
            )
        )

    assert await chunk_count() >= 1  # the upload created at least one indexed chunk

    deleted = await client.delete(f"/api/v1/documents/{document_id}", headers=admin_headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/api/v1/documents/{document_id}", headers=admin_headers)
    assert gone.status_code == 404

    assert await chunk_count() == 0  # its indexed chunks are gone too, not orphaned


async def test_delete_unknown_document_returns_404(client, admin_headers):
    response = await client.delete("/api/v1/documents/999999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


async def test_delete_document_forbidden_for_viewer(client, admin_headers, viewer_headers):
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=admin_headers,
        files={"file": ("viewer-cannot-delete.txt", CONTENT, "text/plain")},
        data={"project_id": "1"},
    )
    document_id = upload.json()["document_id"]
    response = await client.delete(
        f"/api/v1/documents/{document_id}", headers=viewer_headers
    )
    assert response.status_code == 403


async def test_delete_document_still_cited_as_claim_evidence_returns_409(
    client, admin_headers, db_session
):
    from sqlalchemy import select

    from app.models import ClaimEvidence

    # A document referenced by the claim-evidence chain must not be deletable — the FK rejects
    # it and the app's global handler returns a clean 409, the same FK-safe behavior every other
    # entity delete uses, rather than silently orphaning the evidence link.
    evidence = await db_session.scalar(select(ClaimEvidence).limit(1))
    assert evidence is not None, "seed data must include claim evidence"

    response = await client.delete(
        f"/api/v1/documents/{evidence.document_id}", headers=admin_headers
    )
    assert response.status_code == 409

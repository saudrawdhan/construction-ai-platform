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

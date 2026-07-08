async def test_list_documents_total(client, admin_headers):
    response = await client.get("/api/v1/documents?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 120


async def test_list_generated_documents_total(client, admin_headers):
    response = await client.get("/api/v1/documents/generated?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1060


async def test_filter_generated_documents_by_type(client, admin_headers):
    response = await client.get(
        "/api/v1/documents/generated?doc_type=meeting_minutes&size=5", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 200
    assert all(d["type"] == "meeting_minutes" for d in body["items"])


async def test_generated_document_route_precedence(client, admin_headers):
    # /documents/generated must not be captured by /documents/{document_id}
    response = await client.get("/api/v1/documents/generated/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == 1


async def test_missing_document_404(client, admin_headers):
    response = await client.get("/api/v1/documents/999999", headers=admin_headers)
    assert response.status_code == 404

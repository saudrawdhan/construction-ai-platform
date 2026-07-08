async def test_list_claims_total(client, admin_headers):
    response = await client.get("/api/v1/claims?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 120


async def test_get_claim_by_id(client, admin_headers):
    response = await client.get("/api/v1/claims/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["claim_number"] == "CLM-00001"


async def test_claim_evidence_chain(client, admin_headers):
    response = await client.get("/api/v1/claims/1/evidence", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["claim"]["id"] == 1
    assert body["evidence_count"] >= 1
    first = body["evidence"][0]
    assert first["change_order"] is not None
    assert first["decision"] is not None
    assert first["document"] is not None
    assert first["correspondence"] is not None


async def test_evidence_chain_missing_claim_404(client, admin_headers):
    response = await client.get("/api/v1/claims/999999/evidence", headers=admin_headers)
    assert response.status_code == 404

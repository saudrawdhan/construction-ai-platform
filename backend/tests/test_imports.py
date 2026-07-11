import io

from openpyxl import Workbook

SUPPLIER_CSV = (
    b"supplier_name,category,city,status\n"
    b"Alpha Materials,Steel,Riyadh,Active\n"
    b"Beta Concrete,Concrete,Dammam,Active\n"
    b"Gamma,,Jeddah,Active\n"  # missing category -> invalid row (line 4)
)


async def _supplier_total(client, headers) -> int:
    return (await client.get("/api/v1/suppliers?size=1", headers=headers)).json()["total"]


async def test_import_suppliers_csv_reports_and_creates(client, admin_headers):
    before = await _supplier_total(client, admin_headers)
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={"file": ("suppliers.csv", SUPPLIER_CSV, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_rows"] == 3
    assert report["valid_rows"] == 2
    assert report["invalid_rows"] == 1
    assert report["created"] == 2
    assert report["errors"][0]["row"] == 4  # header is line 1, so the third data row is line 4

    after = await _supplier_total(client, admin_headers)
    assert after == before + 2


async def test_import_suppliers_dry_run_creates_nothing(client, admin_headers):
    before = await _supplier_total(client, admin_headers)
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={"file": ("suppliers.csv", SUPPLIER_CSV, "text/csv")},
        data={"dry_run": "true"},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["dry_run"] is True
    assert report["valid_rows"] == 2
    assert report["created"] == 0
    assert await _supplier_total(client, admin_headers) == before


async def test_import_suppliers_xlsx(client, admin_headers):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["supplier_name", "category", "city", "status"])
    sheet.append(["Delta Steel", "Steel", "Riyadh", "Active"])
    sheet.append(["Epsilon MEP", "MEP", "Khobar", "Active"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={
            "file": (
                "suppliers.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_rows"] == 2
    assert report["created"] == 2


async def test_import_rejects_unsupported_type(client, admin_headers):
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={"file": ("suppliers.txt", b"not a spreadsheet", "text/plain")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 415


async def test_import_corrupt_xlsx_returns_422(client, admin_headers):
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={
            "file": (
                "suppliers.xlsx",
                b"this is not really a spreadsheet",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"dry_run": "false"},
    )
    assert response.status_code == 422


async def test_import_rejects_empty_file(client, admin_headers):
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=admin_headers,
        files={"file": ("suppliers.csv", b"", "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 422


async def test_supplier_import_template_downloads(client, admin_headers):
    response = await client.get("/api/v1/suppliers/import/template", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "supplier_name,category,city,status" in response.text


async def test_viewer_cannot_import(client, viewer_headers):
    response = await client.post(
        "/api/v1/suppliers/import",
        headers=viewer_headers,
        files={"file": ("suppliers.csv", SUPPLIER_CSV, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 403


async def test_import_projects_csv(client, admin_headers):
    csv_data = (
        b"project_code,project_name,project_type,client_name,city,status,budget\n"
        b"PRJ-9001,Test Tower,Tower,Aramco,Riyadh,Active,100000000\n"
        b"PRJ-9002,Test School,School,Ministry,Jeddah,Active,50000000\n"
    )
    response = await client.post(
        "/api/v1/projects/import",
        headers=admin_headers,
        files={"file": ("projects.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_rows"] == 2
    assert report["created"] == 2


async def _first_project_code(client, headers) -> str:
    response = await client.get("/api/v1/projects?size=1", headers=headers)
    return response.json()["items"][0]["project_code"]


async def _rfi_total(client, headers) -> int:
    return (await client.get("/api/v1/rfis?size=1", headers=headers)).json()["total"]


async def test_import_rfis_resolves_project_code(client, admin_headers):
    code = await _first_project_code(client, admin_headers)
    before = await _rfi_total(client, admin_headers)
    csv_data = (
        "project_code,rfi_number,subject,question,discipline,raised_by,assigned_to\n"
        f"{code},RFI-IMP-1,Rebar clarification,Confirm rebar spacing,Structural,Eng A,Eng B\n"
        "NOPE-0000,RFI-IMP-2,Bad row,No such project,Civil,Eng C,Eng D\n"
    ).encode()
    response = await client.post(
        "/api/v1/rfis/import",
        headers=admin_headers,
        files={"file": ("rfis.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_rows"] == 2
    assert report["valid_rows"] == 1
    assert report["created"] == 1
    assert report["errors"][0]["row"] == 3  # the second data row (line 3) has the unknown code
    assert "unknown project code 'NOPE-0000'" in report["errors"][0]["errors"][0]
    assert await _rfi_total(client, admin_headers) == before + 1


async def test_import_child_missing_project_code_is_row_error(client, admin_headers):
    code = await _first_project_code(client, admin_headers)
    # Second row omits project_code entirely -> reported, not a 500.
    csv_data = (
        "project_code,request_no,material_category\n"
        f"{code},PR-IMP-1,Steel\n"
        ",PR-IMP-2,Concrete\n"
    ).encode()
    response = await client.post(
        "/api/v1/procurement/purchase-requests/import",
        headers=admin_headers,
        files={"file": ("prs.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["valid_rows"] == 1
    assert report["created"] == 1
    assert report["errors"][0]["row"] == 3
    assert "project_code" in report["errors"][0]["errors"][0]


async def test_child_import_template_has_project_code(client, admin_headers):
    response = await client.get("/api/v1/meetings/import/template", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("project_code,")


async def test_viewer_cannot_import_child_entity(client, viewer_headers):
    csv_data = b"project_code,title,meeting_type\nPRJ-0100,Kickoff,Progress\n"
    response = await client.post(
        "/api/v1/meetings/import",
        headers=viewer_headers,
        files={"file": ("meetings.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 403

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
        b"PRJ-9001,Test Tower,Tower,Gulf Energy Holdings,Riyadh,Active,100000000\n"
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


async def test_import_project_code_is_case_insensitive(client, admin_headers):
    # A project code typed into a spreadsheet is human input: "prj-0001" must resolve the same as
    # "PRJ-0001", matching the purchase-order importer's normalization. A genuinely unknown code
    # is still rejected.
    code = await _first_project_code(client, admin_headers)
    csv_data = (
        "project_code,rfi_number,subject,question,discipline,raised_by,assigned_to\n"
        f"{code.lower()},RFI-CI-1,Case test,Confirm,Structural,Eng A,Eng B\n"
        "no-such-code,RFI-CI-2,Bad row,No such project,Civil,Eng C,Eng D\n"
    ).encode()
    response = await client.post(
        "/api/v1/rfis/import",
        headers=admin_headers,
        files={"file": ("rfis.csv", csv_data, "text/csv")},
        data={"dry_run": "true"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["valid_rows"] == 1  # the lower-cased code resolved
    assert report["invalid_rows"] == 1
    assert "unknown project code 'no-such-code'" in report["errors"][0]["errors"][0]


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


async def _first_request_no_and_supplier(client, headers) -> tuple[str, str]:
    pr = (await client.get("/api/v1/procurement/purchase-requests?size=1", headers=headers)).json()
    supplier = (await client.get("/api/v1/suppliers?size=1", headers=headers)).json()
    return pr["items"][0]["request_no"], supplier["items"][0]["supplier_name"]


async def _po_total(client, headers) -> int:
    return (
        await client.get("/api/v1/procurement/purchase-orders?size=1", headers=headers)
    ).json()["total"]


async def test_import_purchase_orders_resolves_request_no_and_supplier(client, admin_headers):
    request_no, supplier_name = await _first_request_no_and_supplier(client, admin_headers)
    before = await _po_total(client, admin_headers)
    csv_data = (
        "request_no,supplier_name,po_number,status\n"
        f"{request_no},{supplier_name},PO-IMP-1,Issued\n"
        "NOPE-0000,Some Unknown Supplier,PO-IMP-2,Issued\n"
    ).encode()
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=admin_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_rows"] == 2
    assert report["valid_rows"] == 1
    assert report["created"] == 1
    assert report["errors"][0]["row"] == 3
    row_errors = " ".join(report["errors"][0]["errors"])
    assert "unknown purchase request 'NOPE-0000'" in row_errors
    assert "unknown supplier 'Some Unknown Supplier'" in row_errors
    assert await _po_total(client, admin_headers) == before + 1


async def test_purchase_order_import_matches_request_no_and_supplier_case_insensitively(
    client, admin_headers
):
    """Human-typed spreadsheet values shouldn't fail on casing alone — WRONG.CASE and Wrong.Case
    should both resolve to the same real record as the exact casing stored in the database."""
    request_no, supplier_name = await _first_request_no_and_supplier(client, admin_headers)
    before = await _po_total(client, admin_headers)
    csv_data = (
        "request_no,supplier_name,po_number,status\n"
        f"{request_no.lower()},{supplier_name.upper()},PO-IMP-CASE,Issued\n"
    ).encode()
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=admin_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["valid_rows"] == 1, report["errors"]
    assert report["created"] == 1
    assert await _po_total(client, admin_headers) == before + 1


async def test_purchase_order_import_matches_supplier_with_extra_internal_whitespace(
    client, admin_headers
):
    """A stray extra space typed into a supplier name ("Risk  Supplier 001") shouldn't fail on
    whitespace alone — .strip() (applied at parse time) only catches leading/trailing spaces, not
    an internal double space, so this needs its own normalization and its own test."""
    request_no, supplier_name = await _first_request_no_and_supplier(client, admin_headers)
    doubled_space_name = "  ".join(supplier_name.split(" "))
    before = await _po_total(client, admin_headers)
    csv_data = (
        "request_no,supplier_name,po_number,status\n"
        f"{request_no},{doubled_space_name},PO-IMP-WS,Issued\n"
    ).encode()
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=admin_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["valid_rows"] == 1, report["errors"]
    assert report["created"] == 1
    assert await _po_total(client, admin_headers) == before + 1


async def test_purchase_order_import_blank_resolver_fields_are_row_errors(client, admin_headers):
    """Blank request_no/supplier_name must be reported as clear row errors (distinct from an
    unrecognized value) rather than crashing or being silently coerced into something else."""
    csv_data = b"request_no,supplier_name,po_number,status\n,,PO-IMP-BLANK,Issued\n"
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=admin_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["valid_rows"] == 0
    assert report["invalid_rows"] == 1
    row_errors = " ".join(report["errors"][0]["errors"])
    assert "request_no: this field is required" in row_errors
    assert "supplier_name: this field is required" in row_errors


async def test_purchase_order_import_derives_project_from_request(client, admin_headers):
    """The imported PO's project_id must match its resolved request's own project — proving
    project_id is genuinely derived from request_no, not left unset or wrong."""
    pr_response = await client.get(
        "/api/v1/procurement/purchase-requests?size=1", headers=admin_headers
    )
    pr = pr_response.json()["items"][0]
    supplier_name = (
        (await client.get("/api/v1/suppliers?size=1", headers=admin_headers)).json()
    )["items"][0]["supplier_name"]
    csv_data = (
        "request_no,supplier_name,po_number,status\n"
        f"{pr['request_no']},{supplier_name},PO-IMP-3,Issued\n"
    ).encode()
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=admin_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 200, response.text
    orders = (
        await client.get(
            f"/api/v1/procurement/purchase-orders?project_id={pr['project_id']}&size=100",
            headers=admin_headers,
        )
    ).json()["items"]
    assert any(o["po_number"] == "PO-IMP-3" and o["project_id"] == pr["project_id"] for o in orders)


async def test_purchase_order_import_template_has_no_project_code(client, admin_headers):
    """Deliberately different from the other child-entity templates: project_id is derived from
    the resolved request_no, so there's no project_code column to fill in."""
    response = await client.get(
        "/api/v1/procurement/purchase-orders/import/template", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("request_no,supplier_name,")
    assert "project_code" not in response.text


async def test_viewer_cannot_import_purchase_orders(client, viewer_headers):
    csv_data = b"request_no,supplier_name,po_number\nPR-001,Some Supplier,PO-999\n"
    response = await client.post(
        "/api/v1/procurement/purchase-orders/import",
        headers=viewer_headers,
        files={"file": ("pos.csv", csv_data, "text/csv")},
        data={"dry_run": "false"},
    )
    assert response.status_code == 403

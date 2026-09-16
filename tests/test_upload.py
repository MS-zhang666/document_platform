def test_upload_text_file(
    client,
):

    response = client.post(
        "/documents",
        files={
            "file": (
                "hello.txt",
                b"Hello Agent Platform",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["original_filename"] == "hello.txt"

    assert data["file_type"] == "txt"

    assert data["parse_status"] == "uploaded"

    document_id = data["id"]

    get_response = client.get(f"/documents/{document_id}")

    assert get_response.status_code == 200


def test_reject_unsupported_file(
    client,
):

    response = client.post(
        "/documents",
        files={
            "file": (
                "hello.docx",
                b"not really docx",
                ("application/octet-stream"),
            )
        },
    )

    assert response.status_code == 415


def test_result_not_ready(
    client,
):

    response = client.post(
        "/documents",
        files={
            "file": (
                "waiting.txt",
                b"waiting",
                "text/plain",
            )
        },
    )

    document_id = response.json()["id"]

    response = client.get(f"/documents/{document_id}/result")

    assert response.status_code == 409

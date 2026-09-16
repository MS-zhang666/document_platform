def create_document(
    client,
) -> str:

    response = client.post(
        "/documents",
        files={
            "file": (
                "job.txt",
                b"Hello background worker",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_create_parse_job(
    client,
):

    document_id = create_document(client)

    response = client.post(f"/documents/{document_id}/parse")

    assert response.status_code == 202

    job_id = response.json()["job_id"]

    status_response = client.get(f"/jobs/{job_id}")

    assert status_response.status_code == 200

    assert status_response.json()["status"] == "queued"


def test_cancel_and_retry_job(
    client,
):

    document_id = create_document(client)

    create_response = client.post(f"/documents/{document_id}/parse")

    job_id = create_response.json()["job_id"]

    cancel_response = client.post(f"/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200

    assert cancel_response.json()["cancel_requested"] is True

    retry_response = client.post(f"/jobs/{job_id}/retry")

    assert retry_response.status_code == 202

    new_job_id = retry_response.json()["job_id"]

    assert new_job_id != job_id

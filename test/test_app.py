import pytest
from unittest.mock import patch, ANY
from src.app import app
import pandas as pd
import ast
import io
from werkzeug.datastructures import FileStorage
from urllib.parse import unquote_plus


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("src.app.upload_df_to_s3")
@patch("src.app.get_df_from_csv_in_s3")
@patch("src.app.username", "test_user")
def test_remove_course(mock_get_df, mock_upload_df, client):
    # Mock DataFrame setup
    initial_courses = ["course1", "course2", "course3"]
    mock_df = pd.DataFrame(
        {"username": ["test_user"], "courses": [str(initial_courses)]}
    )
    mock_get_df.return_value = mock_df

    # Index of the course to be removed
    index_to_remove = 1

    # Perform the test request
    i_to_rem = index_to_remove
    response = client.post("/remove_course", data={"index": str(i_to_rem)})

    # Assertions
    assert response.status_code == 302
    mock_get_df.assert_called_once_with(ANY, ANY, ANY)
    mock_upload_df.assert_called_once_with(ANY, ANY, ANY, ANY)

    # Additional check to ensure the course is removed
    updated_courses_str = mock_df.loc[
        mock_df["username"] == "test_user", "courses"
    ].iloc[0]
    updated_courses = ast.literal_eval(updated_courses_str)
    assert len(updated_courses) == len(initial_courses) - 1
    assert initial_courses[index_to_remove] not in updated_courses


@patch("src.app.extract_emails_from_pdf")
@patch("src.app.check_syllabus_exists")
@patch("src.app.username", "test_user")
def test_course_detail(mock_check_syllabus, mock_extract_es, client):
    course_id = "test_course"
    mock_check_syllabus.return_value = (True, "syllabus.pdf")
    mock_extract_es.return_value = ["email1@example.com", "email2@example.com"]

    response = client.get(f"/course_detail_page/{course_id}")

    assert response.status_code == 200
    assert b"test_course" in response.data
    assert b"email1@example.com" in response.data
    assert b"email2@example.com" in response.data

    mock_check_syllabus.return_value = (False, "")
    response = client.get(f"/course_detail_page/{course_id}")

    assert response.status_code == 200
    assert b"email1@example.com" not in response.data
    assert b"email2@example.com" not in response.data


@patch("src.app.s3.upload_fileobj")
@patch("src.app.update_csv")
def test_upload_file(mock_update_csv, mock_upload_fileobj, client):
    mock_file = FileStorage(
        stream=io.BytesIO(b"test file content"),
        filename="test.pdf",
        content_type="application/pdf",
    )

    course_id = "course123"
    data = {"file": mock_file}

    response = client.post(
        f"/upload/{course_id}", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 302
    assert "course_detail" in response.location

    decoded_location = unquote_plus(response.location)
    assert "File uploaded successfully!" in decoded_location

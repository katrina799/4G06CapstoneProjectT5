import ast
import pandas as pd
import pytest
from unittest.mock import patch, ANY, MagicMock
from src.app import app
import io
import sys
import os


p = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
sys.path.insert(0, p)

# Test cases generated by: OpenAI. (2023). ChatGPT
# [Large language model]. https://chat.openai.com


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def s3_mock():
    with patch("boto3.client") as mock:
        yield mock


@patch("src.app.s3")
def test_download(mock_s3, client):
    # Set up a mock response for s3.get_object
    mock_file_content = b"file content"
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=mock_file_content))
    }

    # Test file name
    test_filename = "testfile.txt"

    # Perform the test request
    response = client.get(f"/download?filename={test_filename}")

    # Assertions
    assert response.status_code == 200
    assert response.data == mock_file_content
    assert (
        response.headers["Content-Disposition"]
        == f"attachment; filename={test_filename}"
    )
    mock_s3.get_object.assert_called_once_with(
        Bucket=app.config["BUCKET_NAME"], Key=test_filename
    )


@patch("src.app.upload_df_to_s3")
@patch("src.app.get_df_from_csv_in_s3")
# Directly set the username to 'test_user'
@patch("src.app.username", "test_user")
def test_change_username(mock_get_df, mock_upload_df, client):
    initial_username = "old_user"
    new_user = "new_user"

    # Mock DataFrame setup
    mock_df = pd.DataFrame(
        {"username": [initial_username], "courses": ["course1, course2"]}
    )
    mock_get_df.return_value = mock_df

    # Perform the test request
    response = client.post("/change_username", data={"newusername": new_user})

    # Assertions
    assert response.status_code == 302
    mock_get_df.assert_called_once_with(ANY, ANY, ANY)
    mock_upload_df.assert_called_once_with(mock_df, ANY, ANY, ANY)


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
    assert mock_get_df.call_count == 2
    mock_upload_df.assert_called_once_with(ANY, ANY, ANY, ANY)

    # Additional check to ensure the course is removed
    updated_courses_str = mock_df.loc[
        mock_df["username"] == "test_user", "courses"
    ].iloc[0]
    updated_courses = ast.literal_eval(updated_courses_str)
    assert len(updated_courses) == len(initial_courses) - 1


def test_course_detail_page(client):
    # Assuming 'course_id' is a valid course ID you want to test
    course_id = "CS101"
    response = client.get(f"/course_detail_page/{course_id}")

    assert response.status_code == 200
    assert b"Course Details" in response.data


@patch("src.app.extract_text_from_pdf", return_value="Mock PDF Text")
def test_upload_file(mock_extract_text, client):
    course_id = "CS101"
    data = {"file": (io.BytesIO(b"Mock PDF content."), "test.pdf")}
    response = client.post(
        f"/upload/{course_id}", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 302


@patch("src.app.upload_df_to_s3")
@patch("src.app.get_df_from_csv_in_s3")
# Directly set the username to 'test_user'
@patch("src.app.username", "test_user")
def test_add_course(mock_get_df, mock_upload_df, client):
    # Mock DataFrame setup
    initial_courses = ["course1", "course2"]
    mock_df = pd.DataFrame(
        {"username": ["test_user"], "courses": [str(initial_courses)]}
    )
    mock_get_df.return_value = mock_df

    # New course to add
    new_course = "new_course"

    # Perform the test request
    response = client.post("/add_course", data={"newcourse": new_course})

    # Assertions
    assert response.status_code == 302
    assert mock_get_df.call_count == 2  # Expecting two calls
    # Checking the parameters of the last call
    mock_get_df.assert_called_with(ANY, ANY, ANY)
    mock_upload_df.assert_called_once_with(mock_df, ANY, ANY, ANY)


@patch("src.app.username", new_callable=lambda: "test_user")
@patch("src.app.courses", new_callable=lambda: ["course1", "course2"])
def test_course_page(mock_username, mock_courses, client):
    # Perform the test request
    response = client.get("/course_page")

    # Assertions
    assert response.status_code == 200
    assert "text/html" in response.content_type
    data = response.data.decode("utf-8")
    assert "course-list" in data
    assert "course1" in data
    assert "course2" in data


@patch("src.app.username", new_callable=lambda: "test_user")
def test_profile_page(mock_username, client):
    # Perform the test request
    response = client.get("/profile_page")

    # Assertions
    assert response.status_code == 200
    assert "text/html" in response.content_type
    data = response.data.decode("utf-8")
    assert "/change_username" in data


@patch("app.get_df_from_csv_in_s3")
def test_tasks_page(mock_get_df, client):
    # Mocking the dataframe to return a predefined set of tasks
    mock_get_df.return_value = {
        "status": ["todo", "in_progress"],
        "title": ["Task 1", "Task 2"],
        "course": ["Course 1", "Course 2"],
        "due_date": ["2023-04-05", "2023-04-10"],
        "weight": [10, 15],
        # Add any other necessary fields according to your tasks_page logic
    }

    # Sending a GET request to the tasks route
    response = client.get("/tasks")

    # Verify the HTTP response status code is 200 (OK)
    assert response.status_code == 200


def test_forum_page(client):

    # Making a GET request to the forum page route
    response = client.get("/forum_page")  # Adjust the route as necessary
    print(response.data)

    # Check if the HTTP response status code is 200 (OK)
    assert response.status_code == 200

    assert (
        b"MacForum - The McMaster community dissussion board" in response.data
    )


def test_add_topic(client):

    # Define the form data for adding a new topic
    form_data = {
        "title": "New Topic",
        "content": "This is a new forum topic.",
        # Add any other necessary fields
    }

    # Sending a POST request to the add_topic route with the form data
    response = client.post(
        "/add_topic", data=form_data
    )  # Adjust the route as necessary

    # Check if the HTTP response indicates a successful operation
    assert response.status_code in [200, 302]  # 302 if there's a redirect


def test_topic_page(client):
    topic_id = "1"
    # Simulate a GET request to the topic page
    response = client.get(f"/forum/topic/{topic_id}")

    # Verify the response status code is OK
    assert response.status_code == 200
    # Optionally, verify that the response contains parts of the topic details
    assert b"What are your thoughts?" in response.data


def test_search(client):
    search_query = "spot"
    # Simulate a GET request with a search query
    response = client.get(f"/search_forum?query={search_query}")

    # Verify the response status code is OK
    assert response.status_code == 200
    # Optionally, verify that the response contains the search results
    assert b"McMaster Library" in response.data


def test_add_task(client):
    # Ensure all required form fields are included and have valid values
    task_data = {
        "course_name": "Test Course",
        "task_name": "Test Task",
        "due_date": "2023-01-01",  # Use an appropriate date format
        "weight": "5",
        # Assuming weight is a string; adjust the type as needed
        "est_hours": "2",
        # Assuming est_hours is a string; adjust the type as needed
    }
    response = client.post("/add_task", data=task_data)

    assert (
        response.status_code == 302
    )  # Or the appropriate success code for your application


def test_get_task(client):
    task_id = 100  # Assuming a task with this ID exists
    response = client.get(f"/get_task/{task_id}")
    assert response.status_code == 200
    # Verify the task's details are in the response
    assert (
        b"SFWRENG 4G06" in response.data
    )  # Based on the task's expected content


def test_delete_task(client):
    task_id = 60  # Assuming a task with this ID exists and can be deleted
    response = client.post(
        f"/delete_task/{task_id}"
    )  # Assuming deletion is a POST request
    assert (
        response.status_code == 200
    )  # Or appropriate code indicating success
    # Additional assertions can include verifying the task has been removed


def test_edit_task(client):
    task_id = 60  # Assuming a task with this ID exists and can be edited
    updated_task_data = {
        "title": "Updated Test Task",
        "description": "Updated Description",
    }
    response = client.post(f"/edit_task/{task_id}", data=updated_task_data)
    assert response.status_code == 200  # Or appropriate success code
    # Additional assertions to verify task update
    # This might involve checking response data or querying the database


def test_submit_feedback(client):
    feedback_data = {
        "username": "test_user",
        "name": "Test Name",
        "email": "test@example.com",
        "feedback_type": "website",  # or other relevant type
        "feedback": "This is a test feedback message.",
        # "status" and "developer_feedback" may not be required for submission
        # but if they are, include them as well
    }
    response = client.post("/submit_feedback", data=feedback_data)
    print(response.data)

    assert response.status_code in [200, 302]  # Check for success or redirect


def test_pomodoro_page(client):
    # Sending a GET request to the pomodoro_page route
    response = client.get("/pomodoro_page")

    # Check if the HTTP response status code is 200 (OK)
    assert response.status_code == 200

    assert (
        b"Pomodoro" in response.data
    )  # Adjust the keyword based on your page content


def test_get_weekly_data(client):
    response = client.get("/get_weekly_data")
    assert response.status_code == 200

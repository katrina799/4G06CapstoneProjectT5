import pytest
from unittest.mock import patch, MagicMock, ANY
from src.app import app
import pandas as pd
import ast


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@patch('src.app.upload_df_to_s3')
@patch('src.app.get_df_from_csv_in_s3')
# Directly patch the username with a string value
@patch('src.app.username', 'test_user')
def test_remove_course(mock_get_df, mock_upload_df, client):
    # Since we've directly patched username, we don't need to set its return
    # value

    # Mock DataFrame setup
    initial_courses = ['course1', 'course2', 'course3']
    mock_df = pd.DataFrame(
        {'username': ['test_user'], 'courses': [str(initial_courses)]})
    mock_get_df.return_value = mock_df

    # Index of the course to be removed
    index_to_remove = 1

    # Perform the test request
    response = client.post('/remove_course',
                           data={'index': str(index_to_remove)})

    # Assertions
    assert response.status_code == 302
    mock_get_df.assert_called_once_with(
        ANY, ANY, ANY)  # Use ANY for simplicity
    mock_upload_df.assert_called_once_with(ANY, ANY, ANY, ANY)

    # Additional check to ensure the course is removed
    updated_courses_str = mock_df.loc[mock_df['username']
                                      == 'test_user', 'courses'].iloc[0]
    updated_courses = ast.literal_eval(updated_courses_str)
    assert len(updated_courses) == len(initial_courses) - 1
    assert initial_courses[index_to_remove] not in updated_courses

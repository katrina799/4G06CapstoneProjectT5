from unittest.mock import patch, MagicMock
import pandas as pd
from unittest.mock import patch, MagicMock, ANY
import pytest
from src.app import app
import ast


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@patch('src.app.upload_df_to_s3')
@patch('src.app.get_df_from_csv_in_s3')
def test_remove_course(mock_get_df, mock_upload_df, client):
    test_username = 'test_user'
    initial_courses = ['course1', 'course2', 'course3']
    index_to_remove = 1
    real_df = pd.DataFrame(
        {'username': [test_username], 'courses': [str(initial_courses)]})
    mock_get_df.return_value = real_df

    app.username = test_username
    response = client.post('/remove_course',
                           data={'index': str(index_to_remove)})

    # Assertions
    assert response.status_code == 302
    mock_get_df.assert_called_once_with(ANY, ANY, ANY)
    mock_upload_df.assert_called_once_with(ANY, ANY, ANY, ANY)

    # Check if the course was removed
    updated_courses_str = real_df.loc[real_df['username']
                                      == app.username, 'courses'].iloc[0]
    updated_courses = ast.literal_eval(updated_courses_str)
    assert len(updated_courses) == 2  # One course should be removed
    # 'course2' was at index 1 and should be removed
    assert 'course2' not in updated_courses

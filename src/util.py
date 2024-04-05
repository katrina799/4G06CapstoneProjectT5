"""
Filename: <app_grid.py>

Description:
    Collection of helper functions designed for task management and data
    handling within a web application. Includes functionalities for adding
    tasks,fetching and uploading dataframes to AWS S3, and processing
    data. Integrates OpenAI for advanced text processing and uses pandas
    for data manipulation.

Author: All team members
Created: 2024-02-14
Last Modified: 2024-04-04
"""

# Helper functions that will be commonly used
import pandas as pd
import os
import openai
from io import StringIO
from datetime import datetime
from sklearn.base import TransformerMixin


# Initialize OpenAI API with your API key
openai.api_key = os.environ.get("OPENAI_API_KEY")


class SqueezeTransformer(TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X.squeeze()


def add_task_todo(
    course_name,  # Name of the course
    task_name,  # Task description
    due_date,  # Task due date in YYYY-MM-DD format
    weight,  # Importance of the task
    est_hours,  # Estimated hours to complete the task
    s3,  # S3 service client
    bucket_name,  # S3 bucket name for storing task data
    mock_tasks_data_file,  # File name for mock tasks data
):
    """
    This function adds a new task to a todo list for a course, considering the
    task's due date, weight, estimated hours to complete, and priority, and
    updates the task list in an S3 bucket.
    """
    try:
        # Convert due date to date object and calculate days until due
        if due_date not in ["", "Not Found", "0"]:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
            days_until_due = (due_date_obj - datetime.now()).days
            # Set priority based on days until due
            priority = "high" if days_until_due < 7 else "low"
        else:
            # Handle missing or invalid due dates
            due_date = "0000-00-00"
            priority = "unknown"
    except ValueError:
        # Handle errors in due date format
        due_date = "0000-00-00"
        priority = "unknown"

    # Fetch current tasks from S3
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    # Create new task entry
    new_task = {
        "id": tasks_df["id"].max() + 1 if not tasks_df.empty else 1,
        "title": task_name,
        "course": course_name,
        "due_date": due_date,
        "weight": weight,
        "est_time": est_hours,
        "priority": priority,
        "status": "todo",
    }

    # Append new task to tasks DataFrame
    new_task_df = pd.DataFrame([new_task])
    tasks_df = pd.concat([tasks_df, new_task_df], ignore_index=True)

    # Prepare DataFrame for S3 upload
    csv_buffer = StringIO()
    tasks_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    # Upload updated tasks list to S3
    s3.put_object(
        Bucket=bucket_name,
        Key=mock_tasks_data_file,
        Body=csv_buffer.getvalue(),
        ContentType="text/csv",
    )


def get_df_from_csv_in_s3(s3, bucket_name, s3_csv_file_path):
    """
    This function retrieves a CSV file from an S3 bucket and returns it as a
    pandas DataFrame. It requires the S3 resource, the name of the bucket,
    and the path to the CSV file within the S3 bucket as inputs.
    """
    # Retrieve the specified object from the S3 bucket
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    # Read the object (CSV content) directly into a DataFrame
    df = pd.read_csv(s3_obj["Body"])
    # Return the DataFrame
    return df


# Uploads a dataframe to AWS S3.
def upload_df_to_s3(df, s3, bucket_name, s3_csv_file_path):
    """
    Uploads a given dataframe to Amazon S3 storage.
    """
    new_csv_file_path = "poc-data/tmp.csv"  # Temporary local CSV file path.
    df.to_csv(new_csv_file_path)  # Save dataframe to a temporary CSV file.
    s3.upload_file(
        new_csv_file_path,  # Local file to upload.
        bucket_name,  # Destination bucket name.
        s3_csv_file_path,  # Destination path in S3.
    )
    os.remove(new_csv_file_path)  # Remove temporary local CSV file.


def write_order_csv_to_s3(s3, icon_order_path, df, bucket_name):
    """
    Writes DataFrame to a CSV file and uploads it to Amazon S3 bucket.
    """
    # Create a temporary CSV file path
    new_csv_file_path = "poc-data/tmp.csv"

    # Write DataFrame to the temporary CSV file
    df.to_csv(new_csv_file_path, index=False)

    # Upload the CSV file to S3
    s3.upload_file(
        new_csv_file_path,
        bucket_name,
        icon_order_path,
    )

    # Remove the temporary CSV file
    os.remove(new_csv_file_path)

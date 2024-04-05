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
    course_name,
    task_name,
    due_date,
    weight,
    est_hours,
    s3,
    bucket_name,
    mock_tasks_data_file,
):
    try:
        if due_date not in ["", "Not Found", "0"]:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
            days_until_due = (due_date_obj - datetime.now()).days
            priority = "high" if days_until_due < 7 else "low"
        else:
            due_date = "0000-00-00"
            priority = "unknown"
    except ValueError:
        due_date = "0000-00-00"
        priority = "unknown"

    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

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
    new_task_df = pd.DataFrame([new_task])
    tasks_df = pd.concat([tasks_df, new_task_df], ignore_index=True)

    csv_buffer = StringIO()
    tasks_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    s3.put_object(
        Bucket=bucket_name,
        Key=mock_tasks_data_file,
        Body=csv_buffer.getvalue(),
        ContentType="text/csv",
    )


# Get a specific csv file from s3 and return it as a dataframe
def get_df_from_csv_in_s3(s3, bucket_name, s3_csv_file_path):
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    df = pd.read_csv(s3_obj["Body"])
    return df


# Upload a dataframe to AWS s3
def upload_df_to_s3(df, s3, bucket_name, s3_csv_file_path):
    new_csv_file_path = "poc-data/tmp.csv"
    df.to_csv(new_csv_file_path)
    s3.upload_file(
        new_csv_file_path,
        bucket_name,
        s3_csv_file_path,
    )
    os.remove(new_csv_file_path)


def write_order_csv_to_s3(s3, icon_order_path, df, bucket_name):
    new_csv_file_path = "poc-data/tmp.csv"
    df.to_csv(new_csv_file_path, index=False)
    s3.upload_file(
        new_csv_file_path,
        bucket_name,
        icon_order_path,
    )
    os.remove(new_csv_file_path)

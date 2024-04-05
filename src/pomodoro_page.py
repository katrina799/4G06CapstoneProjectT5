"""
Filename: <pomodoro_page.py>

Description:
    Manages Pomodoro timer functionalities in a web app. Allows users to start
    Pomodoro timers for tasks, view and update task statuses, and track weekly
    Pomodoro counts. Utilizes AWS S3 for storing task and Pomodoro count data.

Author: Shuting Shi
Created: 2024-01-21
Last Modified: 2024-04-04
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    jsonify,
)

try:
    from src.util import (
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        get_df_from_csv_in_s3,
    )

import pandas as pd
from io import StringIO
from datetime import datetime, timezone

pomodoro_blueprint = Blueprint("pomodoro", __name__)


@pomodoro_blueprint.route("/pomodoro_page", methods=["GET"])
def pomodoro_page():
    """
    Render the Pomodoro page with optional task ID, estimated time,
    and username.
    """
    # Retrieve task ID from request query parameters
    task_id = request.args.get("task_id", None)

    # Retrieve username from application configuration
    username = current_app.config["username"]

    # Retrieve estimated time from request query parameters
    est_time = request.args.get("est_time", default=None)

    # Retrieve current page from application configuration
    # and update it to 'pomodoro_page'
    current_page = current_app.config["current_page"]
    current_app.config["current_page"] = "pomodoro_page"

    # If task ID is provided, ensure it is an integer and update
    # its status to 'in_progress'
    if task_id:
        task_id = int(task_id)  # Ensure task_id is an integer
        if update_task_status_endpoint(task_id, "in_progress"):
            print(f"Task {task_id} updated to in_progress")

    # Render the Pomodoro page template with provided parameters
    return render_template(
        "pomodoro_page.html",
        username=username,
        current_page=current_page,
        est_time=est_time,
        task_id=task_id,
    )


@pomodoro_blueprint.route(
    "/update_task_status/<int:task_id>/<string:new_status>", methods=["POST"]
)
def update_task_status_endpoint(task_id, new_status):
    """
    Endpoint to update the status of a task.
    """
    # Path to mock tasks data file
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    # Name of the S3 bucket
    bucket_name = current_app.config["BUCKET_NAME"]
    # Boto3 S3 client
    s3 = current_app.config["S3_CLIENT"]

    # Fetch the current tasks DataFrame from S3
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    # Check if the task exists
    if task_id in tasks_df["id"].values:
        # Update the status of the task
        tasks_df.loc[tasks_df["id"] == task_id, "status"] = new_status
        # Write the updated DataFrame back to S3
        write_df_to_csv_in_s3(s3, bucket_name, mock_tasks_data_file, tasks_df)

        # Return JSON response indicating success
        return jsonify(
            {
                "message": "Task status updated successfully",
                "status": new_status,
            }
        )
    else:
        # Return JSON response indicating task not found
        return jsonify({"error": "Task not found"}), 404


@pomodoro_blueprint.route("/get_weekly_data", methods=["GET"])
def get_weekly_data():
    """
    Router for getting weekly data from s3
    """
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    utc_now = datetime.now(timezone.utc)
    current_week = utc_now.isocalendar()[1]
    tomato_df = get_df_from_csv_in_s3(
        s3, bucket_name, current_app.config["TOMATO_DATA_KEY"]
    )
    if tomato_df["week_of_year"].iloc[0] != current_week:
        # Reset the weekly data since it's a new week
        tomato_df = initialize_weekly_data()
        write_df_to_csv_in_s3(
            s3, bucket_name, current_app.config["TOMATO_DATA_KEY"], tomato_df
        )
    # Convert DataFrame to JSON response
    return jsonify(tomato_df.to_dict(orient="records"))


def initialize_weekly_data():
    """
    Initialize weekly data DataFrame with zero records for each day
    of the week.
    """
    # Initialize the weekly data for each day to zero
    days = [
        "Saturday",
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
    ]
    # Get the current week of the year
    week_of_year = datetime.now().isocalendar()[1]
    # Create dictionary for DataFrame construction
    data = {"day": days, "count": [0] * 7, "week_of_year": [week_of_year] * 7}
    # Create DataFrame from dictionary
    return pd.DataFrame(data)


@pomodoro_blueprint.route("/update_tomato/<day>", methods=["POST"])
def update_tomato(day):
    """
    Update Tomato count for weekly achievements form
    """
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    tomato_data_key = current_app.config["TOMATO_DATA_KEY"]
    utc_now = datetime.now(timezone.utc)
    current_week = utc_now.isocalendar()[1]

    try:
        # Load existing data or initialize if not present
        try:
            tomato_df = get_df_from_csv_in_s3(s3, bucket_name, tomato_data_key)
            # Check if it's a new week
            if tomato_df["week_of_year"].iloc[0] != current_week:
                tomato_df["count"] = 0
                tomato_df["week_of_year"] = current_week
        except s3.exceptions.NoSuchKey:
            tomato_df = pd.DataFrame(
                {
                    "day": [
                        "Saturday",
                        "Sunday",
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                    ],
                    "count": [0, 0, 0, 0, 0, 0, 0],
                    "week_of_year": [current_week] * 7,
                }
            )

        # Update count for the specified day
        if day in tomato_df["day"].values:
            tomato_df.loc[tomato_df["day"] == day, "count"] += 1
            write_df_to_csv_in_s3(s3, bucket_name, tomato_data_key, tomato_df)
            return jsonify({"message": "Tomato count updated successfully"})
        else:
            return jsonify({"message": "Invalid day"}), 400

    except Exception as e:
        print(f"An error occurred: {e}")
        return (
            jsonify(
                {"message": "An error occurred while updating tomato count"}
            ),
            500,
        )


def write_df_to_csv_in_s3(client, bucket, key, dataframe):
    """
    Write DataFrame to a CSV file in Amazon S3 bucket.

    Returns:
        None
    """
    # Convert DataFrame to CSV format
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, index=False)

    # Put CSV object into S3 bucket
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_buffer.getvalue(),
        ContentType="text/csv",
    )

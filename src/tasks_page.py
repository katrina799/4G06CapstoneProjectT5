"""
Filename: tasks_module.py

Description:
    Handles task management for a web application, including displaying tasks,
    adding new tasks, editing, and deleting tasks. Integrates with AWS S3 for
    task data storage and retrieval. Supports filtering tasks by date and
    status, and updating task status directly from the tasks page.

Author: Qiang Gao
Created: 2024-01-24
Last Modified: 2024-04-04
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    jsonify,
    url_for,
)

try:
    from src.util import (
        add_task_todo,
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        add_task_todo,
        get_df_from_csv_in_s3,
    )

import pandas as pd
from io import StringIO
from datetime import datetime, timedelta

tasks_blueprint = Blueprint("tasks", __name__)


@tasks_blueprint.route("/tasks", methods=["GET", "POST"])
def tasks_page():
    """
    Router to tasks page
    """
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    current_page = current_app.config["current_page"]
    current_app.config["current_page"] = "tasks"
    tasks_df = get_df_from_csv_in_s3(
        s3, bucket_name, current_app.config["MOCK_DATA_POC_TASKS"]
    )

    # Replace invalid dates and convert to datetime
    tasks_df["due_date"] = tasks_df["due_date"].replace("0000-00-00", pd.NaT)
    tasks_df["due_date"] = pd.to_datetime(
        tasks_df["due_date"], errors="coerce"
    )

    # Convert the tasks DataFrame to a list of dictionaries
    tasks = (
        tasks_df.groupby("status")
        .apply(lambda x: x.drop("status", axis=1).to_dict(orient="records"))
        .to_dict()
    )
    today = datetime.now().date()
    end_date = today + timedelta(days=21)
    tasks_df["due_date"] = pd.to_datetime(tasks_df["due_date"])
    filtered_tasks = tasks_df[
        (tasks_df["status"].isin(["todo", "in_progress"]))
        & (tasks_df["due_date"] >= pd.Timestamp(today))
        & (tasks_df["due_date"] <= pd.Timestamp(end_date))
    ]

    # Convert due dates to strings in 'YYYY-MM-DD' format
    filtered_tasks["due_date"] = filtered_tasks["due_date"].dt.strftime(
        "%Y-%m-%d"
    )

    # Convert tasks to a list of dictionaries for the frontend
    tasks_for_calendar = filtered_tasks[
        ["title", "course", "due_date", "weight"]
    ].to_dict(orient="records")

    for task in tasks_for_calendar:
        if pd.isna(task["weight"]):
            task["weight"] = None

    print("user_name in tasks page", current_app.config["username"])
    return render_template(
        "tasks.html",
        username=current_app.config["username"],
        tasks=tasks,
        tasks_for_calendar=tasks_for_calendar,
        current_page=current_page,
    )


# Update tasks status after dragging
@tasks_blueprint.route("/update_task_status", methods=["POST"])
def update_task_status():
    """
    Update the status of a task after it has been dragged.
    """
    # Get bucket name and S3 client
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]

    # Get JSON data from request
    data = request.get_json()

    try:
        # Extract task ID from JSON data
        task_id = int(data["id"])
    except ValueError:
        # Return error message for invalid task ID format
        return jsonify({"message": "Invalid task ID format"}), 400

    # Extract new status from JSON data
    new_status = data["status"]

    # Get DataFrame of tasks from CSV file in S3
    tasks_df = get_df_from_csv_in_s3(
        s3, bucket_name, current_app.config["MOCK_DATA_POC_TASKS"]
    )

    # Check if task ID exists in DataFrame
    if task_id in tasks_df["id"].tolist():
        # Update status of task with given ID
        tasks_df.loc[tasks_df["id"] == task_id, "status"] = new_status

        # Write updated DataFrame back to CSV file in S3
        csv_buffer = StringIO()
        tasks_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=current_app.config["MOCK_DATA_POC_TASKS"],
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )

        # Return success message
        return jsonify({"message": "Task status updated successfully"})
    else:
        # Return error message for task not found
        return jsonify({"message": "Task not found"}), 404


# Route for adding a task via POST request
@tasks_blueprint.route("/add_task", methods=["POST"])
def add_task():
    """
    Add a task to the to-do list.

    Retrieves necessary paths and clients from the app configuration.
    Gets task information from form data, including course name, task name,
    due date, weight, and estimated hours. Adds the task to the to-do list
    and redirects to the tasks page.
    """
    # Get paths and clients from app configuration
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]

    # Get task information from form data
    course_name = request.form.get("course_name")
    task_name = request.form.get("task_name")
    due_date = request.form.get("due_date")
    weight = request.form.get("weight", 0)
    est_hours = request.form.get("est_hours", 0)

    # Add task to todo list
    add_task_todo(
        course_name,
        task_name,
        due_date,
        weight,
        est_hours,
        s3,
        bucket_name,
        mock_tasks_data_file,
    )

    # Redirect to tasks page
    return redirect(url_for("tasks_page"))


@tasks_blueprint.route("/get_task/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """
    Retrieve details of a task by task ID.
    """
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    try:
        # Load the tasks DataFrame from CSV in S3
        tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

        # Find the task by task_id
        task_row = tasks_df.loc[tasks_df["id"] == task_id]

        if not task_row.empty:
            # Convert the task_row DataFrame to a dictionary
            task_details = task_row.to_dict(orient="records")[0]
            return jsonify(task_details)
        else:
            return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        print(f"An error occurred while fetching task details: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


@tasks_blueprint.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    """
    Delete a task with the given ID.
    """
    # File path for mock tasks data and S3 bucket name
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    bucket_name = current_app.config["BUCKET_NAME"]
    # S3 client
    s3 = current_app.config["S3_CLIENT"]
    try:
        # Load tasks data from CSV in S3
        tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
        # Check if task ID exists in the tasks DataFrame
        if task_id in tasks_df["id"].values:
            # Remove task with the specified ID from DataFrame
            tasks_df = tasks_df[tasks_df["id"] != task_id]
            # Write updated DataFrame to CSV buffer
            csv_buffer = StringIO()
            tasks_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            # Put updated CSV data back to S3
            s3.put_object(
                Bucket=bucket_name,
                Key=mock_tasks_data_file,
                Body=csv_buffer.getvalue(),
                ContentType="text/csv",
            )
            # Return success message and HTTP status code 200
            return jsonify({"message": "Task deleted successfully"}), 200
        else:
            # Return task not found message and HTTP status code 404
            return jsonify({"message": "Task not found"}), 404
    except Exception as e:
        # Print error message and return internal server error message with
        # HTTP status code 500
        print(f"An error occurred: {e}")
        return (
            jsonify({"message": "An error occurred while deleting the task"}),
            500,
        )


@tasks_blueprint.route("/edit_task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    """
    Edit a task identified by its ID.
    """
    # File path for mock tasks data
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    # Bucket name for S3
    bucket_name = current_app.config["BUCKET_NAME"]
    # S3 client
    s3 = current_app.config["S3_CLIENT"]
    # Get DataFrame of tasks from CSV stored in S3
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    # Retrieve existing task based on task ID
    existing_task = tasks_df.loc[tasks_df["id"] == task_id].iloc[0]
    # Retrieve new task details from request form data
    new_course_name = request.form.get("course_name")
    new_task_name = request.form.get("task_name")
    new_due_date_str = request.form.get("due_date")
    new_weight = request.form.get("weight")
    new_est_hours = request.form.get("est_hours")

    # Calculate priority based on due date
    if new_due_date_str:
        new_due_date = datetime.strptime(new_due_date_str, "%Y-%m-%d").date()
        days_until_due = (new_due_date - datetime.now().date()).days
        new_priority = "high" if days_until_due < 7 else "low"
        formatted_due_date = new_due_date.strftime("%Y-%m-%d")
    else:
        formatted_due_date = existing_task["due_date"]
        new_priority = existing_task["priority"]

    # Return error if task ID does not exist in DataFrame
    if task_id not in tasks_df["id"].values:
        return jsonify({"message": "Task not found"}), 404

    try:
        # Update task details in DataFrame
        task_index = tasks_df.index[tasks_df["id"] == task_id].tolist()[0]
        tasks_df.at[task_index, "course"] = new_course_name
        tasks_df.at[task_index, "title"] = new_task_name
        tasks_df.at[task_index, "due_date"] = formatted_due_date
        tasks_df.at[task_index, "weight"] = new_weight
        tasks_df.at[task_index, "est_time"] = new_est_hours
        tasks_df.at[task_index, "priority"] = new_priority

        # Write updated DataFrame back to CSV in S3
        csv_buffer = StringIO()
        tasks_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=mock_tasks_data_file,
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )
        return jsonify({"message": "Task updated successfully"}), 200
    except Exception as e:
        # Handle error if updating task fails
        print(f"An error occurred when updating task: {e}")
        return (
            jsonify({"message": "An error occurred while updating the task"}),
            500,
        )

"""
Filename: <feedback_page.py>

Description:
    Manages feedback for a web app. Supports submitting and viewing feedback,
    using AWS S3 for storage. Feedback is categorized as 'viewed' or 'pending'.
    This module facilitates feedback form rendering, submission to S3, and
    retrieval/display of feedback from S3 based on user interactions.

Author: Qianni Wang
Created: 2024-01-23
Last Modified: 2024-04-03
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    url_for,
)

import os
import uuid
import pandas as pd

feedback_blueprint = Blueprint("feedback", __name__)


@feedback_blueprint.route("/feedback_page", methods=["GET", "POST"])
def feedback_page():
    """
    Route to the feedback page.
    """
    # Retrieve necessary configurations
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    current_app.config["current_page"] = "feedback_page"

    # Read feedback data from S3 bucket
    df = read_feedback_csv_from_s3(s3, bucket_name, "feedback.csv")

    # Filter feedback data for the current user
    viewed = df.loc[(df["username"] == username) & (df["status"] == 1)]
    pending = df.loc[(df["username"] == username) & (df["status"] == 0)]

    # Convert filtered feedback data to dictionaries
    viewed_feedback_list = viewed.to_dict("records")
    pending_feedback_list = pending.to_dict("records")

    # Render feedback page with relevant data
    return render_template(
        "feedback_page.html",
        username=current_app.config["username"],
        current_page=current_page,
        viewed_feedback_list=viewed_feedback_list,
        pending_feedback_list=pending_feedback_list,
    )


def read_feedback_csv_from_s3(s3, bucket_name, key):
    """
    Read feedback CSV file from Amazon S3 bucket.
    """
    try:
        # Get object from S3 bucket
        response = s3.get_object(Bucket=bucket_name, Key=key)

        # Read CSV into a DataFrame
        df = pd.read_csv(response["Body"])

        # Fill NaN values with empty string
        df.fillna("", inplace=True)

        return df
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame(columns=["username", "orders"])


@feedback_blueprint.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    """
    Store the feedback data in an Amazon S3 bucket.
    """
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]

    if request.method == "POST":
        # Extract feedback data from the form
        name = request.form.get("name", default=None)
        email = request.form.get("email", default=None)
        feedback_type = request.form["feedback_type"]
        feedback = request.form["feedback"]

        # Generate a unique feedback ID
        feedback_id = str(uuid.uuid4())

        # Construct a dictionary to create a DataFrame for the new feedback
        feedback_data = {
            "feedback_id": [feedback_id],
            "username": [username],
            "name": [name],
            "email": [email],
            "feedback_type": [feedback_type],
            "feedback": [feedback],
            "status": [0],  # Initial status is set to 0
            "developer_feedback": [""],  # Developer feedback initially empty
        }
        new_feedback_df = pd.DataFrame(feedback_data)

        # Path to the feedback data file in the S3 bucket
        feedback_data_path = "feedback.csv"

        try:
            # Try to read existing feedback data from S3
            response = s3.get_object(
                Bucket=bucket_name, Key=feedback_data_path
            )
            feedback_df = pd.read_csv(response["Body"])
        except s3.exceptions.NoSuchKey:
            # If no such key (file) exists, create an empty DataFrame
            feedback_df = pd.DataFrame(
                columns=[
                    "feedback_id",
                    "username",
                    "name",
                    "email",
                    "feedback_type",
                    "feedback",
                    "status",
                    "developer_feedback",
                ]
            )

        # Concatenate new feedback DataFrame with existing data
        feedback_df = pd.concat(
            [feedback_df, new_feedback_df], ignore_index=True
        )

        # Temporary file path to save the updated CSV
        new_csv_file_path = "poc-data/tmp.csv"

        # Write the updated DataFrame to a temporary CSV file
        feedback_df.to_csv(new_csv_file_path, index=False)

        # Upload the temporary CSV file to the S3 bucket
        s3.upload_file(new_csv_file_path, bucket_name, feedback_data_path)

        # Remove the temporary CSV file
        os.remove(new_csv_file_path)

    # Redirect to the feedback page
    return redirect(url_for("feedback.feedback_page"))

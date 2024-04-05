"""
Filename: <app.py>

Description:
    This file serves as the main entry point for a Flask-based web application.

Author: Qianni Wang
Created: 2023-09-24
Last Modified: 2024-04-04
"""

import os
import boto3
import ast

from flask import (
    Flask,
    render_template,
)

# Importing blueprints for different application modules
from profile_page import profile_blueprint
from course_page import courses_blueprint
from forum_page import forum_blueprint
from feedback_page import feedback_blueprint
from pomodoro_page import pomodoro_blueprint
from tasks_page import tasks_blueprint
from app_grid import grid_blueprint

# Attempt to import utility function for S3 operations
try:
    from src.util import (
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        get_df_from_csv_in_s3,
    )

app = Flask(__name__)
# Generate a random secret key for session management
app.secret_key = os.urandom(24)

# Registering application blueprints with their URL prefixes
app.register_blueprint(profile_blueprint, url_prefix="/profile")
app.register_blueprint(courses_blueprint, url_prefix="/courses")
app.register_blueprint(forum_blueprint, url_prefix="/forum")
app.register_blueprint(feedback_blueprint, url_prefix="/feedback")
app.register_blueprint(pomodoro_blueprint, url_prefix="/pomodoro")
app.register_blueprint(tasks_blueprint, url_prefix="/tasks")
app.register_blueprint(grid_blueprint, url_prefix="/grid")

# Loading configs/global variables
app.config.from_pyfile("config.py")

bucket_name = app.config["BUCKET_NAME"]
mock_data_file = app.config["MOCK_DATA_POC_NAME"]
user_data_file = app.config["USER_DATA_NAME"]
topic_data_file = app.config["TOPIC_DATA_NAME"]
comment_data_file = app.config["COMMENT_DATA_NAME"]
model_file_path = app.config["PRIORITY_MODEL_PATH"]
mock_tasks_data_file = app.config["MOCK_DATA_POC_TASKS"]
Transcript_path = app.config["UPLOAD_FOLDER"]
tomato_data_key = app.config["TOMATO_DATA_KEY"]
icon_order_path = app.config["ICON_ORDER_PATH"]

# Setting global variables
app.config["username"] = ""
app.config["userId"] = 1
app.config["courses"] = []
app.config["model"] = None
app.config["current_page"] = "home"
app.config["cGPA"] = "None (Please upload your transcript)"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=app.config["REGION_NAME"],
)

app.config["S3_CLIENT"] = s3


@app.route("/")
def start():
    """
    Route to handle the landing page of the application.
    Fetches user-related data from an S3-stored CSV file to
    demonstrate a proof of concept(PoC). This includes setting
    a default username, user ID, and courses list for the session.
    """
    # Fetch mock data from CSV in S3 for PoC and set initial configuration
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)

    # Set up default session variables for demonstration purposes
    app.config["username"] = df.loc[0, "username"]  # For PoC purpose
    print("username is: ", app.config["username"])
    app.config["userId"] = df.loc[0, "user_id"]  # For PoC purpose

    cs = df.loc[0, "courses"]  # For PoC purpose
    print("courses is :", cs)
    # Parsing it into a Python list
    app.config["courses"] = ast.literal_eval(cs)
    app.config["current_page"] = "home"
    return render_template(
        "index.html",
        username=app.config["username"],
        courses=app.config["courses"],
        current_page=app.config["current_page"],
    )


if __name__ == "__main__":
    app.run(debug=True)

import os
import pandas as pd
import boto3
import ast

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
)

from profile_page import profile_blueprint
from course_page import courses_blueprint
from forum_page import forum_blueprint
from feedback_page import feedback_blueprint
from pomodoro_page import pomodoro_blueprint
from tasks_page import tasks_blueprint

try:
    from src.util import (
        get_df_from_csv_in_s3,
        write_order_csv_to_s3,
    )
except ImportError:
    from .util import (
        get_df_from_csv_in_s3,
        write_order_csv_to_s3,
    )

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.register_blueprint(profile_blueprint, url_prefix="/profile")
app.register_blueprint(courses_blueprint, url_prefix="/courses")
app.register_blueprint(forum_blueprint, url_prefix="/forum")
app.register_blueprint(feedback_blueprint, url_prefix="/feedback")
app.register_blueprint(pomodoro_blueprint, url_prefix="/pomodoro")
app.register_blueprint(tasks_blueprint, url_prefix="/tasks")

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
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)

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


@app.route("/get-order")
def get_order():
    username = app.config["username"]

    df = read_order_csv_from_s3(s3, username, bucket_name, icon_order_path)

    filtered_df = df[df["username"] == username]

    if filtered_df.empty:
        existing_order = [3, 1, 11, 4, 2, 12, 8, 10, 6, 9, 5, 7]
    else:
        existing_order = filtered_df["orders"].iloc[0]

    return jsonify(existing_order)


@app.route("/update-order", methods=["POST"])
def update_order():
    new_orders = request.json
    username = app.config["username"]

    df = get_df_from_csv_in_s3(s3, bucket_name, icon_order_path)

    if username in df["username"].values:
        df.loc[df["username"] == username, "orders"] = str(new_orders)
    else:
        new_row = pd.DataFrame(
            {"username": [username], "orders": [str(new_orders)]}
        )
        df = pd.concat([df, new_row], ignore_index=True)

    write_order_csv_to_s3(s3, icon_order_path, df, bucket_name)

    return jsonify(
        {"status": "success", "message": "Order updated successfully."}
    )


def read_order_csv_from_s3(s3, username, bucket_name, key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        df = pd.read_csv(response["Body"])
        return df
    except s3.exceptions.NoSuchKey:
        default_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        default_df = pd.DataFrame(
            [{"username": username, "orders": default_order}]
        )

        write_order_csv_to_s3(s3, icon_order_path, default_df, bucket_name)

        return default_df
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame(columns=["username", "orders"])


if __name__ == "__main__":
    app.run(debug=True)

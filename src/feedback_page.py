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


# Router to feedback bpx page
@feedback_blueprint.route("/feedback_page", methods=["GET", "POST"])
def feedback_page():
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    current_app.config["current_page"] = "feedback_page"
    # render the feedback box page

    df = read_feedback_csv_from_s3(s3, bucket_name, "feedback.csv")
    viewed = df.loc[(df["username"] == username) & (df["status"] == 1)]
    pending = df.loc[(df["username"] == username) & (df["status"] == 0)]
    viewed_feedback_list = viewed.to_dict("records")
    pending_feedback_list = pending.to_dict("records")

    return render_template(
        "feedback_page.html",
        username=current_app.config["username"],
        current_page=current_page,
        viewed_feedback_list=viewed_feedback_list,
        pending_feedback_list=pending_feedback_list,
    )


def read_feedback_csv_from_s3(s3, bucket_name, key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        df = pd.read_csv(response["Body"])
        df.fillna("", inplace=True)
        return df
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame(columns=["username", "orders"])


# Store the feedback to our s3
@feedback_blueprint.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    if request.method == "POST":
        name = request.form.get("name", default=None)
        email = request.form.get("email", default=None)
        feedback_type = request.form["feedback_type"]
        feedback = request.form["feedback"]

        feedback_id = str(uuid.uuid4())

        feedback_data = {
            "feedback_id": [feedback_id],
            "username": [username],
            "name": [name],
            "email": [email],
            "feedback_type": [feedback_type],
            "feedback": [feedback],
            "status": [0],
            "developer_feedback": [""],
        }
        new_feedback_df = pd.DataFrame(feedback_data)

        feedback_data_path = "feedback.csv"

        try:
            response = s3.get_object(
                Bucket=bucket_name, Key=feedback_data_path
            )
            feedback_df = pd.read_csv(response["Body"])
        except s3.exceptions.NoSuchKey:
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

        feedback_df = pd.concat(
            [feedback_df, new_feedback_df], ignore_index=True
        )
        new_csv_file_path = "poc-data/tmp.csv"
        feedback_df.to_csv(new_csv_file_path, index=False)
        s3.upload_file(
            new_csv_file_path,
            bucket_name,
            feedback_data_path,
        )
        os.remove(new_csv_file_path)

    return redirect(url_for("feedback.feedback_page"))

import os
import io
import PyPDF2
import re
import botocore
import boto3
from flask import Flask, render_template, request, Response, redirect, url_for
import ast
import pandas as pd

from helper import (
    check_syllabus_exists,
    update_csv,
    upload_df_to_s3,
    get_df_from_csv_in_s3,
    load_priority_model_from_s3,
)


app = Flask(__name__)


# Loading configs/global variables
app.config.from_pyfile("config.py")
bucket_name = app.config["BUCKET_NAME"]
mock_data_file = app.config["MOCK_DATA_POC_NAME"]
model_file_path = app.config["PRIORITY_MODEL_PATH"]

# Setting global variables
username = ""
courses = []
emails = ""
model = None

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)


# Set up home page for the website
@app.route("/")
def start():
    global username, courses
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
    username = df.loc[0, "username"]  # For PoC purpose
    courses = df.loc[0, "courses"]  # For PoC purpose
    # Parsing it into a Python list
    courses = ast.literal_eval(courses)

    return render_template(
        "index.html", username=username, courses=courses, current_page="home"
    )


# Predict priority using trained model based on user input
@app.route("/priority_predict", methods=["GET", "POST"])
def prority_predict():
    if request.method == "POST":
        # Load pipeline that has transformed processor and trained model
        pipeline = load_priority_model_from_s3(
            s3, bucket_name, model_file_path
        )
        # Retrieve input data
        form_data = request.form
        input_data = {
            "task_name": [form_data.get("task_name")],
            "school_year": [int(form_data.get("school_year"))],
            "course_name": [form_data.get("course_name")],
            "credit": [int(form_data.get("credit"))],
            "task_mode": [form_data.get("task_mode")],
            "task_type": [form_data.get("task_type")],
            "task_weight_percent": [
                float(form_data.get("task_weight_percent"))
            ],
            "time_required_hours": [
                float(form_data.get("time_required_hours"))
            ],
            "difficulty": [float(form_data.get("difficulty"))],
            "current_progress_percent": [
                float(form_data.get("current_progress_percent"))
            ],
            "time_spent_hours": [float(form_data.get("time_spent_hours"))],
            "days_until_due": [int(form_data.get("days_until_due"))],
        }

        input_df = pd.DataFrame(input_data)

        # Ensure that text columns are in the correct format
        for text_col in ["task_name", "course_name"]:
            input_df[text_col] = input_df[text_col].apply(
                lambda x: [x] if isinstance(x, str) else x
            )

        # Give prediction on the input data
        prediction = pipeline.predict(input_df).tolist()

        priority_mapping = {1: "Low", 2: "Medium", 3: "High"}

        # Replace values in the prediction list
        mapped_prediction = [priority_mapping.get(n, n) for n in prediction]

        pred_prob = pipeline.predict_proba(input_df).tolist()

        model_params = pipeline.get_params()

        # Return prediction
        return render_template(
            "model_prediction_page.html",
            prediction=mapped_prediction,
            prediction_prob=pred_prob,
            model_params=model_params,

        )
    return render_template("model_page.html")


# Router to smodel page
@app.route("/model_page", methods=["GET", "POST"])
def model_page():
    # render the plan page
    return render_template(
        "model_page.html", username=username, current_page="model_page"
    )

# Download a file from s3
@app.route("/download", methods=["GET"])
def download():
    filename = request.args.get("filename")
    if request.method == "GET":
        # s3_file_path would be different for different types of files, for
        # now use filename as default s3 file path
        s3_file_path = filename
        response = s3.get_object(Bucket=bucket_name, Key=s3_file_path)

        file_content = response["Body"].read()
        headers = {"Content-Disposition": f"attachment; filename={filename}"}

        return Response(file_content, headers=headers)


# Change user's name
@app.route("/change_username", methods=["POST"])
def change_username():
    global username
    if request.method == "POST":
        new_username = request.form["newusername"]
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
        df.loc[df["username"] == username, "username"] = new_username
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        username = new_username
    return redirect(url_for("start"))


# Remove an existing course
@app.route("/remove_course", methods=["POST"])
def remove_course():
    if request.method == "POST":
        index = request.form["index"]

        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
        user_courses_serires = df.loc[df["username"] == username, "courses"]
        user_courses_str = user_courses_serires.tolist()[0]
        user_courses = ast.literal_eval(user_courses_str)
        user_courses.pop(int(index))

        list_str = str(user_courses)
        df.loc[df["username"] == username, "courses"] = list_str

        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
    return redirect(url_for("start"))


# Add a new course
@app.route("/add_course", methods=["POST"])
def add_course():
    global username
    if request.method == "POST":
        new_course = request.form["newcourse"]
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)

        user_courses_serires = df.loc[df["username"] == username, "courses"]
        user_courses_str = user_courses_serires.tolist()[0]
        user_courses = ast.literal_eval(user_courses_str)

        user_courses.append(new_course)
        list_str = str(user_courses)
        df.loc[df["username"] == username, "courses"] = list_str

        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
    return redirect(url_for("start"))


# Router to course detailed page
@app.route("/course_page", methods=["GET", "POST"])
def course_page():
    # render the course page, display the course content(name)
    return render_template(
        "course_page.html",
        username=username,
        courses=courses,
        current_page="course_page",
    )


# Router to study plan detailed page
@app.route("/plan_page", methods=["GET", "POST"])
def plan_page():
    # render the plan page
    return render_template(
        "plan_page.html", username=username, current_page="plan_page"
    )


# Router to user profile pageile
@app.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    # render the profile page, showing username on pege
    return render_template(
        "profile_page.html", username=username, current_page="profile_page"
    )


@app.route("/course_detail_page/<course_id>")
def course_detail(course_id):
    message = request.args.get("message", "")
    bk = bucket_name
    syllabus_exists, pdf_name = check_syllabus_exists(course_id, s3, bk)

    if syllabus_exists:
        email_list = extract_emails_from_pdf(pdf_name)
    else:
        email_list = []

    return render_template(
        "course_detail_page.html",
        course_id=course_id,
        course=course_id,
        username=username,
        email_list=email_list,
        message=message,
    )


# input:pdf file
# output: a list of string emails
# extract all the email in the input pdf
@app.route("/get_emails", methods=["GET"])
def extract_emails_from_pdf(filename):
    if request.method == "GET":
        response = s3.get_object(Bucket=bucket_name, Key=filename)
        pdf_file = response["Body"].read()
        pdf_file_obj = io.BytesIO(pdf_file)

        pdf_reader = PyPDF2.PdfReader(pdf_file_obj)
        text = ""

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        emails = re.findall(email_pattern, text)

        return emails


@app.route("/upload/<course_id>", methods=["POST"])
def upload_file(course_id):
    print("course id", course_id)
    if (
        "file" not in request.files
        or not request.files["file"]
        or request.files["file"].filename == ""
    ):
        print("checked")
        return redirect(
            url_for(
                "course_detail",
                course_id=course_id,
                message="No file selected",
                username=username,
            )
        )

    file = request.files["file"]
    new_filename = f"{course_id}-syllabus.pdf"
    file.filename = new_filename
    print("file:", file.filename)

    try:
        print("uploading")

        s3.upload_fileobj(
            file, bucket_name, file.filename, ExtraArgs={"ACL": "private"}
        )
        update_csv(course_id, file.filename)
        print("returning")
        return redirect(
            url_for(
                "course_detail",
                course_id=course_id,
                message="File uploaded successfully!",
                username=username,
            )
        )
    except botocore.exceptions.NoCredentialsError:
        print("error")
        return redirect(
            url_for(
                "course_detail",
                course_id=course_id,
                message="AWS authentication failed. Check your AWS keys.",
                username=username,
            )
        )


if __name__ == "__main__":
    app.run(debug=True)

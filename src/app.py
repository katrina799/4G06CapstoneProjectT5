import os
import io
import PyPDF2
import re
import botocore
import boto3
from flask import Flask, render_template, request, Response, redirect, url_for
import ast

from helper import (
    check_syllabus_exists,
    update_csv,
    upload_df_to_s3,
    get_df_from_csv_in_s3,
  load_priority_model_from_s3,
)

from task-prioirty-training-pipeline.training_pipeline import pipeline

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
def predict():
    # Load model
    model = load_priority_model_from_s3(s3, bucket_name, model_file_path)

    # Get data
import os
import logging
import argparse
from joblib import dump

import boto3
import pandas as pd
from sklearn.base import TransformerMixin
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder

# from sklearn.ensemble import RandomForestClassifier
# from sklearn.ensemble import GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier

# from sklearn.linear_model import LogisticRegression
# from sklearn.tree import DecisionTreeClassifier

from src import config

# Set up logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Set up argument parser
parser = argparse.ArgumentParser(description="Process the file path.")

parser.add_argument("data_file_path", type=str, help="Data file path")

args = parser.parse_args()


class SqueezeTransformer(TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X.squeeze()


# Read the data
data = pd.read_csv(args.data_file_path)

# Convert column with limited number, discrete set of values to category
# datatype.
category_data_cols = [
    "school_year",
    "task_mode",
    "task_type",
    "difficulty",
    "priority_level",
]
for col in category_data_cols:
    data[col] = data[col].astype("category")

# Converting date columns to datetime format
date_columns = ["due_date", "current_date_(today)"]
for col in date_columns:
    data[col] = pd.to_datetime(data[col], errors="coerce", format="%Y/%m/%d")

# Feature Selection - select relevant features for priority classification
feature_selected_columns = [
    "task_name",
    "school_year",
    "course_name",
    "credit",
    "task_mode",
    "task_type",
    "task_weight_percent",
    "time_required_hours",
    "difficulty",
    "current_progress_percent",
    "time_spent_hours",
    "days_until_due",
]
X = data[feature_selected_columns]
replacement_dict = {2: 1, 3: 2, 4: 2, 5: 3}
data["priority_level"] = data["priority_level"].replace(replacement_dict)
y = data["priority_level"]

split_params = {"test_size": 0.2, "random_state": 0}
X_train, X_test, y_train, y_test = train_test_split(X, y, **split_params)
X.to_csv("poc_test_input.csv")

# Numerical feature pipeline
numerical_cols = [
    "school_year",
    "credit",
    "task_weight_percent",
    "time_required_hours",
    "difficulty",
    "current_progress_percent",
    "time_spent_hours",
    "days_until_due",
]
numerical_feature_pipeline = Pipeline(
    [
        ("scaler", StandardScaler()),
    ]
)

# Categorical feature pipeline
category_cols = ["task_mode", "task_type"]
categorical_feature_pipeline = Pipeline(
    steps=[("onehot", OneHotEncoder(handle_unknown="ignore"))]
)

# Text feature pipeline
text_cols = ["task_name", "course_name"]
text_feature_pipeline = Pipeline(
    steps=[
        (
            "squeeze",
            SqueezeTransformer(),
        ),  # Custom transformer to squeeze the DataFrame column
        ("td-idf", TfidfVectorizer()),
    ]
)

# Preprocessing step: combining feature pipelines
preprocessor = ColumnTransformer(
    transformers=[
        ("numerical", numerical_feature_pipeline, numerical_cols),
        ("categorical", categorical_feature_pipeline, category_cols),
        ("text1", text_feature_pipeline, text_cols[0]),
        ("text2", text_feature_pipeline, text_cols[1]),
    ]
)

# This can be changed to different model
classfier = MLPClassifier(
    solver="lbfgs", alpha=1e-5, hidden_layer_sizes=(12,), random_state=1
)
# classfier = GradientBoostingClassifier(
#     n_estimators=150, learning_rate=0.1, max_depth=5, random_state=42
# )
# DecisionTreeClassifier()
# LogisticRegression(max_iter=1000)
# GradientBoostingClassifier(n_estimators=100, learning_rate=0.1,
#  max_depth=3, random_state=42)
# RandomForestClassifier()


# Create the full pipeline
pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("cf", classfier)])

pipeline.fit(X_train, y_train)

y_pred_train = pipeline.predict(X_train)
y_pred_test = pipeline.predict(X_test)

train_accuracy = pipeline.score(X_train, y_train)
test_accuracy = pipeline.score(X_test, y_test)

logging.info(f"Training set score: {train_accuracy}")
logging.info(f"Testing set score: {test_accuracy}")

model_filepath = config.PRIORITY_MODEL_FILE_PATH
dump(pipeline, model_filepath)
logging.info(f"Model saved as {model_filepath}")


s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)
s3_file_path = f"model/{config.PRIORITY_MODEL_FILE_NAME}"
s3.upload_file(model_filepath, config.BUCKET_NAME, s3_file_path)
logging.info(f"Model uploaded to S3 as {s3_file_path}")


    # Transform data


    # Make prediction
    prediction = model.predict([features])

    # Return prediction
    return jsonify({"prediction": prediction.tolist()})


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

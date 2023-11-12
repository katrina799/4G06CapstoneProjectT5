import os

import boto3
from flask import Flask, render_template, request, Response, redirect, url_for
import ast

from helper import get_df_from_csv_in_s3, upload_df_to_s3


app = Flask(__name__)

# Loading configs/global variables
app.config.from_pyfile("config.py")
bucket_name = app.config["BUCKET_NAME"]
mock_data_file = app.config["MOCK_DATA_POC_NAME"]

# Setting global variables
username = ""
courses = []

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

    return render_template("index.html", username=username, courses=courses)


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
    return render_template("course_page.html", courses=courses)


# Router to study plan detailed page
@app.route("/plan_page", methods=["GET", "POST"])
def plan_page():
    # render the plan page
    return render_template("plan_page.html")


# Router to user profile page
@app.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    # render the profile page, showing username on pege
    return render_template("profile_page.html", username=username)


if __name__ == "__main__":
    app.run(debug=True)

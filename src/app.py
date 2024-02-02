from datetime import datetime
from io import StringIO
import os
import pandas as pd
import botocore
import boto3
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    Response,
    redirect,
    url_for,
)
import ast

try:
    from helper import (
        check_syllabus_exists,
        update_csv,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
        extract_emails_from_pdf,
        load_priority_model_from_s3,
        extract_instructor_name_from_pdf,
    )
except ImportError:
    from .helper import (
        check_syllabus_exists,
        update_csv,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
        extract_emails_from_pdf,
        load_priority_model_from_s3,
        extract_instructor_name_from_pdf,
    )


app = Flask(__name__)


# Loading configs/global variables
app.config.from_pyfile("config.py")
bucket_name = app.config["BUCKET_NAME"]
mock_data_file = app.config["MOCK_DATA_POC_NAME"]
model_file_path = app.config["PRIORITY_MODEL_PATH"]
mock_tasks_data_file = app.config["MOCK_DATA_POC_TASKS"]

# Setting global variables
username = ""
courses = []
model = None
current_page = "home"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)


# Set up home page for the website
@app.route("/")
def start():
    global username, courses, current_page, tasks
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
    username = df.loc[0, "username"]  # For PoC purpose
    courses = df.loc[0, "courses"]  # For PoC purpose
    # Parsing it into a Python list
    courses = ast.literal_eval(courses)
    current_page = "home"
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
    # Convert the tasks DataFrame to a list of dictionaries
    tasks = (
        tasks_df.groupby("status")
        .apply(lambda x: x.drop("status", axis=1).to_dict(orient="records"))
        .to_dict()
    )
    c_p = current_page
    return render_template(
        "index.html",
        username=username,
        courses=courses,
        current_page=c_p,
        tasks=tasks,
    )


# Predict priority using trained model based on user input
@app.route("/priority_predict", methods=["GET", "POST"])
def prority_predict():
    if request.method == "POST":
        # Load pipeline that has transformed processor and trained model
        m_f_p = model_file_path
        pipeline = load_priority_model_from_s3(s3, bucket_name, m_f_p)
        # Retrieve input data
        form_data = request.form
        t_w_p = "task_weight_percent"
        t_r_h = "time_required_hours"
        input_data = {
            "task_name": [form_data.get("task_name")],
            "school_year": [int(form_data.get("school_year"))],
            "course_name": [form_data.get("course_name")],
            "credit": [int(form_data.get("credit"))],
            "task_mode": [form_data.get("task_mode")],
            "task_type": [form_data.get("task_type")],
            t_w_p: [float(form_data.get(t_w_p))],
            t_r_h: [float(form_data.get(t_r_h))],
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


# Router to model page
@app.route("/model_page", methods=["GET", "POST"])
def model_page():
    global current_page
    current_page = "model_page"
    # render the plan page
    return render_template(
        "model_page.html", username=username, current_page=current_page
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
    global username, current_page, courses
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
        courses = user_courses
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=courses,
                current_page="course_page",
            )
    return redirect(url_for("start"))


# Add a new course
@app.route("/add_course", methods=["POST"])
def add_course():
    global username, current_page, courses
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
        courses = user_courses
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=courses,
                current_page="course_page",
            )
    return redirect(url_for("start"))


# Router to course detailed page
@app.route("/course_page", methods=["GET", "POST"])
def course_page():
    global courses, current_page
    current_page = "course_page"
    # Render the course page, display the course content(name)
    return render_template(
        "course_page.html",
        username=username,
        courses=courses,
        current_page=current_page,
    )


# Router to study plan detailed page
@app.route("/plan_page", methods=["GET", "POST"])
def plan_page():
    global current_page
    current_page = "plan_page"
    # Render the plan page
    return render_template(
        "plan_page.html", username=username, current_page=current_page
    )


# Router to user profile pageile
@app.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    global current_page
    current_page = "profile_page"
    # Render the profile page, showing username on pege
    return render_template(
        "profile_page.html", username=username, current_page=current_page
    )


# Router to course detail page
@app.route("/course_detail_page/<course_id>")
def course_detail(course_id):
    message = request.args.get("message", "")
    bk = bucket_name
    syllabus_exists, pdf_name = check_syllabus_exists(course_id, s3, bk)

    if syllabus_exists:
        email_list = extract_emails_from_pdf(
            pdf_name,
            bucket_name,
            s3,
        )
        instructor_name = extract_instructor_name_from_pdf(
            pdf_name,
            bucket_name,
            s3,
        )
    else:
        email_list = []
        instructor_name = ""

    return render_template(
        "course_detail_page.html",
        course_id=course_id,
        course=course_id,
        username=username,
        email_list=email_list,
        instructor_name=instructor_name,
        message=message,
    )


# Upload the a pdf syllabus file to S3 and extract the course info in the file
@app.route("/upload/<course_id>", methods=["POST"])
def upload_file(course_id):
    if (
        "file" not in request.files
        or not request.files["file"]
        or request.files["file"].filename == ""
    ):
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

    try:
        s3.upload_fileobj(
            file, bucket_name, file.filename, ExtraArgs={"ACL": "private"}
        )

        bk = bucket_name
        syllabus_exists, pdf_name = check_syllabus_exists(course_id, s3, bk)
        if syllabus_exists:
            # Extract email list
            email_list = extract_emails_from_pdf(
                pdf_name,
                bucket_name,
                s3,
            )
            # Extract instructor name
            instructor_name = extract_instructor_name_from_pdf(
                pdf_name,
                bucket_name,
                s3,
            )
        else:
            email_list = []
            instructor_name = ""

        update_csv(course_id, file.filename, email_list, instructor_name)
        return redirect(
            url_for(
                "course_detail",
                course_id=course_id,
                message="File uploaded successfully!",
                username=username,
            )
        )
    except botocore.exceptions.NoCredentialsError:
        return redirect(
            url_for(
                "course_detail",
                course_id=course_id,
                message="AWS authentication failed. Check your AWS keys.",
                username=username,
            )
        )


# update tasks status after dragging
@app.route("/update_task_status", methods=["POST"])
def update_task_status():
    data = request.get_json()

    try:
        task_id = int(data["id"])
    except ValueError:
        return jsonify({"message": "Invalid task ID format"}), 400
    new_status = data["status"]

    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
    if task_id in tasks_df["id"].tolist():
        tasks_df.loc[tasks_df["id"] == task_id, "status"] = new_status
        csv_buffer = StringIO()
        tasks_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=mock_tasks_data_file,
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )
        return jsonify({"message": "Task status updated successfully"})
    else:
        return jsonify({"message": "Task not found"}), 404


def add_task_todo(course_name, task_name, due_date, weight, est_hours):
    if due_date:
        due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
        priority = (
            "high" if (due_date_obj - datetime.now()).days < 7 else "low"
        )
    else:
        due_date = "0000-00-00"
        priority = "unknown"

    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    new_task = {
        "id": tasks_df["id"].max() + 1,
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


@app.route("/add_task", methods=["POST"])
def add_task():
    course_name = request.form.get("course_name")
    task_name = request.form.get("task_name")
    due_date = request.form.get("due_date")
    weight = request.form.get("weight", 0)
    est_hours = request.form.get("est_hours", 0)

    add_task_todo(course_name, task_name, due_date, weight, est_hours)
    return redirect(url_for("start"))


@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    try:
        tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
        if task_id in tasks_df["id"].values:
            tasks_df = tasks_df[tasks_df["id"] != task_id]
            csv_buffer = StringIO()
            tasks_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            s3.put_object(
                Bucket=bucket_name,
                Key=mock_tasks_data_file,
                Body=csv_buffer.getvalue(),
                ContentType="text/csv",
            )
            return jsonify({"message": "Task deleted successfully"}), 200
        else:
            return jsonify({"message": "Task not found"}), 404
    except Exception as e:
        print(f"An error occurred: {e}")
        return (
            jsonify({"message": "An error occurred while deleting the task"}),
            500,
        )


@app.route("/edit_task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    existing_task = tasks_df.loc[tasks_df["id"] == task_id].iloc[0]
    new_course_name = request.form.get("course_name")
    new_task_name = request.form.get("task_name")
    new_due_date_str = request.form.get("due_date")
    new_weight = request.form.get("weight")
    new_est_hours = request.form.get("est_hours")

    if new_due_date_str:
        new_due_date = datetime.strptime(new_due_date_str, "%Y-%m-%d").date()
        days_until_due = (new_due_date - datetime.now().date()).days
        new_priority = "high" if days_until_due < 7 else "low"
        formatted_due_date = new_due_date.strftime("%Y-%m-%d")
    else:
        formatted_due_date = existing_task["due_date"]
        new_priority = existing_task["priority"]

    if task_id not in tasks_df["id"].values:
        return jsonify({"message": "Task not found"}), 404

    try:
        task_index = tasks_df.index[tasks_df["id"] == task_id].tolist()[0]
        tasks_df.at[task_index, "course"] = new_course_name
        tasks_df.at[task_index, "title"] = new_task_name
        tasks_df.at[task_index, "due_date"] = formatted_due_date
        tasks_df.at[task_index, "weight"] = new_weight
        tasks_df.at[task_index, "est_time"] = new_est_hours
        tasks_df.at[task_index, "priority"] = new_priority

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
        print(f"An error occurred when updating task: {e}")
        return (
            jsonify({"message": "An error occurred while updating the task"}),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True)

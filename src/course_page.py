from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    jsonify,
    url_for,
)
import botocore
import ast
import pandas as pd
from io import StringIO

try:
    from config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO
except ImportError:
    from .config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO

try:
    from src.util import (
        check_syllabus_exists,
        update_csv,
        upload_df_to_s3,
        add_task_todo,
        get_df_from_csv_in_s3,
        update_csv_after_deletion,
        extract_text_from_pdf,
        extract_course_work_details,
        process_course_work_with_openai,
        analyze_course_content,
        convert_to_list_of_dicts,
        write_course_work_to_csv,
    )
except ImportError:
    from .util import (
        check_syllabus_exists,
        update_csv,
        add_task_todo,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
        update_csv_after_deletion,
        extract_text_from_pdf,
        extract_course_work_details,
        process_course_work_with_openai,
        analyze_course_content,
        convert_to_list_of_dicts,
        write_course_work_to_csv,
    )
courses_blueprint = Blueprint("courses", __name__)


# Router to course page
@courses_blueprint.route("/course_page", methods=["GET", "POST"])
def course_page():
    current_app.config["current_page"] = "course_page"
    # Render the course page, display the course content(name)
    return render_template(
        "course_page.html",
        username=current_app.config["username"],
        courses=current_app.config["courses"],
        current_page=current_app.config["current_page"],
    )


# Remove an existing course
@courses_blueprint.route("/remove_course", methods=["POST"])
def remove_course():
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    bucket_name = current_app.config["BUCKET_NAME"]
    mock_data_file = current_app.config["MOCK_DATA_POC_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    if request.method == "POST":
        index = request.form["index"]
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
        user_courses_series = df.loc[df["username"] == username, "courses"]
        user_courses_str = user_courses_series.tolist()[0]
        user_courses = ast.literal_eval(user_courses_str)

        course_id = user_courses.pop(int(index))

        syllabus_exists, pdf_name = check_syllabus_exists(
            course_id, s3, bucket_name
        )
        if syllabus_exists:
            s3.delete_object(Bucket=bucket_name, Key=pdf_name)
            update_csv_after_deletion(course_id)
        delete_task_by_course(course_id)

        list_str = str(user_courses)
        df.loc[df["username"] == username, "courses"] = list_str
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        current_app.config["courses"] = user_courses
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=current_app.config["courses"],
                current_page="course_page",
            )
    return redirect(url_for("start"))


def delete_task_by_course(course_name):
    bucket_name = current_app.config["BUCKET_NAME"]
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    s3 = current_app.config["S3_CLIENT"]
    try:
        tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
        if course_name in tasks_df["course"].values:
            tasks_df = tasks_df[tasks_df["course"] != course_name]
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


# Add a new course
@courses_blueprint.route("/add_course", methods=["POST"])
def add_course():
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    bucket_name = current_app.config["BUCKET_NAME"]
    mock_data_file = current_app.config["MOCK_DATA_POC_NAME"]
    s3 = current_app.config["S3_CLIENT"]
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
        current_app.config["courses"] = user_courses
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=current_app.config["courses"],
                current_page="course_page",
            )
    return redirect(url_for("start"))


# Router to course detail page
@courses_blueprint.route("/course_detail_page/<course_id>")
def course_detail(course_id):
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    message = request.args.get("message", "")
    syllabus_exists, pdf_name = check_syllabus_exists(
        course_id, s3, bucket_name
    )

    course_info_df = pd.read_csv(MOCK_COURSE_INFO_CSV)
    course_info_row = course_info_df[course_info_df["course"] == course_id]

    course_works_df = pd.read_csv(
        current_app.config["COURSE_WORK_EXTRACTED_INFO"]
    )
    course_works = course_works_df[course_works_df["course"] == course_id]

    for index, row in course_works.iterrows():
        course_name = row["course"]
        task_name = row["course_work"]
        due_date = row["due_date"]
        weight = row["score_distribution"]
        est_hours = 3
        add_task_todo(
            course_name,
            task_name,
            due_date,
            str(weight),
            est_hours,
            s3,
            bucket_name,
            mock_tasks_data_file,
        )

    return render_template(
        "course_detail_page.html",
        course_id=course_id,
        course=course_id,
        course_info=(
            course_info_row.to_dict(orient="records")[0]
            if not course_info_row.empty
            else None
        ),
        course_works=(
            course_works.to_dict(orient="records")
            if not course_works.empty
            else []
        ),
        message=message,
        username=username,
    )


@courses_blueprint.route("/upload/<course_id>", methods=["POST"])
def upload_file(course_id):
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    if (
        "file" not in request.files
        or not request.files["file"]
        or request.files["file"].filename == ""
    ):
        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                message="No file selected",
                username=username,
            )
        )

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                message="File format is not PDF. Please upload a PDF file.",
            )
        )
    new_filename = f"{course_id}-syllabus.pdf"
    file.filename = new_filename

    try:
        s3.upload_fileobj(
            file, bucket_name, new_filename, ExtraArgs={"ACL": "private"}
        )
        syllabus_exists, pdf_name = check_syllabus_exists(
            course_id, s3, bucket_name
        )
        if syllabus_exists:
            pdf_text = extract_text_from_pdf(pdf_name, bucket_name, s3)
            course_work_details = extract_course_work_details(pdf_text)
            # print(
            #     "!!!!!!!!!course_work_details!!!!!!!!!!: ",
            # course_work_details
            # )
            course_info = analyze_course_content(pdf_text)
            course_work_info = process_course_work_with_openai(
                course_work_details
            )
            # print("!!!!!!!!!course_work_info!!!!!!!!!!: ", course_work_info)
        else:
            course_info = ""
            course_work_info = ""

        update_csv(course_id, file.filename, course_info)
        course_work_list = convert_to_list_of_dicts(course_work_info)
        print("!!!!!!!!!course_work_list!!!!!!!!!!: ", course_work_list)
        write_course_work_to_csv(course_work_list, course_id)

        course_info_df = pd.read_csv(MOCK_COURSE_INFO_CSV)
        course_info_row = course_info_df[course_info_df["course"] == course_id]

        course_works_df = pd.read_csv(COURSE_WORK_EXTRACTED_INFO)
        course_works = course_works_df[course_works_df["course"] == course_id]

        for index, row in course_works.iterrows():
            course_name = row["course"]
            task_name = row["course_work"]
            due_date = row["due_date"]
            weight = row["score_distribution"]
            est_hours = 3
            add_task_todo(
                course_name,
                task_name,
                due_date,
                str(weight),
                est_hours,
                s3,
                bucket_name,
                current_app.config["MOCK_DATA_POC_TASKS"],
            )

        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                course_info=(
                    course_info_row.to_dict(orient="records")[0]
                    if not course_info_row.empty
                    else None
                ),
                course_works=(
                    course_works.to_dict(orient="records")
                    if not course_works.empty
                    else []
                ),
                message="File uploaded successfully!",
                username=username,
            )
        )
    except botocore.exceptions.NoCredentialsError:
        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                message="AWS authentication failed. Check your AWS keys.",
                username=username,
            )
        )

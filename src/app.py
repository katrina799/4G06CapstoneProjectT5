from datetime import datetime, timedelta, timezone
from io import StringIO
import os
import pandas as pd
import botocore
import boto3
import uuid
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    Response,
    redirect,
    url_for,
    abort,
)
import ast

try:
    from helper import (
        check_syllabus_exists,
        update_csv,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
        read_order_csv_from_s3,
        write_order_csv_to_s3,
        update_csv_after_deletion,
        extract_text_from_pdf,
        extract_course_work_details,
        process_course_work_with_openai,
        analyze_course_content,
        convert_to_list_of_dicts,
        write_course_work_to_csv,
        process_transcript_pdf,
    )
except ImportError:
    from .helper import (
        check_syllabus_exists,
        update_csv,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
        read_order_csv_from_s3,
        write_order_csv_to_s3,
        update_csv_after_deletion,
        extract_text_from_pdf,
        extract_course_work_details,
        process_course_work_with_openai,
        analyze_course_content,
        convert_to_list_of_dicts,
        write_course_work_to_csv,
        process_transcript_pdf,
    )


app = Flask(__name__)
app.secret_key = os.urandom(24)

try:
    from config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO
except ImportError:
    from .config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO

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


icon_order_path = app.config["ICON_ORDER_PATH"]
# Setting global variables
username = ""
userId = 1
courses = []
model = None
current_page = "home"
cGPA = "None (Please upload your transcript)"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

tomato_data_key = "weekly_tomato_data.csv"


@app.route("/")
def start():
    global username, userId, courses, current_page, tasks
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
    username = df.loc[0, "username"]  # For PoC purpose
    userId = df.loc[0, "user_id"]  # For PoC purpose
    print(userId)
    courses = df.loc[0, "courses"]  # For PoC purpose
    # Parsing it into a Python list
    courses = ast.literal_eval(courses)
    current_page = "home"
    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

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
        ["title", "course", "due_date"]
    ].to_dict(orient="records")

    c_p = current_page
    return render_template(
        "index.html",
        username=username,
        courses=courses,
        current_page=c_p,
        tasks=tasks,
        tasks_for_calendar=tasks_for_calendar,
    )


@app.route("/get-order")
def get_order():
    df = read_order_csv_from_s3(s3, username, bucket_name, icon_order_path)
    existing_order = df.loc[df["username"] == username, "orders"].iloc[0]
    return jsonify(existing_order)


@app.route("/update-order", methods=["POST"])
def update_order():
    new_orders = request.json

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


# Router to feedback bpx page
@app.route("/feedback_page", methods=["GET", "POST"])
def feedback_page():
    global current_page
    current_page = "feedback_page"
    # render the feedback box page
    return render_template(
        "feedback_page.html", username=username, current_page=current_page
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


# Router to course page
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


# Router to user profile pageile
@app.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    global current_page
    current_page = "profile_page"
    # Render the profile page, showing username on pege
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )


# Router to course detail page
@app.route("/course_detail_page/<course_id>")
def course_detail(course_id):
    message = request.args.get("message", "")
    syllabus_exists, pdf_name = check_syllabus_exists(
        course_id, s3, bucket_name
    )

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
        add_task_todo(course_name, task_name, due_date, str(weight), est_hours)

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
                course_name, task_name, due_date, str(weight), est_hours
            )

        return redirect(
            url_for(
                "course_detail",
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
                "course_detail",
                course_id=course_id,
                message="AWS authentication failed. Check your AWS keys.",
                username=username,
            )
        )


@app.route("/forum_page", methods=["GET"])
def forum_page():
    global current_page
    current_page = "forum_page"
    try:
        # Fetch topics, comments, and users data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)
        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)
        users_df = get_df_from_csv_in_s3(s3, bucket_name, user_data_file)

        # Ensure 'userId' in topics_df is the same type as 'userId' in users_df
        topics_df["userId"] = topics_df["userId"].astype(str)
        users_df["userId"] = users_df["userId"].astype(str)

        # Aggregate comments by topicId to count them
        comments_count = (
            comments_df.groupby("topicId")
            .size()
            .reset_index(name="comment_count")
        )

        # Merge topics with comments count based on topic ID
        topics_with_comments = pd.merge(
            topics_df,
            comments_count,
            how="left",
            left_on="id",
            right_on="topicId",
        ).fillna(0)

        # Merge topics with user data to get usernames
        topics_with_usernames = pd.merge(
            topics_with_comments,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )

        # Prepare the topics list as expected by the template
        topics = [
            (row.to_dict(), row["username"], int(row["comment_count"]))
            for _, row in topics_with_usernames.iterrows()
        ]

    except Exception as e:
        print(f"An error occurred while fetching forum data: {e}")
        topics = []

    return render_template(
        "forum_page.html",
        topics=topics,
        current_page=current_page,
        username=username,
    )


@app.route("/add_topic", methods=["GET", "POST"])
def add_topic():
    global current_page, username, userId, bucket_name
    current_page = "add_topic"

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        # Fetch current topics DataFrame from S3
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)
        if not topics_df.empty:
            topics_df["id"] = topics_df["id"].astype(
                int
            )  # Ensure 'id' is an integer
            new_id = topics_df["id"].max() + 1
        else:
            new_id = 1  # Start with 1 if there are no topics

        new_topic = pd.DataFrame(
            {
                "id": [new_id],  # Ensure 'id' is a string to match types.
                "title": [title],
                "description": [description],
                "userId": [
                    userId
                ],  # Convert userId to a list to match DataFrame structure.
            }
        )

        topics_df["id"] = topics_df["id"].astype(str)
        print("topics_df")
        print(topics_df)

        # Use pd.concat for appending the new record
        updated_topics_df = pd.concat(
            [topics_df, new_topic], ignore_index=True
        )
        print("updated_topics_df")
        print(updated_topics_df)

        # Upload the updated DataFrame back to S3
        csv_buffer = StringIO()
        updated_topics_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=topic_data_file,
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )

        return redirect(url_for("forum_page"))
    else:
        return render_template(
            "add_topic_page.html", current_page=current_page, username=username
        )


@app.route("/forum/topic/<topic_id>", methods=["GET", "POST"])
def topic(topic_id):
    global current_page
    current_page = "forum_topic"  # Set the current page context

    if request.method == "POST":
        # Handle new comment submission
        comment_text = request.form.get("comment")
        # Fetch current comments DataFrame from S3
        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)
        if not comments_df.empty:
            comments_df["id"] = comments_df["id"].astype(
                int
            )  # Ensure 'id' is an integer
            new_comment_id = comments_df["id"].max() + 1
        else:
            new_comment_id = 1  # Start with 1 if there are no comments yet

        new_comment = pd.DataFrame(
            {
                "id": [new_comment_id],
                "text": [comment_text],
                "topicId": [
                    int(topic_id)
                ],  # Ensure the topicId is correctly typed as int
                "userId": [userId],
            }
        )

        # Append the new comment to the DataFrame and upload to S3
        updated_comments_df = pd.concat(
            [comments_df, new_comment], ignore_index=True
        )
        upload_df_to_s3(
            updated_comments_df, s3, bucket_name, comment_data_file
        )

        # Redirect to the same topic page to display the new comment
        return redirect(url_for("topic", topic_id=topic_id))

    # Initialize
    topic_dict = {}
    comments_with_usernames = []

    try:
        # Fetch all necessary data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, "topic_data.csv")
        comments_df = get_df_from_csv_in_s3(
            s3, bucket_name, "comment_data.csv"
        )
        users_df = get_df_from_csv_in_s3(s3, bucket_name, "user_data.csv")

        # Fetch topic data
        topic_data = topics_df[topics_df["id"].astype(str) == str(topic_id)]
        if topic_data.empty:
            abort(404)  # Topic not found
        topic_dict = topic_data.iloc[0].to_dict()

        author_id = topic_dict["userId"]
        author_username = users_df[
            users_df["userId"].astype(str) == str(author_id)
        ].iloc[0]["username"]

        # Prepare comments with usernames
        comments_df = comments_df[
            comments_df["topicId"].astype(str) == str(topic_id)
        ]
        comments_with_users = pd.merge(
            comments_df,
            users_df,
            left_on="userId",
            right_on="userId",
            how="left",
        )

        comments_with_usernames = [
            ({"text": row["text"]}, row["username"])
            for _, row in comments_with_users.iterrows()
        ]

    except Exception as e:
        print(f"An error occurred: {e}")
        abort(500)

    return render_template(
        "forum_topic_page.html",
        topic=topic_dict,
        comments=comments_with_usernames,
        current_page=current_page,
        username=username,  # Assuming username is correctly set elsewhere
        author_username=author_username,
    )


@app.route("/search_forum")
def search():
    global current_page
    current_page = "forum_page"
    query = request.args.get("query", "").strip()

    try:
        # Fetch topics and comments data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)
        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)
        users_df = get_df_from_csv_in_s3(s3, bucket_name, user_data_file)

        # Filter topics and comments based on the search query
        matching_topics = topics_df[
            topics_df["title"].str.contains(query, case=False, na=False)
            | topics_df["description"].str.contains(
                query, case=False, na=False
            )
        ]
        matching_comments = comments_df[
            comments_df["text"].str.contains(query, case=False, na=False)
        ]

        # Join matching topics and comments with user data to include usernames
        matching_topics_with_usernames = pd.merge(
            matching_topics,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )
        matching_comments_with_usernames = pd.merge(
            matching_comments,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )

        # Prepare results to pass to the template
        topics_results = matching_topics_with_usernames.to_dict(
            orient="records"
        )
        comments_results = [
            {
                "text": row["text"],
                "topicId": row["topicId"],
                "username": row["username"],
            }
            for _, row in matching_comments_with_usernames.iterrows()
        ]

        results = {"topics": topics_results, "comments": comments_results}
    except Exception as e:
        print(f"An error occurred while searching: {e}")
        results = {"topics": [], "comments": []}

    return render_template(
        "search_forum_results.html", results=results, query=query
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
    # 检查 due_date 是否是有效的日期格式
    try:
        # 尝试将 due_date 解析为 datetime 对象
        if due_date not in ["", "Not Found", "0"]:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
            days_until_due = (due_date_obj - datetime.now()).days
            # 根据截止日期距今天数设置任务优先级
            priority = "high" if days_until_due < 7 else "low"
        else:
            # 对于无效的 due_date，将其设置为特殊值，并标记优先级为 "unknown"
            due_date = "0000-00-00"
            priority = "unknown"
    except ValueError:
        # 如果 due_date 格式不正确，也将其设置为特殊值，并标记优先级为 "unknown"
        due_date = "0000-00-00"
        priority = "unknown"

    tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)

    new_task = {
        "id": tasks_df["id"].max() + 1 if not tasks_df.empty else 1,
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


def delete_task_by_course(course_name):
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


# Store the feedback to our s3
@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if request.method == "POST":
        name = request.form.get("name", default=None)
        email = request.form.get("email", default=None)
        feedback_type = request.form["feedback_type"]
        feedback = request.form["feedback"]

        feedback_id = str(uuid.uuid4())

        feedback_data = {
            "feedback_id": [feedback_id],
            "name": [name],
            "email": [email],
            "feedback_type": [feedback_type],
            "feedback": [feedback],
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
                    "name",
                    "email",
                    "feedback_type",
                    "feedback",
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

    return redirect(url_for("feedback_page"))


# Router to pomodoro page
@app.route("/pomodoro_page", methods=["GET", "POST"])
def pomodoro_page():
    est_time = request.args.get("est_time", default=None)
    global current_page
    current_page = "pomodoro_page"
    # Render the profile page, showing username on pege
    return render_template(
        "pomodoro_page.html",
        username=username,
        current_page=current_page,
        est_time=est_time,
    )


@app.route("/upload_transcript", methods=["GET", "POST"])
def upload_transcript():
    if request.method == "POST":
        file = request.files["transcript"]
        os.makedirs(Transcript_path, exist_ok=True)
        if file:
            filename = file.filename
            file.save(os.path.join(Transcript_path, filename))
            global cGPA
            cGPA = process_transcript_pdf(
                os.path.join(Transcript_path, filename)
            )
            return render_template(
                "profile_page.html",
                username=username,
                current_page=current_page,
                cGPA=str(cGPA),
            )

    # If it's a GET request, just render the upload form
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )


def write_df_to_csv_in_s3(client, bucket, key, dataframe):
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, index=False)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_buffer.getvalue(),
        ContentType="text/csv",
    )


# Update Tomato count for weekly achievements form
@app.route("/update_tomato/<day>", methods=["POST"])
def update_tomato(day):
    utc_now = datetime.now(timezone.utc)
    current_week = utc_now.isocalendar()[1]

    try:
        # Load existing data or initialize if not present
        try:
            tomato_df = get_df_from_csv_in_s3(s3, bucket_name, tomato_data_key)
            # Check if it's a new week
            if tomato_df["week_of_year"].iloc[0] != current_week:
                tomato_df["count"] = 0
                tomato_df["week_of_year"] = current_week
        except s3.exceptions.NoSuchKey:
            tomato_df = pd.DataFrame(
                {
                    "day": [
                        "Saturday",
                        "Sunday",
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                    ],
                    "count": [0, 0, 0, 0, 0, 0, 0],
                    "week_of_year": [current_week] * 7,
                }
            )

        # Update count for the specified day
        if day in tomato_df["day"].values:
            tomato_df.loc[tomato_df["day"] == day, "count"] += 1
            write_df_to_csv_in_s3(s3, bucket_name, tomato_data_key, tomato_df)
            return jsonify({"message": "Tomato count updated successfully"})
        else:
            return jsonify({"message": "Invalid day"}), 400

    except Exception as e:
        print(f"An error occurred: {e}")
        return (
            jsonify(
                {"message": "An error occurred while updating tomato count"}
            ),
            500,
        )


# Initialize the weekly data for no record for this week
def initialize_weekly_data():
    # Initialize the weekly data for each day to zero
    days = [
        "Saturday",
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
    ]
    week_of_year = datetime.now().isocalendar()[1]
    data = {"day": days, "count": [0] * 7, "week_of_year": [week_of_year] * 7}
    return pd.DataFrame(data)


# Router for getting weekly data from s3
@app.route("/get_weekly_data", methods=["GET"])
def get_weekly_data():
    utc_now = datetime.now(timezone.utc)
    current_week = utc_now.isocalendar()[1]
    tomato_df = get_df_from_csv_in_s3(s3, bucket_name, tomato_data_key)
    if tomato_df["week_of_year"].iloc[0] != current_week:
        # Reset the weekly data since it's a new week
        tomato_df = initialize_weekly_data()
        write_df_to_csv_in_s3(s3, bucket_name, tomato_data_key, tomato_df)
    # Convert DataFrame to JSON response
    return jsonify(tomato_df.to_dict(orient="records"))


if __name__ == "__main__":
    app.run(debug=True)

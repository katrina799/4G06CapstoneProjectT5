"""
Filename: <course_page.py>

Description:
    Manages course functionalities including adding, viewing, and removing
    courses, along with uploading and analyzing course syllabuses. Integrates
    with AWS S3 for storage and OpenAI for text processing.

Author: Jingyao Qin
Created: 2023-09-28
Last Modified: 2024-04-04
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    jsonify,
    url_for,
)

# Importing required modules and packages
import openai
import re
import csv
import json
import botocore
import ast
import pandas as pd
import io
import pypdf

# Attempt to import configuration and utility functions
try:
    from config import (
        MOCK_COURSE_INFO_CSV,
        COURSE_WORK_EXTRACTED_INFO,
        TITLE_TO_COLUMN_MAPPING,
    )
except ImportError:
    from .config import (
        MOCK_COURSE_INFO_CSV,
        COURSE_WORK_EXTRACTED_INFO,
        TITLE_TO_COLUMN_MAPPING,
    )

try:
    from src.util import (
        upload_df_to_s3,
        add_task_todo,
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        add_task_todo,
        upload_df_to_s3,
        get_df_from_csv_in_s3,
    )

# Defining a Blueprint for the courses module
courses_blueprint = Blueprint("courses", __name__)


# Router to course page
@courses_blueprint.route("/course_page", methods=["GET", "POST"])
def course_page():
    """
    Route to display the course page.

    Display the course content (name) on the page.
    """
    current_app.config["current_page"] = "course_page"
    # Render the course page
    return render_template(
        "course_page.html",
        username=current_app.config["username"],
        courses=current_app.config["courses"],
        current_page=current_app.config["current_page"],
    )


# Remove an existing course
@courses_blueprint.route("/remove_course", methods=["POST"])
def remove_course():
    """
    Function to remove an existing course from the user's list of courses.
    :return: Redirects to the start page or renders the course page if the
             current page is the course page.
    """
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

        # Remove the course from the user's courses list
        course_id = user_courses.pop(int(index))

        # Check if syllabus exists and delete associated PDF if found
        syllabus_exists, pdf_name = check_syllabus_exists(
            course_id, s3, bucket_name
        )
        if syllabus_exists:
            s3.delete_object(Bucket=bucket_name, Key=pdf_name)
            update_csv_after_deletion(course_id)
        delete_task_by_course(course_id)

        # Update the DataFrame and upload to S3
        list_str = str(user_courses)
        df.loc[df["username"] == username, "courses"] = list_str
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        current_app.config["courses"] = user_courses

        # Redirect or render the appropriate template
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=current_app.config["courses"],
                current_page="course_page",
            )
    return redirect(url_for("start"))


def delete_task_by_course(course_name):
    """
    Delete tasks associated with a specific course from the mock data.
    """
    bucket_name = current_app.config["BUCKET_NAME"]  # Bucket name in S3
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]  # File
    # path in S3
    s3 = current_app.config["S3_CLIENT"]  # S3 client

    try:
        tasks_df = get_df_from_csv_in_s3(s3, bucket_name, mock_tasks_data_file)
        # Check if the course exists in the tasks DataFrame
        if course_name in tasks_df["course"].values:
            # Delete tasks associated with the given course
            tasks_df = tasks_df[tasks_df["course"] != course_name]
            # Write the modified DataFrame back to CSV
            csv_buffer = io.StringIO()
            tasks_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            # Upload the updated CSV to S3
            s3.put_object(
                Bucket=bucket_name,
                Key=mock_tasks_data_file,
                Body=csv_buffer.getvalue(),
                ContentType="text/csv",
            )
            # Return success message
            return jsonify({"message": "Task deleted successfully"}), 200
        else:
            # Return message if the course is not found
            return jsonify({"message": "Task not found"}), 404
    except Exception as e:
        # Handle exceptions and return error message
        print(f"An error occurred: {e}")
        return (
            jsonify({"message": "An error occurred while deleting the task"}),
            500,
        )


@courses_blueprint.route("/add_course", methods=["POST"])
def add_course():
    """
    Add a new course to the user's profile.
    """
    # Retrieve necessary configurations and data.
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    bucket_name = current_app.config["BUCKET_NAME"]
    mock_data_file = current_app.config["MOCK_DATA_POC_NAME"]
    s3 = current_app.config["S3_CLIENT"]

    # Proceed if the request method is POST.
    if request.method == "POST":
        # Extract the new course from the request form.
        new_course = request.form["newcourse"]

        # Get DataFrame from CSV stored in S3.
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)

        # Retrieve the user's current courses.
        user_courses_series = df.loc[df["username"] == username, "courses"]
        user_courses_str = user_courses_series.tolist()[0]
        user_courses = ast.literal_eval(user_courses_str)

        # Add the new course to the user's courses.
        user_courses.append(new_course)
        list_str = str(user_courses)

        # Update the DataFrame with the new course.
        df.loc[df["username"] == username, "courses"] = list_str
        current_app.config["courses"] = user_courses

        # Upload the updated DataFrame to S3.
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)

        # Redirect to course page if currently on course page.
        if current_page == "course_page":
            return render_template(
                "course_page.html",
                username=username,
                courses=current_app.config["courses"],
                current_page="course_page",
            )

    # Redirect to the start page if not on course page.
    return redirect(url_for("start"))


# Router to course detail page
@courses_blueprint.route("/course_detail_page/<course_id>")
def course_detail(course_id):
    """
    Render the course detail page with information about the specified course.
    """
    mock_tasks_data_file = current_app.config["MOCK_DATA_POC_TASKS"]
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]
    message = request.args.get("message", "")

    # Check if syllabus exists for the specified course
    syllabus_exists, pdf_name = check_syllabus_exists(
        course_id, s3, bucket_name
    )

    # Load course information from CSV file
    course_info_df = pd.read_csv(MOCK_COURSE_INFO_CSV)
    course_info_row = course_info_df[course_info_df["course"] == course_id]

    # Load course works information from CSV file
    course_work_info = current_app.config["COURSE_WORK_EXTRACTED_INFO"]
    course_works_df = pd.read_csv(course_work_info)
    course_works = course_works_df[course_works_df["course"] == course_id]

    # Iterate through course works and add tasks to todo list
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

    # Render course detail page with course information and todo list
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
    """
    Uploads a PDF file as the syllabus for a specific course.
    """
    bucket_name = current_app.config["BUCKET_NAME"]  # S3 bucket name
    s3 = current_app.config["S3_CLIENT"]  # S3 client
    username = current_app.config["username"]  # Username

    # Check if file is present in the request and has a non-empty filename
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

    file = request.files["file"]  # Uploaded file
    # Check if file format is PDF
    if not file.filename.lower().endswith(".pdf"):
        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                message="File format is not PDF. Please upload a PDF file.",
            )
        )
    new_filename = f"{course_id}-syllabus.pdf"  # New filename for the PDF
    file.filename = new_filename

    try:
        # Upload file to S3 bucket with private access
        s3.upload_fileobj(
            file, bucket_name, new_filename, ExtraArgs={"ACL": "private"}
        )
        # Check if syllabus exists
        syllabus_exists, pdf_name = check_syllabus_exists(
            course_id, s3, bucket_name
        )
        if syllabus_exists:
            pdf_text = extract_text_from_pdf(pdf_name, bucket_name, s3)
            # Extract course work details from PDF
            course_work_details = extract_course_work_details(pdf_text)
            # Analyze course content
            course_info = analyze_course_content(pdf_text)
            # Process course work using OpenAI
            course_work_info = process_course_work_with_openai(
                course_work_details
            )
        else:
            course_info = ""  # Empty course info
            course_work_info = ""  # Empty course work info

        # Update CSV with uploaded file details and course info
        update_csv(course_id, file.filename, course_info)
        # Convert course work info to a list of dictionaries
        course_work_list = convert_to_list_of_dicts(course_work_info)
        # Write course work to CSV
        write_course_work_to_csv(course_work_list, course_id)

        # Read course info from CSV
        course_info_df = pd.read_csv(MOCK_COURSE_INFO_CSV)
        course_info_row = course_info_df[course_info_df["course"] == course_id]

        # Read extracted course works from CSV
        course_works_df = pd.read_csv(COURSE_WORK_EXTRACTED_INFO)
        course_works = course_works_df[course_works_df["course"] == course_id]

        # Iterate over course works and add tasks to TODO list
        for index, row in course_works.iterrows():
            course_name = row["course"]
            task_name = row["course_work"]
            due_date = row["due_date"]
            weight = row["score_distribution"]
            est_hours = 3  # Estimated hours for task
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

        # Redirect to course detail page with success message
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
        # Redirect to course detail page with failure message
        return redirect(
            url_for(
                "courses.course_detail",
                course_id=course_id,
                message="AWS authentication failed. Check your AWS keys.",
                username=username,
            )
        )


# Update the record in mock_course_info.csv file
def update_csv(course_id, pdf_name, api_response):
    """
    Update the information of a course in the mock_course_info.csv file.

    """
    course_info = parse_course_info(api_response)

    df = pd.read_csv(MOCK_COURSE_INFO_CSV).dropna(how="all")

    # Check if the course ID exists in the DataFrame
    if course_id in df["course"].dropna().values:
        # Update existing course information
        for column, value in course_info.items():
            df.loc[df["course"] == course_id, column] = value
    else:
        # Add new course information
        new_data = pd.DataFrame(
            [
                {
                    **{"course": course_id, "course_syllabus": pdf_name},
                    **course_info,
                }
            ]
        )
        df = pd.concat([df, new_data], ignore_index=True)

    # Fill NaN values with "Not Found"
    df.fillna("Not Found", inplace=True)

    # Write updated DataFrame back to CSV file
    df.to_csv(MOCK_COURSE_INFO_CSV, index=False)


def parse_course_info(api_response):
    """
    Parses course information from the API response.
    """

    # Regular expression pattern to extract course information
    pattern = r"\d+\.\s+([A-Za-z ]+):\s+((?:(?!#).)*)"

    # Find all matches of the pattern in the API response
    matches = re.findall(pattern, api_response, re.DOTALL)

    # Initialize dictionary to store parsed information
    info_dict = {}

    # Set to store found titles to avoid duplicates
    found_titles = set()

    # Iterate through matches to extract information
    for match in matches:
        title = match[0].strip()
        if title in TITLE_TO_COLUMN_MAPPING and title not in found_titles:
            found_titles.add(title)
            info = match[1].rstrip(" #").strip()
            if info == "":
                info = "Not Found"
            info_dict[TITLE_TO_COLUMN_MAPPING[title]] = info

    return info_dict


def check_syllabus_exists(course_id, s3, bucket_name):
    """
    Check if syllabus PDF exists in the specified S3 bucket for a given
    course ID.
    """
    try:
        pdf_name = course_id + "-syllabus.pdf"  # Construct PDF name
        s3.head_object(Bucket=bucket_name, Key=pdf_name)  # Check if exists
        return True, pdf_name  # Syllabus exists
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":  # Syllabus not found
            return False, None
        else:
            raise e  # Other error, re-raise


# Extracts text from a PDF file.
def extract_text_from_pdf(filename, bucket_name, s3):
    """
    Extracts text content from a PDF file stored in an S3 bucket.
    """
    # Retrieve the PDF file from S3 bucket
    response = s3.get_object(Bucket=bucket_name, Key=filename)
    pdf_file = response["Body"].read()
    pdf_file_obj = io.BytesIO(pdf_file)

    # Read PDF using PyPDF2
    pdf_reader = pypdf.PdfReader(pdf_file_obj)
    text = ""

    # Iterate through each page and extract text
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() if page.extract_text() else ""

    return text


def update_csv_after_deletion(course_id):
    """
    an helper function make the website refresh after deletion
    """
    pass


def extract_course_work_details(syllabus_text, max_tokens=4097):
    """
    Extracts course work details from a syllabus text.
    """
    if estimate_token_count(syllabus_text) <= max_tokens:
        api_result = process_course_work_with_openai(syllabus_text)
        # API result contains course work details.
        return api_result
    else:
        # If syllabus exceeds token limit, process in segments.
        return process_course_work_in_segments(syllabus_text, max_tokens)


def estimate_token_count(text):
    """
    Helper function to estimate the number of tokens
    """
    return len(text) // 4  # A rough estimate


def analyze_course_content(pdf_text, max_tokens=4097):
    """
    Modified analyze_course_content function
    """
    # Estimate the token count
    if estimate_token_count(pdf_text) <= max_tokens:
        # If within token limit, process normally
        return process_text_with_openai(pdf_text)
    else:
        # If over the limit, split the text and process in segments
        return process_text_in_segments(pdf_text, max_tokens)


def process_course_work_in_segments(text, max_tokens):
    """
    Process the given text in segments to ensure it fits within the specified
    maximum token limit per segment.
    """
    # Calculate the length of each segment based on the maximum allowed tokens
    segment_length = max_tokens * 4

    # Divide the input text into segments of specified length
    segments = [
        text[i: i + segment_length]
        for i in range(0, len(text), segment_length)
    ]

    full_output = ""

    # Process each segment independently and concatenate the results
    for segment in segments:
        full_output += process_course_work_with_openai(segment) + "\n\n"

    return full_output


def process_text_in_segments(text, max_tokens):
    """
    Process the input text in segments to ensure it fits within the specified
    token limit.
    """
    segment_length = (
        max_tokens * 4
    )  # Roughly estimate segment length in characters

    full_output = ""
    start_index = 0

    while start_index < len(text):
        end_index = min(start_index + segment_length, len(text))
        segment = text[start_index:end_index]
        full_output += process_text_with_openai(segment) + "\n\n"
        start_index += segment_length

    return full_output


def process_text_with_openai(text):
    """
    Function to process a text segment with OpenAI fot extract course info
    """

    # Constructing a prompt for OpenAI based on the given text segment
    prompt = f"""
    human read the pdf_text and extract the following information from the
    course syllabus and strictly follow the format mentioned below
    MOST IMPORTANT: all info message should have "#" at the end to
    inform the ending! If you do not found, put a String "Not Found" in the
    corresponding area of the return template!
    Template:
    1. Instructor Name:
    2. Instructor Email:
    3. Instructor Office Hour:
    4. Required and Optional Textbook List:
    5. Lecture Schedule List with Location:
    6. Tutorials Schedule List with Location:
    7. Course Teaching Assistants (TAs) Name and Email List:
    (template: Jane Qin: qinj15@mcmaster.ca; Qianni Wang: qian12@mcmaster.ca#)
    8. Course Introduction:
    9. Course Goal/Mission:
    10. MSAF Policy:

    Syllabus Content:
    {text}
    """
    # Getting response from OpenAI ChatCompletion API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    return response["choices"][0]["message"]["content"].strip()


def process_course_work_with_openai(syllabus_text):
    """
    Function to process a text segment with OpenAI for coursework info
    """

    # Constructing a prompt for OpenAI based on the given text segment
    prompt = f"""
    human read and understand the syllabus_text content and extract all
    the courseworks, with their start date (if there is any),
    due date/deadline, and score distribution percentage.
    If there is only one date displayed for a course work,
    consider it as it's deadline.
    I want you reformat and only return these course work details into a
    Python List of Python Dictionary format, and each course work is a
    Python library in the list.

    All Library in the list have following Keys:
        - "Course Work Name" with value of String data type
        - "Start Date" with value of String "yyyy-mm-dd" data format
        - "Due Date" with value of String "yyyy-mm-dd" data format
        - "Score Distribution" with value of Int data type

    MOST IMPORTANT: you do not need to reply any other words, but the
    Python list! If any other information is missing, put String 'Not Found'
    in the corresponding value.
    Also, please exclude any course work library that do not have a score
    distribution. All Date need to be in yyyy-mm-dd format or
    a String "Not Found". Put 2024 as year if there is a due date but no year
    has been mentioned! If there is no due date, just put String "Not Found"!
    Reply with only Python list.
    Your response should start with "[{" and end with "}]"!
    Syllabus Content:
    {syllabus_text}
    """
    # Getting response from OpenAI ChatCompletion API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a human teaching assistant.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    return response["choices"][0]["message"]["content"].strip()


def write_course_work_to_csv(course_work_list, course_id):
    """
    Write course work information to a CSV file.

    """
    # File path for CSV where course work information is stored
    csv_file_path = COURSE_WORK_EXTRACTED_INFO

    # Headers for CSV columns
    headers = [
        "course id",
        "course work",
        "start date",
        "due date",
        "score distribution",
    ]

    # Open CSV file in append mode
    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
        # Initialize CSV writer with specified headers
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if file is empty
        if file.tell() == 0:
            writer.writeheader()

        # Iterate over course work list
        for item in course_work_list:
            # Prepare a row for writing into CSV
            row = {
                "course id": course_id,  # Course ID
                "course work": item.get("Course Work Name", "Not Found"),
                "start date": item.get("Start Date", "Not Found"),
                "due date": item.get("Due Date", "Not Found"),
                "score distribution": str(
                    item.get("Score Distribution", "Not Found")
                ),
            }
            # Write row into CSV
            writer.writerow(row)


def convert_to_list_of_dicts(course_work_data):
    """
    Convert course work data from JSON format to a list of dictionaries.
    """
    try:
        # Attempt to parse JSON string into a list of dictionaries
        course_work_list = json.loads(course_work_data)
        return course_work_list
    except json.JSONDecodeError:
        # Return an empty list if JSON decoding fails
        return []

# Helper functions that will be commonly used
import pandas as pd
import os
import io
import botocore
import pypdf
import re
import json
import csv
import openai

from joblib import load
from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.neural_network import MLPClassifier
import sqlite3
from flask_sqlalchemy import SQLAlchemy


try:
    from config import (
        MOCK_COURSE_INFO_CSV,
        ICON_ORDER_PATH,
        COURSE_WORK_EXTRACTED_INFO,
        TITLE_TO_COLUMN_MAPPING,
    )
except ImportError:
    from .config import (
        MOCK_COURSE_INFO_CSV,
        ICON_ORDER_PATH,
        COURSE_WORK_EXTRACTED_INFO,
    )

# Initialize OpenAI API with your API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

db = SQLAlchemy()


class User(db.Model):
    userId = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    topics = db.relationship("Topic", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="commenter", lazy=True)


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(120))
    userId = db.Column(db.Integer, db.ForeignKey("user.userId"))


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)
    topicId = db.Column(db.Integer, db.ForeignKey("topic.id"))
    userId = db.Column(db.Integer, db.ForeignKey("user.userId"))


class SqueezeTransformer(TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X.squeeze()


# Define training pipeline for task priority classification
def get_task_priority_training_pipeline():
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
    # This can be changed to different model
    classifier = MLPClassifier(
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

    # Preprocessing step: combining feature pipelines
    preprocessor = ColumnTransformer(
        transformers=[
            ("numerical", numerical_feature_pipeline, numerical_cols),
            ("categorical", categorical_feature_pipeline, category_cols),
            ("text1", text_feature_pipeline, text_cols[0]),
            ("text2", text_feature_pipeline, text_cols[1]),
        ]
    )
    prepro = preprocessor
    classif = classifier
    pipeline = Pipeline(steps=[("preprocessor", prepro), ("cf", classif)])

    return pipeline


# Load priority model from s3
def load_priority_model_from_s3(s3, bucket_name, s3_model_file_path):
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_model_file_path)
    model_file = io.BytesIO(s3_obj["Body"].read())
    model_file.seek(0)
    model = load(model_file)
    return model


# Get a specific csv file from s3 and return it as a dataframe
def get_df_from_csv_in_s3(s3, bucket_name, s3_csv_file_path):
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    df = pd.read_csv(s3_obj["Body"])
    return df


def parse_course_info(api_response):
    if not api_response:
        return {}

    pattern = r"\d+\.\s+([A-Za-z ]+):\s+((?:(?!#).)*)"
    matches = re.findall(pattern, api_response, re.DOTALL)

    info_dict = {}
    found_titles = set()

    for match in matches:
        title = match[0].strip()
        if title in TITLE_TO_COLUMN_MAPPING and title not in found_titles:
            found_titles.add(title)
            info = match[1].rstrip(" #").strip()
            if info == "":
                info = "Not Found"
            info_dict[TITLE_TO_COLUMN_MAPPING[title]] = info

    return info_dict


# Upload a dataframe to AWS s3
def upload_df_to_s3(df, s3, bucket_name, s3_csv_file_path):
    new_csv_file_path = "poc-data/tmp.csv"
    df.to_csv(new_csv_file_path)
    s3.upload_file(
        new_csv_file_path,
        bucket_name,
        s3_csv_file_path,
    )
    os.remove(new_csv_file_path)


# Update the record in mock_course_info.csv file
def update_csv(course_id, pdf_name, api_response):
    course_info = parse_course_info(api_response)

    df = pd.read_csv(MOCK_COURSE_INFO_CSV).dropna(how="all")

    if course_id in df["course"].dropna().values:
        for column, value in course_info.items():
            df.loc[df["course"] == course_id, column] = value
    else:
        new_data = pd.DataFrame(
            [
                {
                    **{"course": course_id, "course_syllabus": pdf_name},
                    **course_info,
                }
            ]
        )
        df = pd.concat([df, new_data], ignore_index=True)

    df.fillna("Not Found", inplace=True)

    df.to_csv(MOCK_COURSE_INFO_CSV, index=False)


# Check if the syllabus pdf is exist in S3 folder or not
def check_syllabus_exists(course_id, s3, bucket_name):
    try:
        pdf_name = course_id + "-syllabus.pdf"
        s3.head_object(Bucket=bucket_name, Key=pdf_name)
        return True, pdf_name
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False, None
        else:
            raise e


# Extract text from pdf file
def extract_text_from_pdf(filename, bucket_name, s3):
    response = s3.get_object(Bucket=bucket_name, Key=filename)
    pdf_file = response["Body"].read()
    pdf_file_obj = io.BytesIO(pdf_file)

    pdf_reader = pypdf.PdfReader(pdf_file_obj)
    text = ""

    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() if page.extract_text() else ""

    return text


def update_csv_after_deletion(course_id):
    mock_course_info_path = MOCK_COURSE_INFO_CSV
    df_course_info = pd.read_csv(mock_course_info_path)
    df_course_info = df_course_info[df_course_info["course"] != course_id]
    df_course_info.to_csv(mock_course_info_path, index=False)

    course_work_info_path = COURSE_WORK_EXTRACTED_INFO
    df_course_works = pd.read_csv(course_work_info_path)
    df_course_works = df_course_works[df_course_works["course"] != course_id]
    df_course_works.to_csv(course_work_info_path, index=False)


def extract_course_work_details(syllabus_text, max_tokens=4097):
    if estimate_token_count(syllabus_text) <= max_tokens:
        api_result = process_course_work_with_openai(syllabus_text)
        # print("check course work detail api result: ", api_result)
        return api_result
    else:
        # print("course_work_api go to segments")
        return process_course_work_in_segments(syllabus_text, max_tokens)


def process_course_work_in_segments(text, max_tokens):
    segment_length = max_tokens * 4
    segments = [
        text[i: i + segment_length]
        for i in range(0, len(text), segment_length)
    ]
    full_output = ""

    for segment in segments:
        full_output += process_course_work_with_openai(segment) + "\n\n"

    return full_output


def process_text_in_segments(text, max_tokens):
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


def convert_to_list_of_dicts(course_work_data):
    try:
        course_work_list = json.loads(course_work_data)
        return course_work_list
    except json.JSONDecodeError:
        return []


def write_course_work_to_csv(course_work_list, course_id):
    csv_file_path = COURSE_WORK_EXTRACTED_INFO
    headers = [
        "course id",
        "course work",
        "start date",
        "due date",
        "score distribution",
    ]

    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        if file.tell() == 0:
            writer.writeheader()

        for item in course_work_list:
            row = {
                "course id": course_id,
                "course work": item.get("Course Work Name", "Not Found"),
                "start date": item.get("Start Date", "Not Found"),
                "due date": item.get("Due Date", "Not Found"),
                "score distribution": str(
                    item.get("Score Distribution", "Not Found")
                ),
            }
            writer.writerow(row)


# Helper function to estimate the number of tokens
def estimate_token_count(text):
    return len(text) // 4  # A rough estimate


# Modified analyze_course_content function
def analyze_course_content(pdf_text, max_tokens=4097):
    # Estimate the token count
    if estimate_token_count(pdf_text) <= max_tokens:
        # If within token limit, process normally
        return process_text_with_openai(pdf_text)
    else:
        # If over the limit, split the text and process in segments
        return process_text_in_segments(pdf_text, max_tokens)


# Function to process a text segment with OpenAI
def process_text_with_openai(text):
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

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    return response["choices"][0]["message"]["content"].strip()


def process_course_work_with_openai(syllabus_text):
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

    Syllabus Content:
    {syllabus_text}
    """

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


def sql_to_csv_s3(table, s3, bucket_name, s3_csv_file_path):
    # Connect to your SQLite database
    conn = sqlite3.connect("instance/project.db")
    cursor = conn.cursor()

    # Query the database to get the data you want to export
    cursor.execute("SELECT * FROM " + table)
    rows = cursor.fetchall()

    # Choose a file name for your CSV file
    csv_filename = "poc-data/" + table + "_data.csv"

    # Open a CSV file for writing
    with open(csv_filename, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)

        # Write the header
        csvwriter.writerow([i[0] for i in cursor.description])

        # Write the data
        csvwriter.writerows(rows)

    # Close the cursor and the database connection
    cursor.close()
    conn.close()
    # Now you can use the AWS CLI to upload the CSV file
    s3.upload_file(csv_filename, bucket_name, s3_csv_file_path)


def initialize_user_db_from_s3(s3, bucket_name, s3_csv_file_path, db):
    # Get the CSV file from S3
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    csv_content = s3_obj["Body"].read().decode("utf-8")

    # Convert the CSV content to a StringIO object and then to a DataFrame
    csv_stringio = io.StringIO(csv_content)
    df = pd.read_csv(csv_stringio)

    # Add the data to the database session
    for _, row in df.iterrows():
        # Check if the Topic with this ID already exists
        existing_user = db.session.query(User).get(row["userId"])
        if existing_user:
            existing_user.username = row["username"]
        else:
            # Or insert a new one if it does not exist
            new_user = User(username=row["username"])
            db.session.add(new_user)

    # Commit the session to the database
    db.session.commit()


def initialize_topic_db_from_s3(s3, bucket_name, s3_csv_file_path, db):
    # Get the CSV file from S3
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    csv_content = s3_obj["Body"].read().decode("utf-8")

    # Convert the CSV content to a StringIO object and then to a DataFrame
    csv_stringio = io.StringIO(csv_content)
    df = pd.read_csv(csv_stringio)

    # Add the data to the database session
    for _, row in df.iterrows():
        # Check if the Topic with this ID already exists
        existing_topic = db.session.query(Topic).get(row["id"])
        if existing_topic:
            # Update existing record if necessary
            existing_topic.title = row["title"]
            existing_topic.description = row["description"]
            existing_topic.userId = row["userId"]
        else:
            # Or insert a new one if it does not exist
            new_topic = Topic(
                title=row["title"],
                description=row["description"],
                userId=row["userId"],
            )
            db.session.add(new_topic)

    # Commit the session to the database
    db.session.commit()


def initialize_comment_db_from_s3(s3, bucket_name, s3_csv_file_path, db):
    # Get the CSV file from S3
    s3_obj = s3.get_object(Bucket=bucket_name, Key=s3_csv_file_path)
    csv_content = s3_obj["Body"].read().decode("utf-8")

    # Convert the CSV content to a StringIO object and then to a DataFrame
    csv_stringio = io.StringIO(csv_content)
    df = pd.read_csv(csv_stringio)

    # Add the data to the database session
    for _, row in df.iterrows():
        # Check if the Topic with this ID already exists
        existing_comment = db.session.query(Comment).get(row["id"])
        if existing_comment:
            # Update existing record if necessary
            existing_comment.text = row["text"]
            existing_comment.topicId = row["topicId"]
            existing_comment.userId = row["userId"]
        else:
            # Or insert a new one if it does not exist
            new_comment = Comment(
                text=row["text"],
                topicId=row["topicId"],
                userId=row["userId"],
            )
            db.session.add(new_comment)

    # Commit the session to the database
    db.session.commit()


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

        write_order_csv_to_s3(s3, ICON_ORDER_PATH, default_df, bucket_name)

        return default_df
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame(columns=["username", "orders"])


def write_order_csv_to_s3(s3, icon_order_path, df, bucket_name):
    new_csv_file_path = "poc-data/tmp.csv"
    df.to_csv(new_csv_file_path, index=False)
    s3.upload_file(
        new_csv_file_path,
        bucket_name,
        icon_order_path,
    )
    os.remove(new_csv_file_path)


def process_transcript_pdf(path_to_pdf):
    reader = pypdf.PdfReader(path_to_pdf)
    text = ""
    points = []
    units = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            for line in text.split("\n"):
                if line.startswith("Term Totals"):
                    points.append(float(line.split()[-2]))
                    units.append(float(line.split()[-3]))
    cGPA = sum(points) / sum(units)
    os.remove(path_to_pdf)
    return cGPA

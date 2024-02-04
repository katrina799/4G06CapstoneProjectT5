# Helper functions that will be commonly used
import pandas as pd
import os
import io
import botocore
import pypdf
import re
from joblib import load
from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.neural_network import MLPClassifier
import csv
import sqlite3
from flask_sqlalchemy import SQLAlchemy


try:
    from config import MOCK_COURSE_INFO_CSV, ICON_ORDER_PATH
except ImportError:
    from .config import MOCK_COURSE_INFO_CSV

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


# Upload a dataframe to s3
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
def update_csv(course_id, pdf_name, email_list, instructor_name):
    csv_file_path = MOCK_COURSE_INFO_CSV

    df = pd.read_csv(csv_file_path).dropna(how="all")

    col_name_syllabus = "course_syllabus"
    col_name_emails = "email_list"
    col_name_prof = "instructor_name"

    if course_id in df["course"].dropna().values:
        df.loc[df["course"] == course_id, col_name_syllabus] = pdf_name
        df.loc[df["course"] == course_id, col_name_emails] = str(email_list)
        df.loc[df["course"] == course_id, col_name_prof] = instructor_name
    else:
        new_row = pd.DataFrame(
            {
                "course": [course_id],
                col_name_syllabus: [pdf_name],
                col_name_emails: [str(email_list)],
                col_name_prof: [instructor_name],
            }
        )
        df = pd.concat([df, new_row], ignore_index=True)

    df.to_csv(csv_file_path, index=False)


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


# Extract all emails exist in a pdf in S3
def extract_emails_from_pdf(
    filename,
    bucket_name,
    s3,
):
    response = s3.get_object(Bucket=bucket_name, Key=filename)
    pdf_file = response["Body"].read()
    pdf_file_obj = io.BytesIO(pdf_file)

    pdf_reader = pypdf.PdfReader(pdf_file_obj)
    text = ""

    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text()

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    emails = re.findall(email_pattern, text)

    return emails


# Extract the instructor name in a syllabus file in S3
def extract_instructor_name_from_pdf(filename, bucket_name, s3):
    response = s3.get_object(Bucket=bucket_name, Key=filename)
    pdf_file = response["Body"].read()
    pdf_file_obj = io.BytesIO(pdf_file)

    pdf_reader = pypdf.PdfReader(pdf_file_obj)
    text = ""

    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text()

    instructor_pattern = r"(?:Dr\.|Instructor:)\s+([A-Za-z]+ [A-Za-z]+)"
    match = re.search(instructor_pattern, text)
    if match:
        instructor_name = "Dr. " + match.group(1).strip()
    else:
        instructor_name = "sorry not found"

    return instructor_name


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

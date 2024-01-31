# Helper functions that will be commonly used
import pandas as pd
import os
import io
import botocore
import pypdf
import json
import csv

import re
from joblib import load
from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.neural_network import MLPClassifier
import openai

# Initialize OpenAI API with your API key
openai.api_key = "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"

title_to_column_mapping = {
    "Instructor Name": "instructor_name",
    "Instructor Email": "instructor_email",
    "Instructor Office Hour": "instructor_office_hour_list",
    "Required and Optional Textbook List": "textbooks",
    "Lecture Schedule List with Location": "lecture_schedule",
    "Tutorials Schedule List with Location": "tutorial_schedule",
    "Course Teaching Assistants (TAs) Name and Email List": "TAs",
    "Course Introduction": "course_introduction",
    "Course Goal/Mission": "goal_mission",
    "MSAF Policy": "MSAF",
}

try:
    from config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO
except ImportError:
    from .config import MOCK_COURSE_INFO_CSV, COURSE_WORK_EXTRACTED_INFO


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


def parse_course_info(api_response):
    if not api_response:
        return {}

    # 正则表达式匹配每个信息项
    pattern = r"\d+\.\s+([A-Za-z ]+):\s+((?:(?!#).)*)"
    matches = re.findall(pattern, api_response, re.DOTALL)

    info_dict = {}
    found_titles = set()

    for match in matches:
        title = match[0].strip()
        if title in title_to_column_mapping and title not in found_titles:
            found_titles.add(title)
            # 去除每个信息项末尾的 "#" 号和可能的空白
            info = match[1].rstrip(" #").strip()
            if info == "":
                info = "N/A"
            info_dict[title_to_column_mapping[title]] = info

    return info_dict


# Update the record in mock_course_info.csv file
def update_csv(course_id, pdf_name, api_response):
    csv_file_path = MOCK_COURSE_INFO_CSV
    course_info = parse_course_info(api_response)

    # 读取 CSV 文件
    df = pd.read_csv(csv_file_path).dropna(how="all")

    # 检查课程 ID 是否存在
    if course_id in df["course"].dropna().values:
        # 更新现有记录
        for column, value in course_info.items():
            df.loc[df["course"] == course_id, column] = value
    else:
        # 添加新记录
        new_data = pd.DataFrame(
            [
                {
                    **{"course": course_id, "course_syllabus": pdf_name},
                    **course_info,
                }
            ]
        )
        df = pd.concat([df, new_data], ignore_index=True)

    # 保存更新后的 CSV 文件
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


# new
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
    csv_file_path = MOCK_COURSE_INFO_CSV
    df = pd.read_csv(csv_file_path)

    # 删除与course_id匹配的行
    df = df[df["course"] != course_id]

    # 保存更新后的CSV文件
    df.to_csv(csv_file_path, index=False)


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
    course syllabus and strictly follow the format below 
    (If you do not found, just put a "N/A" in the 
    corresponding area of the return template. 
    Strictly careful about that all info message should have "#" at the end to inform the ending):
    1. Instructor Name:
    2. Instructor Email:
    3. Instructor Office Hour:
    4. Required and Optional Textbook List:
    5. Lecture Schedule List with Location: 
    6. Tutorials Schedule List with Location: 
    7. Course Teaching Assistants (TAs) Name and Email List: 
    (template: Jane Qin -- qinj15@mcmaster.ca; Qianni Wang -- qian12@mcmaster.ca#)
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
    read and understand the syllabus_text content and extract all 
    the courseworks, with their start date and time(if there is any), 
    due date and time/ deadline , and score distribution percentage.
    If there is only one date or time displayed for a course work, 
    consider it as it's deadline.

    Then I want you reformat and only return these course work details into a 
    Python List of Python Dictionary format:
    Each course work is a library in the list.
    All Library in the list have following Keys: 
        - "Course Work Name" with value of String data type
        - "Start Date" with value of String "yyyy-mm-dd" data type
        - "Start Time" with value of String "hh:mm" in 24 hours data type
        - "Due Date" with value of String "yyyy-mm-dd" data type
        - "Due Time" with value of String "hh:mm" in 24 hours data type
        - "Score Distribution" with value of int data type
    
    MOST IMPORTANT: you do not need to reply any words, but the Python list! 
    If any other information is missing, put 'N/A' in the corresponding value.
    Also, please exclude any course work library that do not have a score
    distribution. 

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


def extract_course_work_details(syllabus_text, max_tokens=4097):
    # 估计令牌数量
    if estimate_token_count(syllabus_text) <= max_tokens:
        # 如果在令牌限制内，处理整个文本
        return process_course_work_with_openai(syllabus_text)
    else:
        # 如果超过限制，分段处理
        return process_course_work_in_segments(syllabus_text, max_tokens)


def process_course_work_in_segments(text, max_tokens):
    segment_length = max_tokens * 4  # 根据令牌限制估计分段长度
    segments = [
        text[i : i + segment_length]
        for i in range(0, len(text), segment_length)
    ]
    full_output = ""

    for segment in segments:
        full_output += process_course_work_with_openai(segment) + "\n\n"

    return full_output


# Function to split and process text in segments
def process_text_in_segments(text, max_tokens):
    segment_length = (
        max_tokens * 4
    )  # Roughly estimate segment length in characters
    segments = [
        text[i : i + segment_length]
        for i in range(0, len(text), segment_length)
    ]
    full_output = ""

    for segment in segments:
        full_output += process_text_with_openai(segment) + "\n\n"

    return full_output


def convert_to_list_of_dicts(course_work_data):
    try:
        # 尝试将字符串数据转换为 Python 对象
        course_work_list = json.loads(course_work_data)
        return course_work_list
    except json.JSONDecodeError:
        # 如果转换失败，返回空列表或错误信息
        return []


def write_course_work_to_csv(course_work_list, course_id):
    csv_file_path = COURSE_WORK_EXTRACTED_INFO
    headers = [
        "course id",
        "course work",
        "start date",
        "start time",
        "due date",
        "due time",
        "score distribution",
    ]

    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # 如果文件是空的，写入头部
        if file.tell() == 0:
            writer.writeheader()

        # 遍历列表，写入每行数据
        for item in course_work_list:
            row = {
                "course id": course_id,
                "course work": item.get("Course Work Name", "N/A"),
                "start date": item.get("Start Date", "N/A"),
                "start time": item.get("Start Time", "N/A"),
                "due date": item.get("Due Date", "N/A"),
                "due time": item.get("Due Time", "N/A"),
                "score distribution": str(
                    item.get("Score Distribution", "N/A")
                ),
            }
            writer.writerow(row)

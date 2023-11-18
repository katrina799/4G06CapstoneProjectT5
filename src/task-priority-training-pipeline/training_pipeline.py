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
from sklearn.ensemble import RandomForestClassifier

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
y = data["priority_level"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

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
classfier = RandomForestClassifier()

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

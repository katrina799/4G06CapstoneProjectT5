# Helper functions that will be commonly used
import pandas as pd
import os
import io
import botocore
from joblib import load

from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.neural_network import MLPClassifier


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
    pipeline = Pipeline(
        steps=[("preprocessor", preprocessor), ("cf", classifier)]
    )

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


def update_csv(course_id, pdf_name):
    csv_file_path = "./poc-data/mock_course_info.csv"

    df = pd.read_csv(csv_file_path).dropna(how="all")

    col_name = "course_syllabus"
    if course_id in df["course"].dropna().values:
        df.loc[df["course"] == course_id, col_name] = pdf_name
    else:
        new_row = pd.DataFrame({"course": [course_id], col_name: [pdf_name]})
        df = pd.concat([df, new_row], ignore_index=True)

    df.to_csv(csv_file_path, index=False)


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

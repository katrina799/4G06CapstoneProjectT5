# Helper functions that will be commonly used
import pandas as pd
import os
import botocore


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

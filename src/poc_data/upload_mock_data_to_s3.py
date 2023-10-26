import os
import boto3
from config import BUCKET_NAME, MOCK_DATA_POC_NAME

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

s3.upload_file(MOCK_DATA_POC_NAME, BUCKET_NAME, MOCK_DATA_POC_NAME)

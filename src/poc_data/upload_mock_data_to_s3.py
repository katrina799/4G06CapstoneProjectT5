import os
import boto3
from src import config


s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)
filepath = f"src/poc_data/{config.MOCK_DATA_POC_NAME}"
s3.upload_file(filepath, config.BUCKET_NAME, config.MOCK_DATA_POC_NAME)

import os

import boto3
from flask import Flask, render_template, request, Response


app = Flask(__name__)

# Loading configs/global variables
app.config.from_pyfile("config.py")
bucket_name = app.config["BUCKET_NAME"]

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)


# This is the home page of the website
@app.route("/")
def start():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(debug=True)

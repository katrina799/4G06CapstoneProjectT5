import os
import io
import re
import PyPDF2
import boto3
from flask import Flask, render_template, request, Response

from helper import get_df_from_csv_in_s3


app = Flask(__name__)

# Loading configs/global variables
app.config.from_pyfile("config.py")
bucket_name = app.config["BUCKET_NAME"]
mock_data_file = app.config["MOCK_DATA_POC_NAME"]

username = ""

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)


# This is the home page of the website
@app.route("/")
def start():
    global username
    df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
    username = df.loc[0, "username"]  # For PoC purpose
    return render_template("index.html", username=username)


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


@app.route("/change_username", methods=["POST"])
def change_username():
    global username
    if request.method == "POST":
        new_username = request.form["newusername"]
        df = get_df_from_csv_in_s3(s3, bucket_name, mock_data_file)
        df.loc[df["username"] == username, "username"] = new_username
        changed_mock_data_file = "mock_data_poc_changed.csv"
        new_csv_file_path = f"poc_data/{changed_mock_data_file}"
        df.to_csv(new_csv_file_path)
        s3.upload_file(
            new_csv_file_path,
            bucket_name,
            changed_mock_data_file,
        )
        os.remove(new_csv_file_path)
        username = new_username
    return render_template("index.html", username=username)

@app.route("/get_emails", methods=["GET"])
def extract_emails_from_pdf():
    filename = request.args.get("filename")
    if request.method == "GET":
        response = s3.get_object(Bucket=bucket_name, Key=filename)
        pdf_file = response["Body"].read()
        pdf_file_obj = io.BytesIO(pdf_file)
        
        pdf_reader = PyPDF2.PdfReader(pdf_file_obj)
        text = ''

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        emails = re.findall(email_pattern, text)

        return render_template("index.html", emails=emails)

if __name__ == "__main__":
    app.run(debug=True)

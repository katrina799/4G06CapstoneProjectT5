"""
Filename: profile_page.py

Description:
    Manages user profile operations for a web application. Features include
    displaying user profiles with academic details, uploading academic
    transcripts to calculate and display the cumulative Grade Point Average
    (cGPA), and allowing users to change their username. It integrates with
    filesystem operations for file handling and AWS S3 for data storage.

Author: Qianni Wang
Created: 2024-02-04
Last Modified: 2024-04-04
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    url_for,
)
import os
import pypdf

try:
    from src.util import (
        upload_df_to_s3,
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        upload_df_to_s3,
        get_df_from_csv_in_s3,
    )
profile_blueprint = Blueprint("profile", __name__)


@profile_blueprint.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    """
    Render the profile page with user information.
    """
    # Retrieve username from application config
    username = current_app.config.get("username", "")

    # Retrieve current page from application config
    current_page = current_app.config.get("current_page", "home")

    # Retrieve cGPA from application config, set default if not available
    cGPA = current_app.config.get(
        "cGPA", "None (Please upload your transcript)"
    )

    # Render profile page template with retrieved information
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )


@profile_blueprint.route("/upload_transcript", methods=["GET", "POST"])
def upload_transcript():
    """
    Route for uploading a transcript file.
    """
    # Get current user's username and page
    username = current_app.config.get("username", "")
    current_page = current_app.config.get("current_page", "home")

    # Path to store uploaded transcripts
    Transcript_path = current_app.config["UPLOAD_FOLDER"]

    # Current CGPA
    cGPA = current_app.config.get(
        "cGPA", "None (Please upload your transcript)"
    )

    if request.method == "POST":
        # Check if file was uploaded
        file = request.files["transcript"]
        os.makedirs(Transcript_path, exist_ok=True)
        if file:
            # Save the uploaded file
            filename = file.filename
            file.save(os.path.join(Transcript_path, filename))

            # Process the transcript and update current CGPA
            current_app.config["cGPA"] = process_transcript_pdf(
                os.path.join(Transcript_path, filename)
            )

            # Render profile page with updated CGPA
            return render_template(
                "profile_page.html",
                username=username,
                current_page=current_page,
                cGPA=str(current_app.config["cGPA"]),
            )

    # Render profile page with upload form
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )


# Change user's name
@profile_blueprint.route("/change_username", methods=["POST"])
def change_username():
    """
    Endpoint to change user's name.
    """
    username = current_app.config.get(
        "username", ""
    )  # Get current username from configuration
    bucket_name = current_app.config[
        "BUCKET_NAME"
    ]  # Get S3 bucket name from configuration
    mock_data_file = current_app.config[
        "MOCK_DATA_POC_NAME"
    ]  # Get mock data file name from configuration

    s3 = current_app.config["S3_CLIENT"]  # Get S3 client from configuration

    if request.method == "POST":
        new_username = request.form[
            "newusername"
        ]  # Get new username from request form
        df = get_df_from_csv_in_s3(
            s3, bucket_name, mock_data_file
        )  # Read data from S3 into DataFrame
        # Replace current username with new username in DataFrame
        df.loc[df["username"] == username, "username"] = new_username
        # Upload modified DataFrame to S3
        upload_df_to_s3(df, s3, bucket_name, mock_data_file)
        # Update configuration with new username
        current_app.config["username"] = new_username

    return redirect(url_for("start"))  # Redirect to the 'start' endpoint


def process_transcript_pdf(path_to_pdf):
    """
    Process a transcript PDF file to extract cumulative GPA.
    """
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
    os.remove(path_to_pdf)  # Remove the PDF file after processing
    return cGPA

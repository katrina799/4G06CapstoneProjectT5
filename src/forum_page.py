"""
Filename: <forum_page.py>

Description:
    Handles forum operations for a web application. Enables users to post
    topics, submit comments, and manage image uploads. Integrates with AWS
    S3 for storing images and forum data. Supports topic filtering by tags and
    includes functionality for reversing topic order and searching within the
    forum.

Author: Chenwei Song
Created: 2024-01-23
Last Modified: 2024-04-03
"""

from flask import (
    Blueprint,
    render_template,
    current_app,
    request,
    redirect,
    url_for,
    abort,
)

try:
    from src.util import (
        get_df_from_csv_in_s3,
    )
except ImportError:
    from .util import (
        get_df_from_csv_in_s3,
    )

import botocore
import pandas as pd
from io import StringIO
from datetime import datetime
from werkzeug.utils import secure_filename

forum_blueprint = Blueprint("forum", __name__)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


@forum_blueprint.route("/forum_page", methods=["GET"])
def forum_page():

    user_data_file = current_app.config["USER_DATA_NAME"]
    topic_data_file = current_app.config["TOPIC_DATA_NAME"]
    comment_data_file = current_app.config["COMMENT_DATA_NAME"]

    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    current_app.config["current_page"] = "forum_page"
    current_tag = request.args.get("tag", "All")
    try:
        # Fetch topics, comments, and users data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)
        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)
        users_df = get_df_from_csv_in_s3(s3, bucket_name, user_data_file)

        if current_tag and current_tag != "All":
            topics_df = topics_df[topics_df["tag"] == current_tag]
        else:
            topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)

        # Ensure 'userId' in topics_df is the same type as 'userId' in users_df
        topics_df["userId"] = topics_df["userId"].astype(str)
        users_df["userId"] = users_df["userId"].astype(str)

        # Aggregate comments by topicId to count them
        comments_count = (
            comments_df.groupby("topicId")
            .size()
            .reset_index(name="comment_count")
        )

        # Merge topics with comments count based on topic ID
        topics_with_comments = pd.merge(
            topics_df,
            comments_count,
            how="left",
            left_on="id",
            right_on="topicId",
        ).fillna(0)

        # Merge topics with user data to get usernames
        topics_with_usernames = pd.merge(
            topics_with_comments,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )

        # Prepare the topics list as expected by the template
        topics = [
            (row.to_dict(), row["username"], int(row["comment_count"]))
            for _, row in topics_with_usernames.iterrows()
        ]
        topics = topics[::-1]

    except Exception as e:
        print(f"An error occurred while fetching forum data: {e}")
        topics = []

    return render_template(
        "forum_page.html",
        topics=topics,
        current_page=current_app.config["current_page"],
        username=current_app.config["username"],
        current_tag=current_tag,
    )


@forum_blueprint.route("/add_topic", methods=["GET", "POST"])
def add_topic():
    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    userId = current_app.config["userId"]

    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]

    current_app.config["current_page"] = "add_topic"

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        tag = request.form.get("tag")
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        image_url = None  # Or handle the case where there is no valid file

        if "image" in request.files:
            file = request.files["image"]
            if file and allowed_file(file.filename):
                print("yeah image")
                # Handle the file upload
                filename = secure_filename(file.filename)
                image_key = f"uploads/{filename}"
                s3.upload_fileobj(
                    file,
                    bucket_name,
                    image_key,
                    ExtraArgs={"ACL": "private"},
                )

                image_url = create_presigned_url(s3, bucket_name, image_key)

        # Fetch current topics DataFrame from S3
        topics_df = get_df_from_csv_in_s3(
            s3, bucket_name, current_app.config["TOPIC_DATA_NAME"]
        )
        if not topics_df.empty:
            topics_df["id"] = topics_df["id"].astype(
                int
            )  # Ensure 'id' is an integer
            new_id = topics_df["id"].max() + 1
        else:
            new_id = 1  # Start with 1 if there are no topics

        new_topic = pd.DataFrame(
            {
                "id": [new_id],  # Ensure 'id' is a string to match types.
                "title": [title],
                "description": [description],
                "userId": [
                    userId
                ],  # Convert userId to a list to match DataFrame structure.
                "tag": [tag],
                "imageUrl": [image_url],
                "date": [current_timestamp],
            }
        )

        topics_df["id"] = topics_df["id"].astype(str)

        # Use pd.concat for appending the new record
        updated_topics_df = pd.concat(
            [topics_df, new_topic], ignore_index=True
        )

        # Upload the updated DataFrame back to S3
        csv_buffer = StringIO()
        updated_topics_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=current_app.config["TOPIC_DATA_NAME"],
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )

        return redirect(url_for("forum.forum_page"))
    else:
        return render_template(
            "add_topic_page.html", current_page=current_page, username=username
        )


@forum_blueprint.route("/forum_page/reverse_order", methods=["POST"])
def reverse_forum_order():
    topics = current_app.config["topics"]
    # Assuming 'topics' is a global variable that stores your topics

    # Reverse the order of the topics
    current_app.config["topics"] = list(reversed(topics))

    # Redirect back to the forum page
    return redirect(url_for("forum.forum_page"))


@forum_blueprint.route("/fm/topic/<topic_id>", methods=["GET", "POST"])
def topic(topic_id):
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    comment_data_file = current_app.config["COMMENT_DATA_NAME"]

    username = current_app.config["username"]
    current_page = current_app.config["current_page"]
    current_app.config["current_page"] = "forum_topic"
    userId = current_app.config["userId"]

    if request.method == "POST":
        comment_text = request.form.get("comment")
        parent_id = request.form.get(
            "parentId", None
        )  # Might be part of the form if it's a reply
        layer = 0
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)

        # Determine layer based on parent_id
        if parent_id is not None and parent_id != "0":
            parent_comment = comments_df[
                comments_df["id"] == int(parent_id)
            ].iloc[0]
            layer = int(parent_comment["layer"]) + 1

        # Create new comment entry
        new_comment_id = (
            comments_df["id"].max() + 1 if not comments_df.empty else 1
        )
        new_comment = {
            "id": new_comment_id,
            "text": comment_text,
            "topicId": int(topic_id),
            "userId": userId,
            "parentId": parent_id if parent_id and parent_id != "0" else 0,
            "layer": layer,
            "date": [current_timestamp],
        }
        # Append new comment to the dataframe and update CSV
        new_comment_df = pd.DataFrame([new_comment])
        updated_comments_df = pd.concat(
            [comments_df, new_comment_df], ignore_index=True
        )
        csv_buffer = StringIO()
        updated_comments_df.to_csv(csv_buffer, index=False)
        s3.put_object(
            Bucket=bucket_name,
            Key=comment_data_file,
            Body=csv_buffer.getvalue(),
        )

        return redirect(url_for("forum.topic", topic_id=topic_id))
    # Initialize
    topic_dict = {}
    comments_with_usernames = []

    try:
        # Fetch all necessary data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, "topic_data.csv")
        topics_df["imageUrl"] = topics_df["imageUrl"].fillna("none")
        topics_df["imageUrl"] = topics_df["imageUrl"].astype(str)

        comments_df = get_df_from_csv_in_s3(
            s3, bucket_name, "comment_data.csv"
        )
        users_df = get_df_from_csv_in_s3(s3, bucket_name, "user_data.csv")

        # Fetch topic data
        topic_data = topics_df[topics_df["id"].astype(str) == str(topic_id)]
        if topic_data.empty:
            abort(404)  # Topic not found
        topic_dict = topic_data.iloc[0].to_dict()

        author_id = topic_dict["userId"]
        author_username = users_df[
            users_df["userId"].astype(str) == str(author_id)
        ].iloc[0]["username"]

        # Prepare comments with usernames
        comments_df = comments_df[
            comments_df["topicId"].astype(str) == str(topic_id)
        ]
        comments_with_users = pd.merge(
            comments_df,
            users_df,
            left_on="userId",
            right_on="userId",
            how="left",
        )

        comments_with_usernames = [
            (
                {
                    "text": row["text"],
                    "id": row["id"],
                    "parentId": row["parentId"],
                    "layer": row["layer"],
                    "date": row["date"],
                },
                row["username"],
            )
            for _, row in comments_with_users.iterrows()
        ]

        comment_hierarchy = build_comment_hierarchy(comments_with_usernames)

    except Exception as e:
        print(f"An error occurred: {e}")
        abort(500)

    return render_template(
        "forum_topic_page.html",
        topic=topic_dict,
        current_page=current_page,
        username=username,  # Assuming username is correctly set elsewhere
        author_username=author_username,
        comments=comment_hierarchy,
    )


@forum_blueprint.route("/search_forum")
def search():
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]

    user_data_file = current_app.config["USER_DATA_NAME"]
    topic_data_file = current_app.config["TOPIC_DATA_NAME"]
    comment_data_file = current_app.config["COMMENT_DATA_NAME"]

    current_app.config["current_page"] = "forum_page"
    query = request.args.get("query", "").strip()

    try:
        # Fetch topics and comments data from CSV
        topics_df = get_df_from_csv_in_s3(s3, bucket_name, topic_data_file)
        comments_df = get_df_from_csv_in_s3(s3, bucket_name, comment_data_file)
        users_df = get_df_from_csv_in_s3(s3, bucket_name, user_data_file)

        # Filter topics and comments based on the search query
        matching_topics = topics_df[
            topics_df["title"].str.contains(query, case=False, na=False)
            | topics_df["description"].str.contains(
                query, case=False, na=False
            )
        ]
        matching_comments = comments_df[
            comments_df["text"].str.contains(query, case=False, na=False)
        ]

        # Join matching topics and comments with user data to include usernames
        matching_topics_with_usernames = pd.merge(
            matching_topics,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )
        matching_comments_with_usernames = pd.merge(
            matching_comments,
            users_df[["userId", "username"]],
            how="left",
            left_on="userId",
            right_on="userId",
        )

        # Prepare results to pass to the template
        topics_results = matching_topics_with_usernames.to_dict(
            orient="records"
        )
        comments_results = [
            {
                "text": row["text"],
                "topicId": row["topicId"],
                "username": row["username"],
            }
            for _, row in matching_comments_with_usernames.iterrows()
        ]

        results = {"topics": topics_results, "comments": comments_results}
    except Exception as e:
        print(f"An error occurred while searching: {e}")
        results = {"topics": [], "comments": []}

    return render_template(
        "search_forum_results.html", results=results, query=query
    )


def build_comment_hierarchy(comments_with_usernames, parent_id=0, layer=0):
    """
    Flatten comment hierarchy into a list with context about each comment's
    layer,
    starting with top-level comments having parentId=0.
    Each item in the hierarchy list is a tuple: ((comment, username), layer).
    """
    hierarchy = []
    for comment_with_username in comments_with_usernames:
        comment, username = comment_with_username
        if comment["parentId"] == parent_id:
            # Add the comment with its layer information
            hierarchy.append(((comment, username), layer))
            # Recursively find and append replies, increasing the layer
            hierarchy += build_comment_hierarchy(
                comments_with_usernames, comment["id"], layer + 1
            )
    return hierarchy


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def create_presigned_url(s3, bucket_name, object_name, expiration=604800):
    try:
        response = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expiration,
        )
    except botocore.exceptions.ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None
    return response

"""
Filename: <app_grid.py>

Description:
    This file contains the implementation of the app icon grid functionality
    for MacONE.

Author: Qianni Wang
Created: 2024-02-14
Last Modified: 2024-04-04
"""
from flask import (
    Blueprint,
    current_app,
    request,
    jsonify,
)

import pandas as pd

# Attempt to import utility functions for S3 operations
try:
    from src.util import (
        get_df_from_csv_in_s3,
        write_order_csv_to_s3,
    )
except ImportError:
    from .util import (
        get_df_from_csv_in_s3,
        write_order_csv_to_s3,
    )

# Attempt to import utility functions for S3 operations
grid_blueprint = Blueprint("grid", __name__)


@grid_blueprint.route("/get-order")
def get_order():
    """
    Fetches and returns the current icon order for the logged-in user.
    
    This function retrieves the user's current icon order from an S3 CSV file. 
    If no specific order exists, it returns a default order.
    """
    # Extract necessary configuration and S3 client from app config
    bucket_name = current_app.config["BUCKET_NAME"]
    icon_order_path = current_app.config["ICON_ORDER_PATH"]
    s3 = current_app.config["S3_CLIENT"]
    username = current_app.config["username"]

    # Read current order from S3
    df = read_order_csv_from_s3(s3, username, bucket_name, icon_order_path)
    
    # Filter for current user's order
    filtered_df = df[df["username"] == username]

    # Provide default order if none is found
    if filtered_df.empty:
        existing_order = [3, 1, 11, 4, 2, 12, 8, 10, 6, 9, 5, 7]
    else:
        existing_order = filtered_df["orders"].iloc[0]

    return jsonify(existing_order)


@grid_blueprint.route("/update-order", methods=["POST"])
def update_order():
    """
    Updates the icon order for the logged-in user based on the received input.
    
    This function updates the user's icon order in the S3 CSV file based on the
    order specified in the request's JSON payload.
    """
    # Extract necessary configuration and S3 client from app config
    bucket_name = current_app.config["BUCKET_NAME"]
    s3 = current_app.config["S3_CLIENT"]
    new_orders = request.json
    username = current_app.config["username"]
    icon_order_path = current_app.config["ICON_ORDER_PATH"]

    # Fetch and update current orders
    df = get_df_from_csv_in_s3(s3, bucket_name, icon_order_path)

    if username in df["username"].values:
        df.loc[df["username"] == username, "orders"] = str(new_orders)
    else:
        new_row = pd.DataFrame(
            {"username": [username], "orders": [str(new_orders)]}
        )
        df = pd.concat([df, new_row], ignore_index=True)

    # Write updated orders back to S3
    write_order_csv_to_s3(s3, icon_order_path, df, bucket_name)

    return jsonify(
        {"status": "success", "message": "Order updated successfully."}
    )


def read_order_csv_from_s3(s3, username, bucket_name, key):
    """
    Reads and returns the order data from a CSV file stored in S3.
    
    Attempts to fetch the CSV file specified by the key from the S3 bucket.
    If the file doesn't exist, it creates a default order for the user.
    """
    icon_order_path = current_app.config["ICON_ORDER_PATH"]
    # Try to fetch the specified CSV file from S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        df = pd.read_csv(response["Body"])
        return df
    except s3.exceptions.NoSuchKey:
        # Handle missing file by creating a default order
        default_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        default_df = pd.DataFrame(
            [{"username": username, "orders": default_order}]
        )

        write_order_csv_to_s3(s3, icon_order_path, default_df, bucket_name)

        return default_df
    except Exception as e:
        # Log unexpected errors and return an empty DataFrame
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame(columns=["username", "orders"])

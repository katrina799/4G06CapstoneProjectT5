# Generate mock data for PoC
> **Important Note:**  
> Please ensure that you connect to the dev container first


To generate the mock data for PoC, please ensure that you connect to the dev container and then do the following steps:
- Navigate to the current directory by running `cd src\poc-data`
- Run the code `python3 generate_mock_data.py`

To upload the mock data to *AWS S3*, you need to generate mock data first. 
- Ensure that the environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set properly first so that you have access to *AWS S3*
- Navigate to the root directory `/workspaces/4G06CapstoneProjectT5`
- Run the code `python3 -m src.poc-data.upload_mock_data_to_s3`

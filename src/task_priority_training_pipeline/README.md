# Run training pipeline to upload a trained model to s3
> **Important Note:**  
> 1. Please ensure that you connect to the dev container first
> 2. Ensure that the environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set properly first so that you have access to *AWS S3*


To run the training pipeline and upload the trained model to S3:
- Navigate to the root directory by running `cd /workspaces/4G06CapstoneProjectT5`
- Run the code `python3 -m src.task_priority_training_pipeline.training_pipeline 'src/poc-data/task-priority-data/task_priority_data_cleaned.csv'`
    - Note that `'src/poc-data/task-priority-data/task_priority_data_cleaned.csv'` can be changed to other input data

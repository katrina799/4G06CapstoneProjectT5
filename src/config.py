# A configuration file where all constants are defined
BUCKET_NAME = "course-buddy"
MOCK_DATA_POC_NAME = "mock_data_poc.csv"
USER_DATA_NAME = "user_data.csv"
TOPIC_DATA_NAME = "topic_data.csv"
COMMENT_DATA_NAME = "comment_data.csv"
PRIORITY_MODEL_FILE_NAME = "trained_priority_model.joblib"
PRIORITY_MODEL_FILE_PATH = (
    f"src/task_priority_training_pipeline/{PRIORITY_MODEL_FILE_NAME}"
)
PRIORITY_MODEL_PATH = f"model/{PRIORITY_MODEL_FILE_NAME}"
MOCK_COURSE_INFO_CSV = "./poc-data/mock_course_info.csv"
MOCK_DATA_POC_TASKS = "mock_data_tasks.csv"
SQLALCHEMY_DATABASE_URI = "sqlite:///project.db"
TEMPLATES_AUTO_RELOAD = True
ICON_ORDER_PATH = "icon_order.csv"
COURSE_WORK_EXTRACTED_INFO = "./poc-data/extracted_course_works.csv"
TITLE_TO_COLUMN_MAPPING = {
    "Instructor Name": "instructor_name",
    "Instructor Email": "instructor_email",
    "Instructor Office Hour": "instructor_office_hour_list",
    "Required and Optional Textbook List": "textbooks",
    "Lecture Schedule List with Location": "lecture_schedule",
    "Tutorials Schedule List with Location": "tutorial_schedule",
    "Course Teaching Assistants (TAs) Name and Email List": "TAs",
    "Course Introduction": "course_introduction",
    "Course Goal/Mission": "goal_mission",
    "MSAF Policy": "MSAF",
}
UPLOAD_FOLDER = "poc-data/"
REGION_NAME = "us-east-2"

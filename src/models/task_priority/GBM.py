import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.ensemble import GradientBoostingClassifier


# Correct the paths if necessary
x_test_path = 'src/poc-data/task-priority-data/task_priority_x_test.csv'
x_train_path = 'src/poc-data/task-priority-data/task_priority_x_train.csv'
y_test_path = 'src/poc-data/task-priority-data/task_priority_y_test.csv'
y_train_path = 'src/poc-data/task-priority-data/task_priority_y_train.csv'

# Reading the CSV files into DataFrames
x_test_df = pd.read_csv(x_test_path)
x_train_df = pd.read_csv(x_train_path)
y_test_df = pd.read_csv(y_test_path)  
y_train_df = pd.read_csv(y_train_path)
# Initialize the Gradient Boosting Classifier
gbm = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)

# Fit the model with the training data
gbm.fit(x_train_df, y_train_df)

# Make predictions
y_pred_gbm = gbm.predict(x_test_df)

# Evaluate the model
print("Gradient Boosting Machine Accuracy:", accuracy_score(y_test_df, y_pred_gbm))
print("Confusion Matrix:\n", confusion_matrix(y_test_df, y_pred_gbm))
print("Classification Report:\n", classification_report(y_test_df, y_pred_gbm))

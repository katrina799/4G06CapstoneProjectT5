import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

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

# Flatten y to avoid shape issues, using .ravel()
y_train = y_train_df.values.ravel()
y_test = y_test_df.values.ravel()

# Initialize the Logistic Regression model
logreg = LogisticRegression(max_iter=1000)  # Increased max_iter for convergence

# Fit the model with the training data
logreg.fit(x_train_df, y_train)

# Make predictions
y_pred = logreg.predict(x_test_df)

# Evaluate the model
print("Accuracy:", accuracy_score(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
print("Classification Report:\n", classification_report(y_test, y_pred))

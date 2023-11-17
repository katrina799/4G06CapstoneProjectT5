import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Assuming the file paths are correct and the CSV files are in the expected format
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

# Initialize the Decision Tree Classifier
decision_tree = DecisionTreeClassifier()

# Fit the model with the training data
decision_tree.fit(x_train_df, y_train)

# Make predictions
y_pred = decision_tree.predict(x_test_df)

# Evaluate the model
print("Accuracy:", accuracy_score(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
print("Classification Report:\n", classification_report(y_test, y_pred))

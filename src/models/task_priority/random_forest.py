import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Load the data
x_test_path = 'src/poc-data/task-priority-data/task_priority_x_test.csv'
x_train_path = 'src/poc-data/task-priority-data/task_priority_x_train.csv'
y_test_path = 'src/poc-data/task-priority-data/task_priority_y_test.csv'
y_train_path = 'src/poc-data/task-priority-data/task_priority_y_train.csv'

x_test_df = pd.read_csv(x_test_path)
x_train_df = pd.read_csv(x_train_path)
y_test_df = pd.read_csv(y_test_path)  
y_train_df = pd.read_csv(y_train_path)

# Flatten y to avoid shape issues
y_train = y_train_df.values.ravel()
y_test = y_test_df.values.ravel()

# Initialize the Random Forest Classifier
random_forest = RandomForestClassifier(n_estimators=100, random_state=42)

# Fit the model with the training data
random_forest.fit(x_train_df, y_train)

# Make predictions
y_pred_rf = random_forest.predict(x_test_df)

# Evaluate the model
print("Random Forest Accuracy:", accuracy_score(y_test, y_pred_rf))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_rf))
print("Classification Report:\n", classification_report(y_test, y_pred_rf))

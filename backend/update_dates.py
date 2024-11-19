import pandas as pd
import os

# Path to your CSV file (adjusted to use the absolute path)
CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mlsnext-u13-fall.csv')

# Read the CSV file into a DataFrame
try:
    df = pd.read_csv(CSV_FILE)
    print("CSV file read successfully.")
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)

# Print the columns of the DataFrame
print("Columns in the DataFrame:")
print(df.columns)

# Check the first few rows to understand the date format
#print("Original Data:")
#print(df.head())

# Function to standardize date format
def standardize_date(date):
    try:
        return pd.to_datetime(date).strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Error converting date '{date}': {e}")
        return None  # Return None for invalid dates

# Apply the function to the date column (assuming the column is named 'date')
if 'Date' in df.columns:
    df['Date'] = df['Date'].apply(standardize_date)
else:
    print("Error: 'date' column not found in the CSV file.")
    exit(1)

# Check the updated DataFrame
print("Updated Data:")
print(df.head())

# Save the updated DataFrame back to the CSV file
try:
    df.to_csv(CSV_FILE, index=False)
    print("CSV file updated successfully.")
except Exception as e:
    print(f"Error saving CSV file: {e}") 
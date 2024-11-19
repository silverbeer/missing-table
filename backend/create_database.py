import pandas as pd
import sqlite3
import os

# Path to your CSV file
CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mlsnext-u13-fall.csv')
# Path to the SQLite database
DB_FILE = os.path.join(os.path.dirname(__file__), 'mlsnext_u13_fall.db')

# Debug output: Starting the database creation process
print("Starting the database creation process...")

# Check if the database file exists
if os.path.exists(DB_FILE):
    print(f"Database file '{DB_FILE}' already exists. Dropping the existing database.")
    os.remove(DB_FILE)  # Drop the existing database file

# Read the CSV file into a DataFrame
try:
    print(f"Reading CSV file: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE)
    print("CSV file read successfully.")
    print(f"DataFrame shape: {df.shape}")  # Output the shape of the DataFrame
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)

# Connect to SQLite database (it will create the database file if it doesn't exist)
try:
    print(f"Connecting to SQLite database: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    print("Connection to SQLite database established.")
    
    # Create teams table
    print("Creating 'teams' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL
        )
    ''')
    
    # Create games table with the correct column names
    print("Creating 'games' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            FOREIGN KEY (home_team) REFERENCES teams(name),
            FOREIGN KEY (away_team) REFERENCES teams(name)
        )
    ''')
    
    # Populate the teams table from the CSV file
    teams = df['home_team'].unique().tolist() + df['away_team'].unique().tolist()
    teams = list(set(teams))  # Remove duplicates
    for team in teams:
        conn.execute("INSERT INTO teams (name, city) VALUES (?, ?)", (team, "Unknown City"))  # Replace "Unknown City" with actual city if available
    
    # Create games table from DataFrame without renaming columns
    df.to_sql('games', conn, if_exists='replace', index=False)
    print("Table 'games' created and populated successfully.")
except Exception as e:
    print(f"Error connecting to SQLite database: {e}")
    exit(1)

# Commit the changes and close the connection
try:
    conn.commit()
    print("Changes committed to the database.")
except Exception as e:
    print(f"Error committing changes to the database: {e}")
finally:
    conn.close()
    print("Connection to SQLite database closed.")

print(f"Database '{DB_FILE}' created and populated with data from '{CSV_FILE}'.") 
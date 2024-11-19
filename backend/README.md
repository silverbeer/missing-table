# MLS Next Standings - Backend

This is the backend component of the MLS Next Standings application. It is built using FastAPI and interacts with a SQLite database to manage and serve game data.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Backend Setup](#backend-setup)
- [Database Setup](#database-setup)
- [Running the Backend](#running-the-backend)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [License](#license)

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.7 or higher
- SQLite (for the database)

## Backend Setup

1. **Navigate to the Backend Directory**:

   ```bash
   cd backend
   ```

2. **Create a Virtual Environment** (optional but recommended):

   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**:

   - On macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

4. **Install Required Python Packages**:

   ```bash
   pip install fastapi uvicorn pandas
   ```

## Database Setup

1. **Create the SQLite Database**:

   If you haven't already created the SQLite database, run the following command:

   ```bash
   python create_database.py
   ```

   This will read the `mlsnext-u13-fall.csv` file (if it exists) and create the `mlsnext_u13_fall.db` database.

   **Note**: Ensure that the CSV file is in the root directory of your project.

## Running the Backend

1. **Run the FastAPI Application**:

   ```bash
   uvicorn app:app --reload
   ```

   The backend will be running at `http://127.0.0.1:8000`.

## API Endpoints

### Get All Games

- **Endpoint**: `/api/games`
- **Method**: `GET`
- **Description**: Retrieves all games from the database.
- **Example Request**:
  ```
  GET http://127.0.0.1:8000/api/games
  ```

### Get Games by Team

- **Endpoint**: `/api/games`
- **Method**: `GET`
- **Query Parameter**: `team` (optional)
- **Description**: Retrieves games for a specific team.
- **Example Request**:
  ```
  GET http://127.0.0.1:8000/api/games?team=Bayside%20FC
  ```

## Testing

To run the backend tests, navigate to the `backend` directory and run:

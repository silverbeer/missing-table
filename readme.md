# MLS Next Standings

This project provides a web application to display standings for MLS Next games. It consists of a FastAPI backend and a Vue.js frontend.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [License](#license)

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.7 or higher
- Node.js and npm (for the frontend)
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

5. **Create the SQLite Database**:

   If you haven't already created the SQLite database, run the following command:

   ```bash
   python create_database.py
   ```

   This will read the `mlsnext-u13-fall.csv` file and create the `mlsnext_u13_fall.db` database.

## Frontend Setup

1. **Navigate to the Frontend Directory**:

   ```bash
   cd ../frontend
   ```

2. **Install Required Node Packages**:

   ```bash
   npm install
   ```

## Running the Application

### Start the Backend

1. **Navigate to the Backend Directory** (if not already there):

   ```bash
   cd backend
   ```

2. **Run the FastAPI Application**:

   ```bash
   uvicorn app:app --reload
   ```

   The backend will be running at `http://127.0.0.1:8000`.

### Start the Frontend

1. **Navigate to the Frontend Directory** (if not already there):

   ```bash
   cd ../frontend
   ```

2. **Run the Vue.js Application**:

   ```bash
   npm run serve
   ```

   The frontend will be running at `http://localhost:8080` (or another port if specified).

## Testing

### Backend Tests

To run the backend tests, navigate to the `backend` directory and run:

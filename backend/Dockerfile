# Use the official Python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy the project configuration
COPY pyproject.toml .

# Install dependencies using uv
RUN uv sync --frozen

# Copy the rest of the application code
COPY . .

# Create a volume for the database
VOLUME ["/app/data"]

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
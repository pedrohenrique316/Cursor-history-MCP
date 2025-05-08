# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size and --prefer-binary for faster installation where available
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy the rest of the application code (main.py, and .env if you use one) to the working directory
COPY . .

# Make port 8004 available to the world outside this container
# This is the port Uvicorn will run on inside the container
EXPOSE 8004

# Define environment variables that can be used by the application
# These can be overridden at runtime (e.g., with `docker run -e ...`)
# The LANCEDB_URI should match the mount point specified in the `docker run -v` command
ENV LANCEDB_URI="/data/cursor_chat_history.lancedb"
# OLLAMA_HOST defaults to host.docker.internal for Docker Desktop (Mac/Windows)
# For Linux hosts, you might need to change this to the host's IP or use Docker's host networking mode
ENV OLLAMA_HOST="http://host.docker.internal:11434"
# Ensures Python's print() statements are sent straight to terminal/logs
ENV PYTHONUNBUFFERED=1

# Command to run the application using Uvicorn
# Bind to 0.0.0.0 to make it accessible from outside the container (via the mapped port)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"] 
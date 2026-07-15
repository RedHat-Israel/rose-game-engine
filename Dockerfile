# --- Build Image ---
FROM registry.access.redhat.com/ubi9/python-39 AS build

WORKDIR /build

# Copy only the requirements file and install the Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime Image ---
FROM build

WORKDIR /app
COPY . /app

# Add the rose client package to the python path
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Default values for environment variables
ENV TRACK same
ENV PORT 8880

# Inform Docker that the container listens on port 8880
EXPOSE 8880

# Define the command to run your app using CMD which defines your runtime
CMD ["sh", "-c", "python main.py --listen 0.0.0.0 --track ${TRACK} --port ${PORT}"]

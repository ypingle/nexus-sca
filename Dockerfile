# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the Python script into the container
COPY nexussca.py .
COPY config.yaml . 
COPY requirements.txt . 
COPY /manifest-org/ ./manifest-org 

# Install the required packages using pip
RUN pip install -r requirements.txt

#install from nexus proxy
#RUN pip install -r requirements.txt --index http://ec2-44-237-156-85.us-west-2.compute.amazonaws.com:8081/repository/pypi-test/ --index-url http://ec2-44-237-156-85.us-west-2.compute.amazonaws.com:8081/repository/pypi-test/simple --trusted-host ec2-44-237-156-85.us-west-2.compute.amazonaws.com --no-cache-dir

# Set the command to run your Python script
CMD ["python", "nexussca.py"]

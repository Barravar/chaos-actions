FROM python:3.11-alpine

LABEL name="Chaos Actions" \
      maintainer="Barravar Inc. <barravar@barravar.com.br>" \
      repository="https://github.com/Barravar/chaos-actions"

WORKDIR /chaos-actions

# Copy application files
COPY requirements.txt .
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Python path to include src directory
ENV PYTHONPATH=/chaos-actions

# Run the application
ENTRYPOINT ["python", "-m", "src.main"]

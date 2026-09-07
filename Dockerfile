# Python starter example: adapt the image and commands to your project's stack.
FROM python:3.12.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Install your locked dependencies.
COPY requirements.lock requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy source and run as an unprivileged user.
RUN useradd --create-home --uid 10001 student
COPY --chown=student:student . .
USER student

# TODO: configure any writable data directories and required environment variables.
# TODO: expose your application's port, for example:
# EXPOSE 8080

# TODO: replace this placeholder with your application's startup command.
CMD ["python", "-c", "raise SystemExit('Template only: configure your application startup command in Dockerfile.')"]

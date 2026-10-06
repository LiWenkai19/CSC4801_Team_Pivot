# Installation Guide

## Prerequisites and Versions

The current backend uses Python 3.11 or later; the locked dependency set was
verified with Python 3.12.13 in the project's `SYManage` Conda environment.
It uses FastAPI, SQLModel, and PostgreSQL. Flask dependencies from the starter
remain in the lock file; Flask is not a required application framework.

## Dependency Installation

Run these commands from the repository root in your activated Python environment:

```sh
python -m pip install -r requirements.txt
python -m pip check
```

`requirements.txt` includes `requirements.lock`, which pins backend runtime,
test, and development dependencies, including the required package extras.
To install the backend as an editable package with the same locked versions:

```sh
python -m pip install -r requirements.txt -e "./backend[dev]"
```

## Environment Variables

## Database Setup and Migrations

## Demo Data and Reset Command

## Docker Build

## Docker Startup

## Local Development

## Running Unit Tests

## Troubleshooting

# GRC Weekly Report Pipeline

Automated pipeline for generating GRC (Governance, Risk & Compliance) weekly reports from Inbenta API data.

## Overview

This pipeline automates the process of:
1. Fetching data from Inbenta Reporting API
2. Storing data in SQLite database
3. Transforming data into hierarchical session structure
4. Generating formatted Excel reports

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file with your credentials (see `.env.example`)

## Usage

### Full Pipeline (most common)
```bash
python -m src.cli full-run --date-from 2026-01-18 --date-to 2026-01-24 --report-num 4
```

### Individual Steps
```bash
# Ingest data from API
python -m src.cli ingest --date-from 2026-01-18 --date-to 2026-01-24

# Transform ingested data
python -m src.cli transform --week-key 2026-W04

# Generate Excel report
python -m src.cli generate-report --week-key 2026-W04 --report-num 4
```

### Utilities
```bash
# List all sources and their exclusion status
python -m src.cli list-sources

# List available weeks in database
python -m src.cli list-weeks
```

## Project Structure

- `config/` - Configuration files
- `src/` - Source code
  - `api/` - API client, authentication, HMAC signing
  - `db/` - Database schema and operations
  - `ingestion/` - Data ingestion pipeline
  - `transform/` - Data transformation logic
  - `output/` - Excel report generation
  - `utils/` - Utility functions
- `tests/` - Unit and integration tests
- `data/` - Runtime data (gitignored)

## Configuration

Edit `config/config.yaml` to configure:
- API endpoints and credentials
- Source filters
- Database location
- Output settings

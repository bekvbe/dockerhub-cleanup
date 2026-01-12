# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DockerHub Cleanup Script is a Python tool for automating the cleanup of old and unused Docker image tags to manage DockerHub storage limits. It provides smart cleanup with tag preservation rules, dry-run capabilities, and comprehensive reporting.

## Commands

### Setup
```bash
pip install -r requirements.txt
```

### Running the Script
```bash
# Dry run (preview without deleting)
python3 dockerhub_cleanup.py \
  --dry-run \
  --namespace $DH_NAMESPACE \
  --username $DH_USERNAME \
  --pat $DH_PAT \
  --retention-days 90 \
  --preserve-last 10 \
  --preserve prod:10 staging:5

# Using test data (no API calls)
python3 dockerhub_cleanup.py \
  --namespace testnamespace \
  --username testuser \
  --pat dummy \
  --dry-run \
  --input-json tests/dockerhub_backup_mock.json
```

### Testing
```bash
# Run all tests
python -m unittest tests/e2e_test.py

# Run specific test
python -m unittest tests.e2e_test.TestDockerhubCleanupE2E.test_cleanup_dry_run
```

## Architecture

### Core Components

**dockerhub_cleanup.py** - Single-file script containing all functionality:

1. **Authentication** (`DockerHubAuth`)
   - Manages Docker Hub authentication using Personal Access Tokens (PAT)
   - Automatically generates short-lived JWT access tokens from PAT
   - Handles automatic token refresh when access tokens expire (401 errors)
   - Retries failed requests after token refresh

2. **API Integration** (`get_paginated_results`, `fetch_backup_data`)
   - Fetches repositories and tags from DockerHub API with pagination
   - Handles rate limiting with 1-second delays between requests
   - Falls back between namespace organization and user endpoints

3. **Tag Processing Logic** (`process_tags`)
   - Applies preservation rules (prefix-based with optional counts)
   - Enforces retention policy based on last_pulled dates
   - Sorts tags by last_updated_dt (newest first)
   - Returns tags with status (PRESERVED or TO DELETE) and reasons

4. **Preservation Rules System**
   - Format: `prefix:count` (e.g., `prod:10`) preserves top N matching tags
   - Format: `prefix` (no count) preserves all matching tags
   - If no `--preserve` rules provided, uses `--preserve-last` (default: 10)
   - Multiple rules can be combined

5. **Repository Filtering**
   - `--repos` for selective processing (overrides skip-repos)
   - `--skip-repos` for exclusion patterns (default: logspout)

6. **Date Parsing** (`parse_docker_date`)
   - Handles Docker Hub's variable fractional seconds (4-6 digits)
   - Normalizes timestamps for comparison

### Data Flow

1. Fetch or load repository/tag data (API or `--input-json`)
2. Filter repositories (--repos or --skip-repos)
3. For each repository:
   - Process tags with preservation rules
   - Write decisions to cleanup_report.csv
   - Delete tags marked TO DELETE (unless --dry-run)
4. Save backup to JSON (if fetched from API)

### Key Outputs

- **cleanup_report.csv** - Audit trail with Repository, Tag, Last Pulled, Last Updated, Status, Reason
- **dockerhub_backup.json** - Full tag metadata backup (when fetching from API)

### Testing Approach

E2E test uses mock JSON data (`tests/dockerhub_backup_mock.json`) to verify:
- Preservation rules work correctly
- Dry-run mode functions properly
- Tags marked for deletion are excluded from output

## Important Behavior

- Always backs up tag metadata before deletion (unless using --input-json)
- Rate limiting: 1-second sleep between API requests
- Preservation logic combines multiple conditions (prefix rules + pull recency)
- Tags can be preserved for multiple reasons simultaneously
- Script requires DockerHub PAT with read:write scope

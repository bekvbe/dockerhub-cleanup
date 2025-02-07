# DockerHub Cleanup Script

## Overview
The **DockerHub Cleanup Script** is a Python-based tool designed to manage and optimize DockerHub storage usage. With DockerHub enforcing a storage limit, this script automates the cleanup of old and unused Docker image tags to ensure compliance while retaining critical assets.

## Key Features:
- Dry-run mode (--dry-run) for previewing actions
- Comprehensive CSV report of decisions
- Full JSON backup of tag metadata
- Smart cleanup retaining critical and recent tags
- Support for selective repository processing (--repos)
- Handles pagination, rate limiting, and API error handling

## New Features:
- Added support for processing only selected repositories using the --repos argument (overrides skip-repos)
- Combined preservation rules: a tag prefix without a count preserves all matching tags; a tag prefix with a number (e.g., prod:10) preserves only the top n matching tags.

## Arguments:
- `--namespace`: Docker Hub namespace/organization.
- `--token`: Docker Hub PAT with read:write scope.
- `--dry-run`: Preview changes without deleting.
- `--backup-file`: Path to JSON backup file (default: dockerhub_backup.json).
- `--retention-days`: Days to retain tags (default: 90).
- `--preserve-last`: Global number of newest tags to preserve if no --preserve rules are provided (default: 10).
- `--skip-repos`: List of repository name prefixes to skip (default: logspout).
- `--preserve`: Preservation rules in the format prefix:number (e.g., prod:10 staging:5).
- `--input-json`: Path to JSON file with repository/tag data to use instead of pulling from the API. (great for testing)
- `--repos`: List of specific repositories to process (ignores --skip-repos).

## Purpose
This tool helps organizations reduce excessive DockerHub storage usage caused by outdated and infrequently accessed images. It ensures adherence to DockerHub's storage limits without compromising critical operations.

## Usage Scenarios
 **Compliance**: Stay within DockerHub's newest storage limit. 50 GB is the case with my Docker Team subscribtion.

**Cost Optimization**: Avoid unnecessary charges for overages.

**Storage Hygiene**: Maintain a clean and organized DockerHub repository.

## Target Audience
The script is tailored for DevOps engineers, platform teams, and organizations utilizing DockerHub for container image storage and distribution.

In my personal opinion, anyone who is already spending way too much on increased pricing of Docker.

### Outputs:
- `cleanup_report.csv` - Detailed audit trail

- `dockerhub_backup.json` - Full tag metadata backup

### Verification Steps:
Run with `--dry-run` and inspect CSV report
Check backup file for completeness
Test on a non-critical repository first!
Monitor Docker Hub storage metrics post-cleanup

## Usage
Generate PAT with read:write privileges at [Docker Settings](https://app.docker.com/settings/personal-access-tokens).

```bash
export DH_TOKEN="your_token"
export DH_NAMESPACE="your_organization"

python3 dockerhub_cleanup.py \
  --dry-run \
  --namespace $DH_NAMESPACE \
  --token $DH_TOKEN \
  --retention-days 90 \
  --preserve-last 10 \
  --preserve prod:10 staging:5 \
  --repos repo1 repo2
```
````

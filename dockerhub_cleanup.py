import argparse
import csv
import json
from datetime import datetime, timedelta
import time
import requests

# DockerHub API configuration
DH_API_BASE = "https://hub.docker.com/v2"

def parse_docker_date(date_str):
    """Parse Docker Hub's timestamp format with variable fractional seconds."""
    date_str = date_str.rstrip("Z")
    if "." in date_str:
        main_part, fractional = date_str.split(".", 1)
        # Pad fractional part to 6 digits (Docker uses 4-6 digits)
        fractional = fractional.ljust(6, "0")[:6]
    else:
        main_part = date_str
        fractional = "000000"
    return datetime.fromisoformat(f"{main_part}.{fractional}")

def parse_args():
    parser = argparse.ArgumentParser(description="Docker Hub Tag Cleanup Script")
    parser.add_argument("--namespace", required=True, help="Docker Hub namespace/organization")
    parser.add_argument("--token", required=True, help="Docker Hub PAT with read:write scope")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without deleting")
    parser.add_argument("--backup-file", default="dockerhub_backup.json", help="Backup file path (used when not providing --input-json)")
    parser.add_argument("--retention-days", type=int, default=90, help="Days to retain tags")
    parser.add_argument("--preserve-last", type=int, default=10,
                        help="Global number of newest tags to preserve if no --preserve rules are provided")
    parser.add_argument("--skip-repos", nargs="+", default=["logspout"],
                        help="List of repository name prefixes to skip (default: logspout)")
    parser.add_argument("--preserve", nargs="+", default=[],
                        help="List of preservation rules in format prefix:number (e.g., prod:10 staging:5)")
    parser.add_argument("--input-json", help="Path to JSON file with repository/tag data to use instead of pulling from the API")
    parser.add_argument("--repos", nargs="+", help="List of specific repositories to process (ignores skip-repos)")
    return parser.parse_args()

def get_paginated_results(url, headers, params=None):
    results = []
    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results.extend(data["results"])
        url = data.get("next")
        time.sleep(1)  # Rate limit protection
    return results

def process_tags(tags, retention_days, global_preserve_last, preserve_rules):
    """
    Process the tags list to compute parsed dates and determine preservation criteria.
    'preserve_rules' is a dict mapping a tag prefix to the number of tags to preserve for that prefix.
    If preserve_rules is empty, the global_preserve_last value is used.
    Returns a list of tag dictionaries with additional computed fields.
    """
    pull_cutoff = datetime.utcnow() - timedelta(days=retention_days)
    processed = []
    
    # Parse dates once and build a new collection with computed fields.
    for tag in tags:
        tag_name = tag.get("name")
        last_updated_str = tag.get("last_updated")
        last_updated_dt = parse_docker_date(last_updated_str)
        last_pulled_str = tag.get("tag_last_pulled")
        last_pulled_dt = parse_docker_date(last_pulled_str) if last_pulled_str and last_pulled_str != "0001-01-01T00:00:00Z" else None
        
        processed.append({
            "name": tag_name,
            "last_updated_str": last_updated_str,
            "last_updated_dt": last_updated_dt,
            "last_pulled_str": last_pulled_str,
            "last_pulled_dt": last_pulled_dt,
            "original": tag  # Preserve original data for backup
        })
    
    # Sort tags by last_updated_dt (newest first)
    processed.sort(key=lambda x: x["last_updated_dt"], reverse=True)
    
    # Prepare a dictionary to track preserved tags and their preservation reasons.
    preserved_reasons = {}
    
    if preserve_rules:
        for prefix, count in preserve_rules.items():
            matching = [tag for tag in processed if tag["name"].startswith(prefix)]
            if count is None:
                for tag in matching:
                    preserved_reasons[tag["name"]] = f"preserved all for prefix '{prefix}'"
            else:
                for tag in matching[:count]:
                    if tag["name"] not in preserved_reasons:
                        preserved_reasons[tag["name"]] = f"top {count} for prefix '{prefix}'"
    else:
        for tag in processed[:global_preserve_last]:
            if tag["name"] not in preserved_reasons:
                preserved_reasons[tag["name"]] = f"top {global_preserve_last} newest tags"
    
    for tag in processed:
        reasons = []
        if tag["name"] in preserved_reasons:
            reasons.append(preserved_reasons[tag["name"]])
        if tag["last_pulled_dt"] and tag["last_pulled_dt"] >= pull_cutoff:
            reasons.append(f"pulled within retention ({retention_days} days)")
        
        if reasons:
            tag["status"] = "PRESERVED"
            tag["reason"] = ", ".join(reasons)
        else:
            deletion_reasons = []
            if not tag["last_pulled_dt"]:
                deletion_reasons.append("never pulled")
            else:
                deletion_reasons.append(f"not pulled since {pull_cutoff.isoformat()}")
            tag["status"] = "TO DELETE"
            tag["reason"] = ", ".join(deletion_reasons)
    
    return processed

def process_repository(repo_name, tags, args, preserve_rules, headers, writer):
    processed_tags = process_tags(tags, args.retention_days, args.preserve_last, preserve_rules)
    for tag in processed_tags:
        writer.writerow([
            repo_name,
            tag["name"],
            tag["last_pulled_str"],
            tag["last_updated_str"],
            tag["status"],
            tag["reason"]
        ])
        if tag["status"] == "TO DELETE":
            if args.dry_run:
                print(f"[Dry Run] Would delete {repo_name}:{tag['name']}")
            else:
                delete_url = f"{DH_API_BASE}/repositories/{args.namespace}/{repo_name}/tags/{tag['name']}/"
                try:
                    response = requests.delete(delete_url, headers=headers)
                    response.raise_for_status()
                    print(f"Deleted {repo_name}:{tag['name']}")
                    time.sleep(1)
                except requests.HTTPError as e:
                    print(f"Failed to delete {repo_name}:{tag['name']} - {str(e)}")

def fetch_backup_data(args, headers):
    backup_data = {}
    try:
        repos_url = f"{DH_API_BASE}/repositories/{args.namespace}/"
        repos = get_paginated_results(repos_url, headers)
    except requests.HTTPError:
        repos_url = f"{DH_API_BASE}/users/{args.namespace}/repositories/"
        repos = get_paginated_results(repos_url, headers)
    
    for repo_data in repos:
        repo_name = repo_data["name"]
        # If --repos is provided, process only specified repos; otherwise, use skip-repos filtering.
        if args.repos:
            if repo_name not in args.repos:
                continue
        else:
            if any(repo_name.startswith(prefix) for prefix in args.skip_repos):
                print(f"Skipping repository: {repo_name}")
                continue
        tags_url = f"{DH_API_BASE}/repositories/{args.namespace}/{repo_name}/tags/"
        try:
            tags = get_paginated_results(tags_url, headers)
        except requests.HTTPError as e:
            print(f"Error fetching tags for {repo_name}: {str(e)}")
            continue
        backup_data[repo_name] = tags
    return backup_data

def load_backup_data(args):
    with open(args.input_json, "r") as f:
        return json.load(f)

def get_backup_data(args, headers):
    if args.input_json:
        print(f"Loading backup data from {args.input_json} ...")
        return load_backup_data(args)
    else:
        return fetch_backup_data(args, headers)

def main():
    args = parse_args()
    
    # Parse the preservation rules into a dictionary.
    # Expected format: prefix:number (e.g., prod:10 staging:5)
    preserve_rules = {}
    for rule in args.preserve:
        if ":" in rule:
            prefix, count = rule.split(":", 1)
            preserve_rules[prefix] = int(count)
        else:
            preserve_rules[rule] = None

    headers = {"Authorization": f"Bearer {args.token}"}
    
    with open("cleanup_report.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Repository", "Tag", "Last Pulled", "Last Updated", "Status", "Reason"])
        
        backup_data = get_backup_data(args, headers)
        
        # Filter backup_data if specific repositories are provided via --repos
        if args.repos:
            backup_data = {repo: tags for repo, tags in backup_data.items() if repo in args.repos}
            if not backup_data:
                print("No matching repositories found in backup data for the provided --repos argument.")
                return
        
        # Process each repository's backup data; use skip-repos only when --repos is not provided.
        for repo_name, tags in backup_data.items():
            if not args.repos and any(repo_name.startswith(prefix) for prefix in args.skip_repos):
                print(f"Skipping repository: {repo_name}")
                continue
            process_repository(repo_name, tags, args, preserve_rules, headers, writer)
        
        # Save backup data if it was fetched from the API.
        if not args.input_json:
            with open(args.backup_file, "w") as f:
                json.dump(backup_data, f, indent=2)
            print(f"Backup saved to {args.backup_file}")

if __name__ == "__main__":
    main()

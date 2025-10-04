#!/usr/bin/env python3
"""
List AWS resources for a given service and region.

Supported services (so far):
  - ec2        : EC2 instances
  - s3         : S3 buckets (filtered by their location)
  - dynamodb   : DynamoDB tables
  - rds        : RDS DB instances
  - lambda     : Lambda functions

Requires: boto3
"""

import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any

import boto3
from botocore.exceptions import (
    NoCredentialsError,
    PartialCredentialsError,
    ClientError,
    EndpointConnectionError,
    UnknownServiceError,
    NoRegionError,
    ParamValidationError,
)

# -------- Helpers -------- #

def human_ts(dt: Any) -> str:
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)

def print_header(title: str):
    print("=" * len(title))
    print(title)
    print("=" * len(title))

def print_table(rows: List[List[str]], headers: List[str]):
    if not rows:
        print("(no resources found)")
        return
    # compute column widths
    widths = [len(h) for h in headers]
    for r in rows:
        for i, col in enumerate(r):
            widths[i] = max(widths[i], len(col))

    # header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)

    # rows
    for r in rows:
        print(" | ".join(r[i].ljust(widths[i]) for i in range(len(headers))))

def fail(msg: str, code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)

def get_session(profile: str = None, region: str = None):
    try:
        if profile:
            return boto3.Session(profile_name=profile, region_name=region)
        return boto3.Session(region_name=region)
    except (NoRegionError,) as e:
        fail(f"{e}")
    except Exception as e:
        fail(f"Failed to initialize AWS session: {e}")

# -------- Service handlers -------- #

def list_ec2(session, region: str):
    """List EC2 instances in region."""
    ec2 = session.client("ec2", region_name=region)
    paginator = ec2.get_paginator("describe_instances")
    rows = []
    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                inst_id = inst.get("InstanceId", "")
                inst_type = inst.get("InstanceType", "")
                state = (inst.get("State") or {}).get("Name", "")
                az = (inst.get("Placement") or {}).get("AvailabilityZone", "")
                launch = human_ts(inst.get("LaunchTime"))
                # Try to get Name tag
                name = ""
                for t in inst.get("Tags", []) or []:
                    if t.get("Key") == "Name":
                        name = t.get("Value", "")
                        break
                rows.append([inst_id, state, inst_type, az, launch, name])
    print_header(f"EC2 Instances in {region}")
    print_table(rows, ["InstanceId", "State", "Type", "AZ", "LaunchTime", "Name"])

def list_s3(session, region: str):
    """
    List S3 buckets whose bucket location matches the requested region.
    Note: S3 is a global service; each bucket has its own location.
    """
    s3 = session.client("s3")
    rows = []
    resp = s3.list_buckets()
    buckets = resp.get("Buckets", [])
    for b in buckets:
        name = b.get("Name")
        # Get bucket location
        try:
            loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint")
            # AWS quirk: us-east-1 is reported as None
            bucket_region = loc or "us-east-1"
        except ClientError as e:
            # If access denied to a bucket, skip it gracefully
            continue
        if bucket_region == region:
            created = human_ts(b.get("CreationDate"))
            rows.append([name, bucket_region, created])
    print_header(f"S3 Buckets in {region}")
    print_table(rows, ["BucketName", "Region", "CreationDate"])

def list_dynamodb(session, region: str):
    """List DynamoDB tables in region."""
    ddb = session.client("dynamodb", region_name=region)
    paginator = ddb.get_paginator("list_tables")
    rows = []
    for page in paginator.paginate():
        for table in page.get("TableNames", []):
            try:
                desc = ddb.describe_table(TableName=table)["Table"]
                status = desc.get("TableStatus", "")
                items = str(desc.get("ItemCount", ""))
                size = str(desc.get("TableSizeBytes", ""))
                rows.append([table, status, items, size])
            except ClientError:
                rows.append([table, "(access denied)", "", ""])
    print_header(f"DynamoDB Tables in {region}")
    print_table(rows, ["TableName", "Status", "ItemCount", "SizeBytes"])

def list_rds(session, region: str):
    """List RDS DB instances in region."""
    rds = session.client("rds", region_name=region)
    paginator = rds.get_paginator("describe_db_instances")
    rows = []
    for page in paginator.paginate():
        for db in page.get("DBInstances", []):
            ident = db.get("DBInstanceIdentifier", "")
            eng = db.get("Engine", "")
            cls = db.get("DBInstanceClass", "")
            status = db.get("DBInstanceStatus", "")
            endpoint = (db.get("Endpoint") or {}).get("Address", "")
            created = human_ts(db.get("InstanceCreateTime"))
            rows.append([ident, eng, cls, status, endpoint, created])
    print_header(f"RDS DB Instances in {region}")
    print_table(rows, ["Identifier", "Engine", "Class", "Status", "Endpoint", "Created"])

def list_lambda(session, region: str):
    """List Lambda functions in region."""
    lam = session.client("lambda", region_name=region)
    paginator = lam.get_paginator("list_functions")
    rows = []
    for page in paginator.paginate():
        for fn in page.get("Functions", []):
            name = fn.get("FunctionName", "")
            runtime = fn.get("Runtime", "")
            ver = fn.get("Version", "")
            last_mod = fn.get("LastModified", "")
            rows.append([name, runtime, ver, last_mod])
    print_header(f"Lambda Functions in {region}")
    print_table(rows, ["FunctionName", "Runtime", "Version", "LastModified"])

SUPPORTED = {
    "ec2": list_ec2,
    "s3": list_s3,
    "dynamodb": list_dynamodb,
    "rds": list_rds,
    "lambda": list_lambda,
}

# -------- Main -------- #

def main():
    parser = argparse.ArgumentParser(
        description="List AWS resources for a given service and region."
    )
    parser.add_argument("service", help=f"Service name (one of: {', '.join(sorted(SUPPORTED.keys()))})")
    parser.add_argument("region", help="AWS region code (e.g., us-east-1, eu-west-1)")
    parser.add_argument("--profile", help="AWS CLI profile to use (optional)")
    args = parser.parse_args()

    service = args.service.lower().strip()
    region = args.region.strip()

    if service not in SUPPORTED:
        fail(
            f"Unsupported service '{service}'. "
            f"Supported: {', '.join(sorted(SUPPORTED.keys()))}"
        )

    # Initialize session (credentials/region taken from args or env/config)
    session = get_session(profile=args.profile, region=region)

    try:
        SUPPORTED[service](session, region)
        return 0
    except NoCredentialsError:
        fail("No AWS credentials found. Configure credentials via environment variables or AWS config files.")
    except PartialCredentialsError:
        fail("Partial AWS credentials found. Please complete your AWS credential configuration.")
    except EndpointConnectionError as e:
        fail(f"Could not connect to endpoint for region '{region}'. Is the region correct? Details: {e}")
    except UnknownServiceError:
        fail(f"The AWS SDK does not recognize service '{service}'.")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        fail(f"AWS API error ({code}): {msg}")
    except ParamValidationError as e:
        fail(f"Invalid parameter(s): {e}")
    except KeyboardInterrupt:
        fail("Interrupted by user.", code=130)
    except Exception as e:
        fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    sys.exit(main())
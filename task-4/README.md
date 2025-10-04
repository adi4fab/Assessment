# AWS Resource Lister

A simple, user-friendly CLI to list resources for a given **AWS service** in a specified **region**.  
It prints a clean table with relevant details and handles errors gracefully.

## Supported Services
- `ec2` — lists EC2 instances (ID, state, type, AZ, launch time, Name tag)
- `s3` — lists S3 buckets **located in the specified region** (S3 is global; each bucket has its own region)
- `dynamodb` — lists DynamoDB tables (status, item count, size)
- `rds` — lists RDS DB instances (identifier, engine, class, status, endpoint)
- `lambda` — lists Lambda functions (name, runtime, version, last modified)

## Prerequisites

- Python 3.8+
- [boto3](https://pypi.org/project/boto3/)

Install dependencies:
```bash
pip install boto3
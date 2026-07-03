"""Shared AWS session management."""

_NO_CREDENTIALS_MSG = """
No AWS credentials found. cordless looks for credentials in the standard places:

  1. Environment variables
       export AWS_ACCESS_KEY_ID=...
       export AWS_SECRET_ACCESS_KEY=...
       export AWS_SESSION_TOKEN=...   # if using temporary credentials / SSO

  2. ~/.aws/credentials file (via `aws configure`)
       Stores keys on disk with proper file permissions, not in shell history.

  3. AWS IAM Identity Center (SSO) — recommended
       Set up a profile with `aws configure sso`, then log in with:
       aws sso login --profile your-profile
       and set AWS_PROFILE=your-profile (or pass --profile to aws commands).

Get your credentials from:
  AWS Console → your account name (top right) → Security credentials → Access keys

Once configured, re-run: cordless deploy
"""


def get_session(region=None):
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        raise SystemExit(
            "boto3 is required for AWS operations.\n"
            "Install it: pip install boto3  or  uv add boto3"
        )

    session = boto3.Session(region_name=region)

    try:
        session.client("sts").get_caller_identity()
        return session
    except NoCredentialsError:
        raise SystemExit(_NO_CREDENTIALS_MSG)
    except ClientError as exc:
        raise SystemExit(f"AWS credential error: {exc}")

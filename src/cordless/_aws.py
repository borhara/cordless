"""Shared AWS session management with credential prompting."""


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
    except (NoCredentialsError, ClientError):
        pass

    print("No AWS credentials found. Enter them now (or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY):")
    access_key = input("  AWS Access Key ID: ").strip()
    secret_key = input("  AWS Secret Access Key: ").strip()
    if not region:
        region = input("  AWS Region (e.g. eu-west-2): ").strip()

    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    try:
        session.client("sts").get_caller_identity()
    except (NoCredentialsError, ClientError) as exc:
        raise SystemExit(f"AWS credential validation failed: {exc}")

    return session

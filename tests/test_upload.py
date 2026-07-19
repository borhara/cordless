"""cordless upload: publish a layer and attach it to an existing function."""

import json
import os
import zipfile

import boto3
import pytest
from moto import mock_aws

import cordless.upload as upload

REGION = "us-east-1"

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


def _minimal_zip(tmp_path):
    p = tmp_path / "fn.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("lambda_function.py", "def handler(event, context): pass\n")
    return str(p)


def _make_role(iam, name="test-role"):
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
            ],
        }
    )
    return iam.create_role(RoleName=name, AssumeRolePolicyDocument=trust)["Role"]["Arn"]


def _make_function(lam, name, role_arn, zip_path, layers=None):
    with open(zip_path, "rb") as f:
        kwargs = {
            "FunctionName": name,
            "Runtime": "python3.12",
            "Role": role_arn,
            "Handler": "lambda_function.handler",
            "Code": {"ZipFile": f.read()},
        }
        if layers:
            kwargs["Layers"] = layers
        return lam.create_function(**kwargs)["FunctionArn"]


@pytest.fixture
def aws_clients():
    with mock_aws():
        yield {
            "iam": boto3.client("iam", region_name=REGION),
            "lam": boto3.client("lambda", region_name=REGION),
        }


def test_upload_publishes_layer_and_attaches_it_to_the_function(aws_clients, tmp_path):
    role_arn = _make_role(aws_clients["iam"])
    _make_function(aws_clients["lam"], "my-fn", role_arn, _minimal_zip(tmp_path))

    upload.upload("my-fn", "my-layer", REGION, python_version="3.12")

    config = aws_clients["lam"].get_function_configuration(FunctionName="my-fn")
    layer_arns = [layer["Arn"] for layer in config["Layers"]]
    assert len(layer_arns) == 1
    assert ":layer:my-layer:" in layer_arns[0]


def test_upload_uses_explicit_python_version_as_compatible_runtime(aws_clients, tmp_path):
    role_arn = _make_role(aws_clients["iam"])
    _make_function(aws_clients["lam"], "my-fn", role_arn, _minimal_zip(tmp_path))

    upload.upload("my-fn", "my-layer", REGION, python_version="3.12")

    version = aws_clients["lam"].list_layer_versions(LayerName="my-layer")["LayerVersions"][0]
    assert version["CompatibleRuntimes"] == ["python3.12"]


def test_upload_falls_back_to_known_runtimes_when_no_python_version_given(aws_clients, tmp_path):
    role_arn = _make_role(aws_clients["iam"])
    _make_function(aws_clients["lam"], "my-fn", role_arn, _minimal_zip(tmp_path))

    upload.upload("my-fn", "my-layer", REGION)

    version = aws_clients["lam"].list_layer_versions(LayerName="my-layer")["LayerVersions"][0]
    assert version["CompatibleRuntimes"] == upload._LAMBDA_RUNTIMES


def test_upload_replaces_older_version_of_the_same_layer_instead_of_stacking(aws_clients, tmp_path):
    """A function already carrying an old version of `my-layer` (plus an
    unrelated layer) should end up with just the unrelated layer and the new
    version - not both versions of my-layer attached at once."""
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)

    other_layer_arn = lam.publish_layer_version(
        LayerName="unrelated-layer", Content={"ZipFile": b"stub"}, CompatibleRuntimes=["python3.12"]
    )["LayerVersionArn"]
    old_arn = lam.publish_layer_version(
        LayerName="my-layer", Content={"ZipFile": b"stub"}, CompatibleRuntimes=["python3.12"]
    )["LayerVersionArn"]

    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path), layers=[other_layer_arn, old_arn])

    upload.upload("my-fn", "my-layer", REGION, python_version="3.12")

    config = lam.get_function_configuration(FunctionName="my-fn")
    layer_arns = [layer["Arn"] for layer in config["Layers"]]
    assert other_layer_arn in layer_arns
    assert old_arn not in layer_arns
    assert len(layer_arns) == 2  # unrelated-layer + the new my-layer version

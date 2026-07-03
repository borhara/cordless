import json
import os
import tempfile
import time
import zipfile

try:
    import tomllib
except ImportError:
    tomllib = None

_EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", ".git", "node_modules", ".mypy_cache", ".ruff_cache"}
_EXCLUDE_FILES = {".env", "cordless.toml"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo")

_LAMBDA_TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})
_LAMBDA_BASIC_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
_SQS_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole"


def load_config(source_dir):
    if tomllib is None:
        return {}
    path = os.path.join(source_dir, "cordless.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f).get("deploy", {})


def build_function_zip(source_dir, bundle_cordless=False):
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for fname in files:
                if fname in _EXCLUDE_FILES or fname.endswith(_EXCLUDE_SUFFIXES):
                    continue
                abs_path = os.path.join(root, fname)
                zf.write(abs_path, os.path.relpath(abs_path, source_dir))

        if bundle_cordless:
            from .upload import _cordless_package_dir
            pkg_dir = _cordless_package_dir()
            pkg_parent = os.path.dirname(pkg_dir)
            for root, dirs, files in os.walk(pkg_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    abs_path = os.path.join(root, fname)
                    zf.write(abs_path, os.path.relpath(abs_path, pkg_parent))

    return tmp.name


def ensure_iam_role(iam, role_name):
    try:
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"  Creating IAM role '{role_name}'...", flush=True)
    role_arn = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=_LAMBDA_TRUST_POLICY,
    )["Role"]["Arn"]

    iam.attach_role_policy(RoleName=role_name, PolicyArn=_LAMBDA_BASIC_EXECUTION_POLICY)

    # IAM is eventually consistent — Lambda rejects a brand-new role for ~10 s
    print("  Waiting for IAM role to propagate...", flush=True)
    time.sleep(12)

    return role_arn


def _cordless_version():
    from importlib.metadata import version
    return version("cordless")


def _publish_cordless_layer(lam, layer_name):
    from .upload import build_layer_zip, _LAMBDA_RUNTIMES

    current_version = _cordless_version()
    description = f"cordless {current_version}"

    # Reuse the existing layer version if it was built from the same cordless version
    try:
        versions = lam.list_layer_versions(LayerName=layer_name).get("LayerVersions", [])
        for v in versions:
            if v.get("Description") == description:
                print(f"  Layer already up to date ({description}), reusing.", flush=True)
                return v["LayerVersionArn"]
    except lam.exceptions.ResourceNotFoundException:
        pass

    zip_path = build_layer_zip()
    try:
        with open(zip_path, "rb") as f:
            resp = lam.publish_layer_version(
                LayerName=layer_name,
                Description=description,
                Content={"ZipFile": f.read()},
                CompatibleRuntimes=_LAMBDA_RUNTIMES,
            )
        return resp["LayerVersionArn"]
    finally:
        os.unlink(zip_path)


def _function_exists(lam, function_name):
    try:
        config = lam.get_function_configuration(FunctionName=function_name)
        return True, config["FunctionArn"]
    except lam.exceptions.ResourceNotFoundException:
        return False, None


def _env_vars(env):
    return {"Variables": env} if env else {}


def _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn, env, timeout=10):
    with open(zip_path, "rb") as f:
        resp = lam.create_function(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": f.read()},
            Layers=[layer_arn] if layer_arn else [],
            Environment=_env_vars(env),
            Timeout=timeout,
        )
    lam.get_waiter("function_active").wait(FunctionName=function_name)
    return resp["FunctionArn"]


def _update_function(lam, function_name, zip_path, handler, layer_arn, env, timeout=10):
    with open(zip_path, "rb") as f:
        lam.update_function_code(FunctionName=function_name, ZipFile=f.read())
    lam.get_waiter("function_updated").wait(FunctionName=function_name)

    lam.update_function_configuration(
        FunctionName=function_name,
        Handler=handler,
        Layers=[layer_arn] if layer_arn else [],
        Environment=_env_vars(env),
        Timeout=timeout,
    )
    lam.get_waiter("function_updated").wait(FunctionName=function_name)


def _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id):
    api_name = f"{function_name}-api"

    # Reuse existing API if one with this name exists
    apis = apigw.get_apis().get("Items", [])
    existing = next((a for a in apis if a["Name"] == api_name), None)

    if existing:
        api_id = existing["ApiId"]
        endpoint = existing["ApiEndpoint"]
    else:
        api = apigw.create_api(Name=api_name, ProtocolType="HTTP")
        api_id = api["ApiId"]
        endpoint = api["ApiEndpoint"]

        integration = apigw.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationUri=function_arn,
            PayloadFormatVersion="2.0",
        )

        apigw.create_route(
            ApiId=api_id,
            RouteKey="POST /",
            Target=f"integrations/{integration['IntegrationId']}",
        )

        apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)

    # Always refresh the Lambda invoke permission for this API
    source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*"
    try:
        lam.remove_permission(FunctionName=function_name, StatementId="APIGatewayInvoke")
    except lam.exceptions.ResourceNotFoundException:
        pass

    lam.add_permission(
        FunctionName=function_name,
        StatementId="APIGatewayInvoke",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=source_arn,
    )

    return f"{endpoint}/"


def _ensure_sqs_queue(sqs, queue_name):
    try:
        url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    except sqs.exceptions.QueueDoesNotExist:
        print(f"  Creating SQS queue '{queue_name}'...", flush=True)
        url = sqs.create_queue(
            QueueName=queue_name,
            Attributes={"VisibilityTimeout": "60"},
        )["QueueUrl"]

    arn = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    return url, arn


def _attach_defer_policies(iam, role_name, queue_arn):
    # Worker needs receive/delete; main Lambda needs send — attach both to shared role
    attached = {
        p["PolicyArn"]
        for p in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
    }
    if _SQS_EXECUTION_POLICY not in attached:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=_SQS_EXECUTION_POLICY)

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="cordless-sqs-send",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
            }],
        }),
    )


def _ensure_sqs_trigger(lam, worker_name, queue_arn):
    existing = lam.list_event_source_mappings(
        EventSourceArn=queue_arn,
        FunctionName=worker_name,
    ).get("EventSourceMappings", [])

    if existing:
        return

    print(f"  Creating SQS trigger for '{worker_name}'...", flush=True)
    lam.create_event_source_mapping(
        EventSourceArn=queue_arn,
        FunctionName=worker_name,
        BatchSize=1,
        FunctionResponseTypes=["ReportBatchItemFailures"],
    )


def deploy(function_name, role_name, handler, source_dir, runtime, layer_name, env, region,
           timeout=10, bundle_cordless=False, defer_worker=None,
           defer_handler="lambda_function.worker_handler", defer_timeout=30):
    if not function_name:
        raise SystemExit("Function name is required — pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session

    session = get_session(region)
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    sqs = session.client("sqs")
    account_id = session.client("sts").get_caller_identity()["Account"]

    print("Setting up IAM role...", flush=True)
    role_arn = ensure_iam_role(iam, role_name)
    print(f"  {role_arn}", flush=True)

    if bundle_cordless:
        print("Bundling local cordless into function zip...", flush=True)
        layer_arn = None
    else:
        print("Publishing cordless layer...", flush=True)
        layer_arn = _publish_cordless_layer(lam, layer_name)
        print(f"  {layer_arn}", flush=True)

    print("Packaging function code...", flush=True)
    zip_path = build_function_zip(source_dir, bundle_cordless=bundle_cordless)

    try:
        exists, function_arn = _function_exists(lam, function_name)
        if exists:
            print(f"Updating '{function_name}'...", flush=True)
            _update_function(lam, function_name, zip_path, handler, layer_arn or "", env, timeout=timeout)
        else:
            print(f"Creating '{function_name}'...", flush=True)
            function_arn = _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn or "", env, timeout=timeout)
    finally:
        os.unlink(zip_path)

    print("Setting up API Gateway...", flush=True)
    url = _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id)

    if defer_worker:
        queue_name = f"{function_name}-defer"
        print(f"Setting up deferred dispatch (SQS + worker Lambda)...", flush=True)

        queue_url, queue_arn = _ensure_sqs_queue(sqs, queue_name)
        print(f"  Queue: {queue_url}", flush=True)

        _attach_defer_policies(iam, role_name, queue_arn)
        print(f"  IAM policies attached.", flush=True)

        # Inject queue URL into main Lambda env
        merged_env = {**env, "CORDLESS_QUEUE_URL": queue_url}
        lam.update_function_configuration(
            FunctionName=function_name,
            Environment=_env_vars(merged_env),
        )
        lam.get_waiter("function_updated").wait(FunctionName=function_name)

        worker_zip = build_function_zip(source_dir, bundle_cordless=bundle_cordless)
        try:
            w_exists, _ = _function_exists(lam, defer_worker)
            if w_exists:
                print(f"  Updating worker '{defer_worker}'...", flush=True)
                _update_function(lam, defer_worker, worker_zip, defer_handler, layer_arn, {}, timeout=defer_timeout)
            else:
                print(f"  Creating worker '{defer_worker}'...", flush=True)
                _create_function(lam, defer_worker, worker_zip, role_arn, defer_handler, runtime, layer_arn, {}, timeout=defer_timeout)
        finally:
            os.unlink(worker_zip)

        _ensure_sqs_trigger(lam, defer_worker, queue_arn)
        print(f"  Worker ready.", flush=True)

    print(f"\nDeployed. Paste this into Discord as your Interactions Endpoint URL:\n\n  {url}\n", flush=True)

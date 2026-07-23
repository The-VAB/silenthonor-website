"""GitHub webhook receiver: verifies the push event came from GitHub and
starts the deploy pipeline. Stands in for the CodeStarConnection's automatic
DetectChanges trigger, which relies on the AWS-managed GitHub App -- not
installable on this org, so this plain repo webhook supplies the same signal.
"""
import base64
import hashlib
import hmac
import json
import os

import boto3

codepipeline = boto3.client("codepipeline")
secretsmanager = boto3.client("secretsmanager")

PIPELINE_NAME = os.environ["PIPELINE_NAME"]
BRANCH = os.environ["BRANCH"]
WEBHOOK_SECRET_ARN = os.environ["WEBHOOK_SECRET_ARN"]


def _verify_signature(secret, raw_body, signature_header):
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def handler(event, _context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    raw_body = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()

    secret = secretsmanager.get_secret_value(SecretId=WEBHOOK_SECRET_ARN)["SecretString"]
    if not _verify_signature(secret, raw_body, headers.get("x-hub-signature-256")):
        return {"statusCode": 401, "body": "invalid signature"}

    event_type = headers.get("x-github-event")
    if event_type == "ping":
        return {"statusCode": 200, "body": "pong"}
    if event_type != "push":
        return {"statusCode": 200, "body": f"ignored event: {event_type}"}

    payload = json.loads(raw_body)
    if payload.get("ref") != f"refs/heads/{BRANCH}" or payload.get("deleted"):
        return {"statusCode": 200, "body": f"ignored ref: {payload.get('ref')}"}

    resp = codepipeline.start_pipeline_execution(name=PIPELINE_NAME)
    return {"statusCode": 200, "body": json.dumps({"pipelineExecutionId": resp["pipelineExecutionId"]})}

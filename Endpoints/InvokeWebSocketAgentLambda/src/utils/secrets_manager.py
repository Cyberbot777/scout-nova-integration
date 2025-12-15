import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_secret(secret_name, region_name="us-east-1"):
    client = boto3.client("secretsmanager", region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        logger.error(f"Error retrieving secret: {exc}")
        raise

    if "SecretString" in response:
        return json.loads(response["SecretString"])
    else:
        decoded_binary_secret = response["SecretBinary"]
        return json.loads(decoded_binary_secret.decode("utf-8"))

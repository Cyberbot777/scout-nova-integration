import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_secret(secret_name, region_name="us-east-1"):
    if not secret_name:
        raise ValueError(f"Secret name is required but got: {secret_name}")
        
    client = boto3.client("secretsmanager", region_name=region_name)
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        logger.error(f"Error retrieving secret '{secret_name}': {exc}")
        raise exc

    if "SecretString" in response:
        secret_value = response["SecretString"]
    else:
        secret_value = response["SecretBinary"].decode("utf-8")
    
    if not secret_value or secret_value.strip() == "":
        raise ValueError(f"Secret '{secret_name}' is empty")
    
    try:
        return json.loads(secret_value)
    except json.JSONDecodeError:
        logger.warning(f"Secret '{secret_name}' is not valid JSON, returning as string")
        return secret_value
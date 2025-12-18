"""
WebSocket URL signing helpers for AWS SigV4 authentication.
Creates pre-signed URLs for connecting to AgentCore Runtime WebSocket endpoints.
"""
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from urllib.parse import urlparse, parse_qs, urlencode
from datetime import datetime, timedelta


def create_presigned_url(base_url: str, region: str, service: str = "bedrock-agentcore", expires: int = 3600) -> str:
    """
    Create a pre-signed WebSocket URL with AWS SigV4 authentication.
    
    Args:
        base_url: The base WebSocket URL (e.g., wss://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/ARN/ws)
        region: AWS region (e.g., us-east-1)
        service: AWS service name (default: bedrock-agentcore)
        expires: URL expiration time in seconds (default: 3600 = 1 hour)
    
    Returns:
        Pre-signed WebSocket URL with SigV4 authentication parameters in query string
    
    Example:
        >>> url = create_presigned_url(
        ...     "wss://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/abc123/ws",
        ...     region="us-east-1"
        ... )
        >>> # Returns: wss://...?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=...
    """
    # Get AWS credentials from session
    session = boto3.Session(region_name=region)
    credentials = session.get_credentials()
    frozen_credentials = credentials.get_frozen_credentials()

    # Parse the URL
    parsed = urlparse(base_url)
    
    # Convert wss:// to https:// for signing (then convert back)
    scheme = "https" if parsed.scheme == "wss" else "http"
    
    # Build the canonical URL for signing
    canonical_url = f"{scheme}://{parsed.netloc}{parsed.path}"
    
    # Parse existing query parameters
    query_params = parse_qs(parsed.query) if parsed.query else {}
    
    # Flatten query params (parse_qs returns lists)
    flattened_params = {k: v[0] if isinstance(v, list) else v for k, v in query_params.items()}
    
    # Add SigV4 required parameters
    now = datetime.utcnow()
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    datestamp = now.strftime('%Y%m%d')
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    
    flattened_params.update({
        'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
        'X-Amz-Credential': f"{frozen_credentials.access_key}/{credential_scope}",
        'X-Amz-Date': amz_date,
        'X-Amz-Expires': str(expires),
    })
    
    # Add session token if present
    if frozen_credentials.token:
        flattened_params['X-Amz-Security-Token'] = frozen_credentials.token
    
    # Create the request for signing
    canonical_querystring = urlencode(sorted(flattened_params.items()))
    url_to_sign = f"{canonical_url}?{canonical_querystring}"
    
    # Create AWS request and sign it
    request = AWSRequest(method='GET', url=url_to_sign)
    SigV4Auth(credentials, service, region).add_auth(request)
    
    # Extract the signature from signed request
    signed_url = request.url
    
    # Convert back to WebSocket scheme
    if parsed.scheme == "wss":
        signed_url = signed_url.replace("https://", "wss://")
    elif parsed.scheme == "ws":
        signed_url = signed_url.replace("http://", "ws://")
    
    return signed_url


def validate_presigned_url(url: str) -> bool:
    """
    Validate that a URL contains SigV4 authentication parameters.
    
    Args:
        url: The URL to validate
    
    Returns:
        True if URL contains required SigV4 parameters, False otherwise
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    required_params = [
        'X-Amz-Algorithm',
        'X-Amz-Credential',
        'X-Amz-Date',
        'X-Amz-Signature'
    ]
    
    return all(param in query_params for param in required_params)


def extract_expiration(url: str) -> datetime:
    """
    Extract the expiration time from a pre-signed URL.
    
    Args:
        url: The pre-signed URL
    
    Returns:
        datetime object representing when the URL expires
    
    Raises:
        ValueError: If URL doesn't contain required parameters
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    if 'X-Amz-Date' not in query_params or 'X-Amz-Expires' not in query_params:
        raise ValueError("URL missing required expiration parameters")
    
    amz_date = query_params['X-Amz-Date'][0]
    expires_seconds = int(query_params['X-Amz-Expires'][0])
    
    # Parse the date
    created_at = datetime.strptime(amz_date, '%Y%m%dT%H%M%SZ')
    expires_at = created_at + timedelta(seconds=expires_seconds)
    
    return expires_at


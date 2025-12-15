import logging
import requests
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def make_request(session, host, path, method="GET", headers=None, body=None):
    url = f"https://{host}{path}"
    logger.info(f"Making {method} request to {url}")
    if headers:
        logger.info(f"Request Headers: {headers}")
    if body:
        logger.info(f"Request Body: {body}")
    try:
        response = session.request(method, url, headers=headers, data=body, timeout=30)
        data = response.content
        response_headers = dict(response.headers)
        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Headers: {response_headers}")
        set_cookie = response_headers.get("Set-Cookie")
        return response.status_code, data, set_cookie, response_headers
    except Exception as exc:
        logger.error(f"HTTP request failed for {method} {url}: {exc}")
        raise

def make_json_request(session, url, method="GET", headers=None, payload=None):
    """
    Make a JSON request using the existing session pattern
    Returns status code, response data, cookies, and response headers
    """
    logger.info(f"Making {method} JSON request to {url}")
    
    # Set default JSON headers
    json_headers = {"Content-Type": "application/json"}
    if headers:
        json_headers.update(headers)
    
    logger.info(f"Request Headers: {json_headers}")
    
    # Convert payload to JSON string if it's a dict
    json_payload = None
    if payload:
        json_payload = json.dumps(payload) if isinstance(payload, dict) else payload
        logger.info(f"Request Payload: {json_payload}")
    
    try:
        response = session.request(method, url, headers=json_headers, data=json_payload, timeout=30)
        data = response.content
        response_headers = dict(response.headers)
        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Headers: {response_headers}")
        
        # Extract cookies for session management
        set_cookie = response_headers.get("Set-Cookie")
        
        return response.status_code, data, set_cookie, response_headers
    except Exception as exc:
        logger.error(f"HTTP JSON request failed for {method} {url}: {exc}")
        raise

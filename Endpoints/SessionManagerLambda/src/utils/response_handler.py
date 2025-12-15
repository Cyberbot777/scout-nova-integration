import json
import time
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def decimal_default(obj):
    # Convert Decimal objects to int/float for JSON serialization
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def create_success_response(data):
    # Create standardized success response
    return {
        'statusCode': 200,
        'body': json.dumps(data, default=decimal_default),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
    }

def create_error_response(status_code, message):
    # Create standardized error response
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': message,
            'timestamp': int(time.time())
        }, default=decimal_default),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
    }

def log_request(event):
    # Log incoming request for debugging
    logger.info(f"Request received: {json.dumps(event)}")

def validate_action(action):
    """Validate if the requested action is supported"""
    valid_actions = ['get_or_create_session', 'validate_session', 'update_activity']
    
    if action not in valid_actions:
        raise ValueError(f'Invalid action. Use: {", ".join(valid_actions)}')
    
    return True
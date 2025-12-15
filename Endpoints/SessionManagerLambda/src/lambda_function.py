import json
import logging
from config import LOG_LEVEL
from utils import session_manager
from utils.response_handler import create_success_response, create_error_response, log_request, validate_action

# Configure logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL))

def lambda_handler(event, context):
    # Session management: get/create, validate, update activity
    try:
        log_request(event)
        
        action = event.get('action')
        validate_action(action)
        
        if action == 'get_or_create_session':
            data = event.get('data', {})
            result = session_manager.get_or_create_session(data)
            return create_success_response(result)
            
        elif action == 'validate_session':
            session_id = event.get('sessionId')
            result = session_manager.validate_session(session_id)
            return create_success_response(result)
            
        elif action == 'update_activity':
            session_id = event.get('sessionId')
            result = session_manager.update_session_activity(session_id)
            return create_success_response(result)
            
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return create_error_response(400, str(e))
        
    except Exception as e:
        logger.error(f"Session service error: {str(e)}")
        return create_error_response(500, f'Internal server error: {str(e)}')
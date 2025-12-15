import json
import boto3
import logging
import uuid
import os

logger = logging.getLogger(__name__)

def get_session_id(broker_id, sys_user_id, nmls_id=None, loan_id=None, oauth_token=None):
    # Get or create session and return session ID
    session_function_name = os.environ.get('SESSION_FUNCTION_NAME')
    
    if not session_function_name:
        logger.warning("Session function not configured, creating fallback session ID")
        return _create_fallback_session_id(broker_id, sys_user_id, loan_id)
    
    payload = {
        'action': 'get_or_create_session',
        'data': {
            'brokerId': broker_id,
            'sysUserId': sys_user_id,
            'nmlsId': nmls_id,
            'loanId': loan_id,
            'token': oauth_token
        }
    }
    
    try:
        logger.info(f"Getting session for {broker_id}#{sys_user_id}")
        
        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName=session_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        if result['statusCode'] == 200:
            body = json.loads(result['body'])
            session_id = body['session']['sessionId']
            new_session = body.get('new_session', False)
            
            logger.info(f"Session {'created' if new_session else 'retrieved'}: {session_id}")
            return session_id
        else:
            logger.error(f"Session service error: {result}")
            return _create_fallback_session_id(broker_id, sys_user_id, loan_id)
            
    except Exception as e:
        logger.error(f"Error calling session service: {str(e)}")
        return _create_fallback_session_id(broker_id, sys_user_id, loan_id)

def _create_fallback_session_id(broker_id, sys_user_id, loan_id=None):
    # Create fallback session ID when service unavailable
    if loan_id:
        session_id = f"{broker_id}#{sys_user_id}#Loan#{loan_id}#{str(uuid.uuid4())}"
    else:
        session_id = f"{broker_id}#{sys_user_id}#Portal#{str(uuid.uuid4())}"
    
    logger.warning(f"Created fallback session ID: {session_id}")
    return session_id
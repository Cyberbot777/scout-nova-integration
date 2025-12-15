import boto3
import uuid
import time
import base64
import logging
from typing import Dict, Any
from config import SESSION_TABLE_NAME, TOKEN_ENCRYPTION_KEY_ID

logger = logging.getLogger(__name__)
dynamodb = boto3.resource('dynamodb')
kms_client = boto3.client('kms')

SESSION_ACTIVITY_TIMEOUT_SECONDS = 30 * 60
TTL_SECONDS = 90 * 24 * 60 * 60

def get_or_create_session(data: Dict[str, Any]) -> Dict[str, Any]:
    required_fields = ['brokerId', 'sysUserId']
    missing_fields = [field for field in required_fields if not data.get(field)]
    
    if missing_fields:
        raise ValueError(f'Missing required fields: {", ".join(missing_fields)}')
    
    broker_id = data.get('brokerId')
    sys_user_id = data.get('sysUserId')
    nmls_id = data.get('nmlsId')
    loan_id = data.get('loanId')
    oauth_token = data.get('token')
    
    if not SESSION_TABLE_NAME:
        return _create_fallback_session(broker_id, sys_user_id, nmls_id, loan_id)
    
    try:
        table = dynamodb.Table(SESSION_TABLE_NAME)
        pk = f"{broker_id}#{sys_user_id}"
        
        if loan_id:
            session_id_prefix = f"{broker_id}-{sys_user_id}-Loan-{loan_id}"
            context = f"Loan-{loan_id}"
        else:
            session_id_prefix = f"{broker_id}-{sys_user_id}-Portal"
            context = "Portal"
        
        now = int(time.time())
        
        response = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
            FilterExpression='#status = :active',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':pk': pk,
                ':sk_prefix': f'SESSION#{session_id_prefix}-',
                ':active': 'active'
            },
            Limit=1
        )
        
        if response.get('Items'):
            item = response['Items'][0]
            time_since_activity = now - item['lastActivityAt']
            
            if time_since_activity < SESSION_ACTIVITY_TIMEOUT_SECONDS:
                updated_session = _update_existing_session(table, item, pk, nmls_id, oauth_token, now)
                return {
                    'session': updated_session,
                    'new_session': False,
                    'context': context
                }
        
        new_session = _create_new_session(table, pk, session_id_prefix, broker_id, 
                                       sys_user_id, nmls_id, loan_id, oauth_token, now)
        return {
            'session': new_session,
            'new_session': True,
            'context': context
        }
        
    except Exception as e:
        raise Exception(f'Database error: {str(e)}')

def validate_session(session_id: str) -> Dict[str, Any]:
    if not session_id:
        raise ValueError('Missing sessionId parameter')
    
    if not SESSION_TABLE_NAME:
        return {'valid': True, 'reason': 'Table not configured'}
    
    try:
        table = dynamodb.Table(SESSION_TABLE_NAME)
        
        response = table.query(
            IndexName='sessionId-index',
            KeyConditionExpression='sessionId = :session_id',
            FilterExpression='#status = :active',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':session_id': session_id,
                ':active': 'active'
            }
        )
        
        if response.get('Items'):
            item = response['Items'][0]
            now = int(time.time())
            time_since_activity = now - item['lastActivityAt']
            is_valid = time_since_activity < SESSION_ACTIVITY_TIMEOUT_SECONDS
            
            return {
                'valid': is_valid,
                'sessionId': session_id,
                'lastActivityAt': item['lastActivityAt'],
                'timeSinceActivity': time_since_activity,
                'timeoutSeconds': SESSION_ACTIVITY_TIMEOUT_SECONDS
            }
        else:
            return {'valid': False, 'reason': 'Session not found or inactive'}
            
    except Exception as e:
        raise Exception(f'Validation error: {str(e)}')

def update_session_activity(session_id: str) -> Dict[str, Any]:
    if not session_id:
        raise ValueError('Missing sessionId parameter')
    
    if not SESSION_TABLE_NAME:
        return {'updated': False, 'reason': 'Table not configured'}
    
    try:
        table = dynamodb.Table(SESSION_TABLE_NAME)
        now = int(time.time())
        
        response = table.query(
            IndexName='sessionId-index',
            KeyConditionExpression='sessionId = :session_id',
            ExpressionAttributeValues={':session_id': session_id}
        )
        
        if response.get('Items'):
            item = response['Items'][0]
            
            table.update_item(
                Key={'PK': item['PK'], 'SK': item['SK']},
                UpdateExpression='SET lastActivityAt = :activity, #ttl = :ttl',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':activity': now,
                    ':ttl': now + TTL_SECONDS
                }
            )
            
            return {'updated': True, 'sessionId': session_id, 'lastActivityAt': now}
        else:
            raise Exception('Session not found')
            
    except Exception as e:
        raise Exception(f'Update error: {str(e)}')

def _update_existing_session(table, item, pk, nmls_id, oauth_token, now):
    update_expr = 'SET lastActivityAt = :activity, #ttl = :ttl'
    expr_names = {'#ttl': 'ttl'}
    expr_values = {':activity': now, ':ttl': now + TTL_SECONDS}
    
    if nmls_id and str(nmls_id) != item.get('nmlsId', ''):
        update_expr += ', nmlsId = :nmls'
        expr_values[':nmls'] = str(nmls_id)
    
    if oauth_token:
        encrypted_token = _encrypt_oauth_token(oauth_token)
        if encrypted_token and item.get('oauthToken') != encrypted_token:
            update_expr += ', oauthToken = :token'
            expr_values[':token'] = encrypted_token
    
    table.update_item(
        Key={'PK': pk, 'SK': item['SK']},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )
    
    item['lastActivityAt'] = now
    item['ttl'] = now + TTL_SECONDS
    if nmls_id:
        item['nmlsId'] = str(nmls_id)
    if oauth_token and _encrypt_oauth_token(oauth_token):
        item['oauthToken'] = _encrypt_oauth_token(oauth_token)
        
    return item

def _create_new_session(table, pk, session_id_prefix, broker_id, sys_user_id, nmls_id, loan_id, oauth_token, now):
    session_uuid = str(uuid.uuid4())
    session_id = f"{session_id_prefix}-{session_uuid}"
    sk = f"SESSION#{session_id}"
    
    item = {
        'PK': pk,
        'SK': sk,
        'sessionId': session_id,
        'brokerId': broker_id,
        'loanOfficerId': sys_user_id,
        'nmlsId': str(nmls_id) if nmls_id else '',
        'status': 'active',
        'createdAt': now,
        'lastActivityAt': now,
        'ttl': now + TTL_SECONDS,
    }
    
    if loan_id:
        item['loanId'] = loan_id
    
    if oauth_token:
        encrypted_token = _encrypt_oauth_token(oauth_token)
        if encrypted_token:
            item['oauthToken'] = encrypted_token
    
    table.put_item(Item=item)
    return item

def _encrypt_oauth_token(token):
    if not token or not TOKEN_ENCRYPTION_KEY_ID:
        return None
    
    try:
        response = kms_client.encrypt(
            KeyId=TOKEN_ENCRYPTION_KEY_ID,
            Plaintext=token.encode('utf-8')
        )
        return base64.b64encode(response['CiphertextBlob']).decode('utf-8')
    except Exception:
        return None

def _create_fallback_session(broker_id, sys_user_id, nmls_id, loan_id):
    if loan_id:
        session_id = f"{broker_id}-{sys_user_id}-Loan-{loan_id}-{str(uuid.uuid4())}"
    else:
        session_id = f"{broker_id}-{sys_user_id}-Portal-{str(uuid.uuid4())}"
    
    session = {
        'sessionId': session_id,
        'brokerId': broker_id,
        'loanOfficerId': sys_user_id,
        'nmlsId': str(nmls_id) if nmls_id else '',
        'status': 'active',
        'createdAt': int(time.time()),
        'fallback': True
    }
    
    if loan_id:
        session['loanId'] = loan_id
        
    return {'session': session, 'new_session': True}
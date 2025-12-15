import os

# Environment Variables
SESSION_TABLE_NAME = os.environ.get('SESSION_TABLE_NAME')
TOKEN_ENCRYPTION_KEY_ID = os.environ.get('TOKEN_ENCRYPTION_KEY_ID')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
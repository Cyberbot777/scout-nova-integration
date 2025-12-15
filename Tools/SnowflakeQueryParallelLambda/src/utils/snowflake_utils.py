import os
import logging
import time
import snowflake.connector
from snowflake.connector import DictCursor
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from .secrets_manager import get_secret

# Global connection cache
CACHED_CONNECTION = None
LAST_CONNECTION_TIME = 0
CONNECTION_TTL = 3600  # 1 hour cache
CONNECTION_LOCK = False  # Simple lock
CONNECTION_CONFIG = None  # Cache config too

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Log library versions for debugging
connector_version = getattr(snowflake.connector, "__version__", "unknown")
logger.info("Snowflake connector import OK. Version: %s", connector_version)

try:
    import cryptography
    crypto_version = getattr(cryptography, "__version__", "unknown")
    logger.info(f"Cryptography library version: {crypto_version}")
except ImportError as e:
    logger.warning(f"Cryptography import issue: {e}")

try:
    import OpenSSL
    openssl_version = getattr(OpenSSL, "__version__", "unknown")
    logger.info(f"pyOpenSSL version: {openssl_version}")
except ImportError as e:
    logger.warning(f"pyOpenSSL import issue: {e}")

def get_snowflake_config():
    config = {
        'role': os.environ.get("SNOWFLAKE_ROLE", "KWIKIE_DEV_UAT_FUNCTIONALROLE"),
        'warehouse': os.environ.get("SNOWFLAKE_WAREHOUSE"),
        'database': os.environ.get("SNOWFLAKE_DATABASE"),
        'schema': os.environ.get("SNOWFLAKE_SCHEMA"),
        'username': os.environ.get("SNOWFLAKE_USERNAME"),
        'account': os.environ.get("SNOWFLAKE_ACCOUNT"),
        'pem_secret_name': os.environ.get("SNOWFLAKE_SECRET_PEM_NAME"),
        'passphrase_secret_name': os.environ.get("SNOWFLAKE_SECRET_PASSPHRASE_NAME")
    }
    
    required_fields = ['username', 'account', 'pem_secret_name']
    missing_fields = [field for field in required_fields if not config[field]]
    
    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")
    
    return config

def prepare_private_key(config):
    private_key_pem = get_secret(config['pem_secret_name'])
    
    private_key_passphrase = None
    if config['passphrase_secret_name']:
        try:
            private_key_passphrase = get_secret(config['passphrase_secret_name'])
        except Exception as e:
            logger.warning(f"Could not retrieve passphrase secret: {e}")
    
    logger.info(f"Retrieved private key from Secrets Manager for PEM secret: {config['pem_secret_name']}")

    try:
        private_key_bytes = private_key_pem.encode("utf-8")

        password_bytes = None
        if private_key_passphrase:
            password_bytes = private_key_passphrase.encode("utf-8")

        private_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=password_bytes,
            backend=default_backend()
        )

        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return private_key_der
        
    except Exception as crypto_error:
        logger.error(f"Cryptography library error during key processing: {crypto_error}")
        raise ValueError(f"Failed to process private key: {crypto_error}")

def create_connection_params(config, private_key_der):
    # Ultra-optimized connection params for speed
    connection_params = {
        "user": config['username'],
        "account": config['account'],
        "private_key": private_key_der,
        "client_session_keep_alive": True,
        "client_session_keep_alive_heartbeat_frequency": 14400,  # 4 hours
        "login_timeout": 5,  # Aggressive timeout
        "network_timeout": 5,  # Aggressive timeout
        "socket_timeout": 5,  # Socket timeout
        "autocommit": True,
        "client_prefetch_threads": 1,  # Reduce overhead
        "numpy": False,  # Disable numpy for speed
        "arrow_number_to_decimal": False,  # Disable arrow for speed
    }
    
    # Add optional params only if they exist
    if config.get('warehouse'):
        connection_params['warehouse'] = config['warehouse']
    if config.get('role'):
        connection_params['role'] = config['role']
    if config.get('database'):
        connection_params['database'] = config['database']
    if config.get('schema'):
        connection_params['schema'] = config['schema']
    
    return [connection_params]

def connect_to_snowflake():
    global CACHED_CONNECTION, LAST_CONNECTION_TIME, CONNECTION_LOCK, CONNECTION_CONFIG
    
    # Prevent concurrent connection attempts
    if CONNECTION_LOCK:
        logger.info("Connection in progress, waiting...")
        time.sleep(0.1)
        if CACHED_CONNECTION:
            return CACHED_CONNECTION
    
    # Check if we can reuse cached connection
    current_time = time.time()
    if (CACHED_CONNECTION and 
        (current_time - LAST_CONNECTION_TIME) < CONNECTION_TTL):
        try:
            # Quick validation without full query
            if CACHED_CONNECTION.is_closed():
                logger.info("Cached connection is closed, creating new one")
            else:
                logger.info("Reusing cached connection - connection time: ~0.01 seconds")
                LAST_CONNECTION_TIME = current_time  # Refresh timestamp
                return CACHED_CONNECTION
        except Exception as e:
            logger.warning(f"Cached connection invalid: {e}")
            CACHED_CONNECTION = None
    
    CONNECTION_LOCK = True
    try:
        # Create new connection with optimized approach
        start_time = time.time()
        
        # Cache config to avoid repeated calls
        if not CONNECTION_CONFIG:
            CONNECTION_CONFIG = get_snowflake_config()
        config = CONNECTION_CONFIG
        
        logger.info(f"Creating new Snowflake connection to: {config['account']}")
        
        # Prepare key once
        private_key_der = prepare_private_key(config)
        connection_attempts = create_connection_params(config, private_key_der)
        
        # Single aggressive connection attempt
        conn_params = connection_attempts[0]
        logger.info("Attempting optimized connection...")
        
        try:
            conn = snowflake.connector.connect(**conn_params)
            
            connection_time = time.time() - start_time
            logger.info(f"Snowflake connection established in {connection_time:.2f} seconds")
            
            # Cache the connection
            CACHED_CONNECTION = conn
            LAST_CONNECTION_TIME = current_time
            
            return conn
            
        except Exception as e:
            logger.error(f"Fast connection failed: {e}")
            # Fallback to basic connection
            logger.info("Trying fallback connection...")
            fallback_params = {
                "user": config['username'],
                "account": config['account'], 
                "private_key": private_key_der,
                "login_timeout": 15,
                "network_timeout": 15
            }
            
            conn = snowflake.connector.connect(**fallback_params)
            connection_time = time.time() - start_time
            logger.info(f"Fallback connection established in {connection_time:.2f} seconds")
            
            CACHED_CONNECTION = conn
            LAST_CONNECTION_TIME = current_time
            return conn
    
    finally:
        CONNECTION_LOCK = False

def setup_snowflake_session(connection, config):
    cursor = connection.cursor(DictCursor)
    
    # Skip session setup if connection already has context set
    # (when role/warehouse/database/schema were set in connection params)
    try:
        # Quick test to see if we already have proper context
        cursor.execute("SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
        current_context = cursor.fetchone()
        logger.info(f"Current context: {current_context}")
        
        # If we have the right context from connection params, skip USE statements
        if (current_context and 
            str(current_context.get('CURRENT_ROLE()', '')).upper() == config.get('role', '').upper() and
            str(current_context.get('CURRENT_WAREHOUSE()', '')).upper() == config.get('warehouse', '').upper() and
            str(current_context.get('CURRENT_DATABASE()', '')).upper() == config.get('database', '').upper() and
            str(current_context.get('CURRENT_SCHEMA()', '')).upper() == config.get('schema', '').upper()):
            logger.info("Session context already set via connection params - skipping USE statements")
            return cursor
        
    except Exception as e:
        logger.warning(f"Could not check current context: {e}")
    
    # Fallback: Set context with USE statements (slower)
    if config['role']:
        cursor.execute(f'USE ROLE "{config["role"]}"')
        logger.info(f"Set role to: {config['role']}")
        
    if config['warehouse']:
        cursor.execute(f'USE WAREHOUSE "{config["warehouse"]}"')
        logger.info(f"Set warehouse to: {config['warehouse']}")
        
    if config['database']:
        cursor.execute(f'USE DATABASE "{config["database"]}"')
        logger.info(f"Set database to: {config['database']}")
        
    if config['schema']:
        cursor.execute(f'USE SCHEMA "{config["schema"]}"')
        logger.info(f"Set schema to: {config['schema']}")
    
    return cursor

def execute_snowflake_query(cursor, query, params=None):
    if params:
        logger.info("Executing parameterized query: %s with params: %s", query, params)
        query_start = time.time()
        cursor.execute(query, params)
    else:
        logger.info("Executing query: %s", query)
        query_start = time.time()
        cursor.execute(query)
    
    rows = cursor.fetchall()
    query_time = time.time() - query_start
    logger.info(f"Query completed in {query_time:.2f} seconds, returned {len(rows)} rows")
    
    return rows, query_time

def get_active_pipeline_query():
    return """
        SELECT
            hl.id AS home_loan_id,
            hl.lender_loan_number,
            rls.loan_status_description AS loan_status,
            rct.channel_type_desc AS channel_type,
            rmt.mortgage_type_desc AS mortgage_type,
            rlpt.loan_purpose_type_desc AS loan_purpose_type,
            rrpt.refi_purpose_type_desc AS refi_purpose_type,
            hld.lien_position,
            rii.investor_name AS investor,
            rpt.pricing_tier_desc AS pricing_tier,
            hlsd.total_loan_amt AS loan_amount,
            rrlst.rate_lock_status_type_desc AS rate_loan_status,
            rrlst.rate_locked_yn AS rate_locked,
            hlkd.rate_lock_date_time AS rate_lock_date_time,
            hlkd.rate_lock_expiration_date AS rate_lock_expiration_date,
            (hlkd.rate_lock_expiration_date - CURRENT_DATE) AS days_to_lock_expiration,
            hlkd.anticipated_settlement_date AS anticipated_settlement_date
        FROM home_loan hl
            LEFT JOIN home_loan_detail hld ON hl.id = hld.home_loan_id
            LEFT JOIN home_loan_summary_data hlsd ON hl.id = hlsd.home_loan_id
            LEFT JOIN home_loan_key_date hlkd ON hl.id = hlkd.home_loan_id
            LEFT JOIN ref_loan_status rls ON hl.loan_status_type_id = rls.loan_status_type_id
            LEFT JOIN ref_channel_type rct ON hld.channel_type_id = rct.channel_type_id
            LEFT JOIN ref_mortgage_type rmt ON hld.mortgage_type_id = rmt.mortgage_type_id
            LEFT JOIN ref_loan_purpose_type rlpt ON hld.loan_purpose_type_id = rlpt.loan_purpose_type_id
            LEFT JOIN ref_refi_purpose_type rrpt ON hld.refi_purpose_type_id = rrpt.refi_purpose_type_id
            LEFT JOIN ref_investor_info rii ON hld.investor_id = rii.investor_id
            LEFT JOIN ref_pricing_tier rpt ON hld.pricing_tier_id = rpt.pricing_tier_id
            LEFT JOIN ref_rate_lock_status_type rrlst ON hld.rate_lock_status_type_id = rrlst.rate_lock_status_type_id
            LEFT JOIN sys_user_info sui ON hlsd.loan_originator_id = sui.nmls_id
        WHERE sui.sys_user_id = %(sys_user_id)s
          AND hl.loan_status_type_id != '0740'
          AND hl.loan_status_type_id <= '0743'
    """

def get_funded_loans_query():
    return """
        SELECT
            hl.id AS home_loan_id,
            hl.lender_loan_number,
            rct.channel_type_desc AS channel_type,
            rmt.mortgage_type_desc AS mortgage_type,
            rlpt.loan_purpose_type_desc AS loan_purpose_type,
            rrpt.refi_purpose_type_desc AS refi_purpose_type,
            hld.lien_position,
            rii.investor_name AS investor,
            rpt.pricing_tier_desc AS pricing_tier,
            hlfwi.wire_received_date_time AS funded_date,
            hlsd.total_loan_amt AS loan_amount
        FROM home_loan hl
            LEFT JOIN home_loan_detail hld ON hl.id = hld.home_loan_id
            LEFT JOIN home_loan_summary_data hlsd ON hl.id = hlsd.home_loan_id
            LEFT JOIN home_loan_funding_request hlfr ON hl.id = hlfr.home_loan_id
            LEFT JOIN home_loan_funding_wire_info hlfwi
                ON hlfr.id = hlfwi.home_loan_funding_request_id
            LEFT JOIN ref_channel_type rct ON hld.channel_type_id = rct.channel_type_id
            LEFT JOIN ref_mortgage_type rmt ON hld.mortgage_type_id = rmt.mortgage_type_id
            LEFT JOIN ref_loan_purpose_type rlpt ON hld.loan_purpose_type_id = rlpt.loan_purpose_type_id
            LEFT JOIN ref_refi_purpose_type rrpt ON hld.refi_purpose_type_id = rrpt.refi_purpose_type_id
            LEFT JOIN ref_investor_info rii ON hld.investor_id = rii.investor_id
            LEFT JOIN ref_pricing_tier rpt ON hld.pricing_tier_id = rpt.pricing_tier_id
            LEFT JOIN sys_user_info sui ON hlsd.loan_originator_id = sui.nmls_id
        WHERE sui.sys_user_id = %(sys_user_id)s
          AND hlfwi.wire_received_date_time IS NOT NULL
    """

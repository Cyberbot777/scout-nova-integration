import json
import logging
from botocore.exceptions import ClientError
from utils.snowflake_utils import (
    connect_to_snowflake,
    setup_snowflake_session,
    execute_snowflake_query,
    get_active_pipeline_query,
    get_funded_loans_query,
    get_snowflake_config
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Pre-initialize connection on module load (container warmup)
def warmup_connection():
    """Pre-establish connection on container startup"""
    try:
        logger.info("Warming up Snowflake connection...")
        from utils.snowflake_utils import connect_to_snowflake, CACHED_CONNECTION
        
        # Only warmup if not already cached
        if not CACHED_CONNECTION:
            connect_to_snowflake()
            logger.info("Connection warmup completed")
        else:
            logger.info("Connection already warm")
    except Exception as e:
        logger.warning(f"Connection warmup failed: {e}")

# Warmup on module load (when Lambda container starts)
warmup_connection()


def lambda_handler(event, context):
    logger.info("Event received: %s", json.dumps(event))

    # Handle warmup events
    if event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event":
        logger.info("Warmup event received - keeping Lambda warm")
        return {"statusCode": 200, "body": "Lambda warmed up"}

    connection = None
    try:
        logger.info("Starting Snowflake connection process...")
        
        connection = connect_to_snowflake()
        logger.info("Snowflake connection successful")
        
        config = get_snowflake_config()
        cursor = setup_snowflake_session(connection, config)

        query = event.get("query") if isinstance(event, dict) else None
        query_params = None
        
        if not query:
            sys_user_id = event.get("sys_user_id") if isinstance(event, dict) else None
            query_type = event.get("query_type") if isinstance(event, dict) else None
            
            if not sys_user_id:
                logger.error("Missing required parameter: sys_user_id")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Missing required parameter: sys_user_id"})
                }
            
            if not query_type:
                logger.error("Missing required parameter: query_type")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Missing required parameter: query_type"})
                }
            
            if query_type == "active_pipeline":
                query = get_active_pipeline_query()
                query_params = {"sys_user_id": sys_user_id}
                logger.info(f"Using active pipeline query for sys_user_id: {sys_user_id}")
            elif query_type == "funded_loans":
                query = get_funded_loans_query()
                query_params = {"sys_user_id": sys_user_id}
                logger.info(f"Using funded loans query for sys_user_id: {sys_user_id}")
            else:
                logger.error(f"Invalid query_type: {query_type}. Valid options: active_pipeline, funded_loans")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": f"Invalid query_type: {query_type}. Valid options: active_pipeline, funded_loans"})
                }

        if query_params:
            rows, query_time = execute_snowflake_query(cursor, query, query_params)
        else:
            rows, query_time = execute_snowflake_query(cursor, query)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "rows": rows,
                "query_time_seconds": query_time,
                "row_count": len(rows)
            }, default=str)
        }

    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Configuration error: {str(ve)}"})
        }
    except ClientError as ce:
        logger.error(f"AWS error: {ce}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"AWS error: {str(ce)}"})
        }
    except Exception as e:
        logger.exception("Snowflake query failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

    finally:
        try:
            if connection:
                connection.close()
                logger.info("Snowflake connection closed successfully")
        except Exception:
            logger.warning("Failed closing Snowflake connection", exc_info=True)

import json
import logging
import asyncio
from typing import List, Dict, Any
from botocore.exceptions import ClientError
from utils.snowflake_utils import (
    connect_to_snowflake_async,
    setup_snowflake_session_async,
    execute_snowflake_query_async,
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
        from utils.snowflake_utils import connect_to_snowflake_async
        import asyncio
        
        # Only warmup if not already cached
        from utils.snowflake_utils import CACHED_CONNECTION
        if not CACHED_CONNECTION:
            asyncio.run(connect_to_snowflake_async())
            logger.info("Connection warmup completed")
        else:
            logger.info("Connection already warm")
    except Exception as e:
        logger.warning(f"Connection warmup failed: {e}")

# Warmup on module load (when Lambda container starts)
warmup_connection()


async def execute_single_query_async(
    connection,
    config: Dict,
    query_type: str,
    sys_user_id: int
) -> Dict[str, Any]:
    """Execute a single query asynchronously"""
    try:
        cursor = await setup_snowflake_session_async(connection, config)
        
        if query_type == "active_pipeline":
            query = get_active_pipeline_query()
            query_params = {"sys_user_id": sys_user_id}
            logger.info(f"Executing active pipeline query for sys_user_id: {sys_user_id}")
        elif query_type == "funded_loans":
            query = get_funded_loans_query()
            query_params = {"sys_user_id": sys_user_id}
            logger.info(f"Executing funded loans query for sys_user_id: {sys_user_id}")
        else:
            raise ValueError(f"Invalid query_type: {query_type}. Valid options: active_pipeline, funded_loans")

        rows, query_time = await execute_snowflake_query_async(cursor, query, query_params)
        
        return {
            "query_type": query_type,
            "rows": rows,
            "query_time_seconds": query_time,
            "row_count": len(rows),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Query {query_type} failed: {e}")
        return {
            "query_type": query_type,
            "error": str(e),
            "status": "failed"
        }

async def execute_queries_parallel(
    sys_user_id: int,
    query_types: List[str]
) -> List[Dict[str, Any]]:
    """Execute multiple queries in parallel"""
    connection = None
    try:
        logger.info("Starting Snowflake connection process...")
        connection = await connect_to_snowflake_async()
        logger.info("Snowflake connection successful")
        
        config = get_snowflake_config()
        
        # Execute all queries in parallel
        tasks = [
            execute_single_query_async(connection, config, query_type, sys_user_id)
            for query_type in query_types
        ]
        
        logger.info(f"Executing {len(tasks)} queries in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Query {query_types[i]} failed with exception: {result}")
                processed_results.append({
                    "query_type": query_types[i],
                    "error": str(result),
                    "status": "failed"
                })
            else:
                processed_results.append(result)
        
        return processed_results
        
    finally:
        try:
            if connection:
                connection.close()
                logger.info("Snowflake connection closed successfully")
        except Exception:
            logger.warning("Failed closing Snowflake connection", exc_info=True)

def lambda_handler(event, context):
    """AWS Lambda handler with async support"""
    logger.info("Event received: %s", json.dumps(event))

    # Handle warmup events
    if event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event":
        logger.info("Warmup event received - keeping Lambda warm")
        return {"statusCode": 200, "body": "Lambda warmed up"}

    try:
        # Handle both single and multiple query requests
        if isinstance(event, dict):
            sys_user_id = event.get("sys_user_id")
            
            if not sys_user_id:
                logger.error("Missing required parameter: sys_user_id")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing required parameter: sys_user_id"})
                }
            
            # Check for multiple query types
            query_types = event.get("query_types", [])
            
            if query_types:
                # Multiple queries - async parallel execution
                logger.info(f"Processing multiple queries: {query_types}")
                
                # Validate query types
                valid_types = ["active_pipeline", "funded_loans"]
                invalid_types = [qt for qt in query_types if qt not in valid_types]
                if invalid_types:
                    return {
                        "statusCode": 400,
                        "body": json.dumps({
                            "error": f"Invalid query_types: {invalid_types}. Valid options: {valid_types}"
                        })
                    }
                
                # Execute async function
                results = asyncio.run(execute_queries_parallel(sys_user_id, query_types))
                
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "results": results,
                        "total_queries": len(query_types),
                        "successful_queries": len([r for r in results if r.get("status") == "success"]),
                        "failed_queries": len([r for r in results if r.get("status") == "failed"])
                    }, default=str)
                }
            
            else:
                # Single query - backward compatibility
                query_type = event.get("query_type")
                
                if not query_type:
                    logger.error("Missing required parameter: query_type or query_types")
                    return {
                        "statusCode": 400,
                        "body": json.dumps({"error": "Missing required parameter: query_type or query_types"})
                    }
                
                # Execute single query async
                results = asyncio.run(execute_queries_parallel(sys_user_id, [query_type]))
                
                if results and results[0].get("status") == "success":
                    result = results[0]
                    return {
                        "statusCode": 200,
                        "body": json.dumps({
                            "rows": result["rows"],
                            "query_time_seconds": result["query_time_seconds"],
                            "row_count": result["row_count"]
                        }, default=str)
                    }
                else:
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": results[0].get("error", "Unknown error")})
                    }
        
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid event format"})
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
        logger.exception("Lambda execution failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

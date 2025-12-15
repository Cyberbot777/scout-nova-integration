import logging
import requests
from utils.automation_utils import hydra_login, hydra_query_executor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    session = requests.Session()
    logger.info(f"Event: {event}")

    # Extract required parameters from event
    loan_id = event.get("loanId")
    query_name = event.get("queryName")
    
    if not loan_id:
        logger.error("Missing required parameter: loanId")
        return {
            "statusCode": 400,
            "error": "Missing required parameter: loanId"
        }
    
    if not query_name:
        logger.error("Missing required parameter: queryName")
        return {
            "statusCode": 400,
            "error": "Missing required parameter: queryName"
        }
    
    logger.info(f"Loan ID: {loan_id}")
    logger.info(f"Query Name: {query_name}")

    hydra_result = None
    try:
        logger.info("Starting Hydra API integration")
        hydra_token = hydra_login(session)
        
        if hydra_token:
            hydra_result = hydra_query_executor(session, hydra_token, loan_id, query_name)
            logger.info(f"Hydra API result: {hydra_result}")
        else:
            logger.warning("Failed to obtain Hydra token, skipping Hydra query")
            
    except Exception as e:
        logger.error(f"Hydra API integration failed: {e}")
        hydra_result = {"error": str(e)}

    return {
        "statusCode": 200,
        "loanId": loan_id,
        "queryName": query_name,
        "hydraResult": hydra_result
    }

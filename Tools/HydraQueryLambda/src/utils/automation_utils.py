import re
import json
import urllib.parse
import logging
import config
from .http_client import make_json_request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def hydra_login(session):
    logger.info("Attempting Hydra API login")
    
    login_url = f"{config.HYDRA_BASE_URL}/login"
    login_payload = {
        "userId": config.HYDRA_USERNAME,
        "password": config.HYDRA_PASSWORD
    }
    
    try:
        status_code, response_data, cookies, headers = make_json_request(
            session, login_url, "POST", payload=login_payload
        )
        
        if status_code == 200:
            response_json = json.loads(response_data.decode("utf-8", errors="ignore"))
            logger.info(f"Hydra login successful: {response_json}")
            
            token = response_json.get("token") or response_json.get("access_token")
            return token
        else:
            logger.error(f"Hydra login failed with status {status_code}: {response_data}")
            raise RuntimeError(f"Hydra login failed with status {status_code}")
            
    except Exception as e:
        logger.error(f"Hydra login failed: {e}")
        raise RuntimeError(f"Hydra login failed: {e}")

def hydra_query_executor(session, token, loan_id, query_name):
    logger.info(f"Executing Hydra query for loan ID: {loan_id} with query: {query_name}")
    
    query_url = f"{config.HYDRA_BASE_URL}/queryExecutor/execute"
    
    query_payload = {
        "envelope": {
            "queryName": query_name,
            "transactionDataMap": {
                "Id": loan_id
            }
        }
    }
    
    query_headers = {
        "environment": config.HYDRA_ENVIRONMENT,
        "token": token
    }
    
    try:
        full_url = f"{query_url}"
        
        status_code, response_data, cookies, headers = make_json_request(
            session, full_url, "POST", headers=query_headers, payload=query_payload
        )
        
        if status_code == 200:
            response_json = json.loads(response_data.decode("utf-8", errors="ignore"))
            logger.info(f"Hydra query successful: {response_json}")
            return response_json
        else:
            logger.error(f"Hydra query failed with status {status_code}: {response_data}")
            raise RuntimeError(f"Hydra query failed with status {status_code}")
            
    except Exception as e:
        logger.error(f"Hydra query execution failed: {e}")
        raise RuntimeError(f"Hydra query execution failed: {e}")
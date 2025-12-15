import json
import uuid
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event

        session_id = body.get('sessionId') or f"session-{uuid.uuid4()}"
        user_prompt = body.get('prompt', 'Hello')

    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Invalid request format"})
        }

    agent_runtime_arn = "arn:aws:bedrock-agentcore:us-east-1:025066260073:runtime/kwikieagent-9XPLfP2pzl"
    input_payload = json.dumps({"prompt": user_prompt}).encode("utf-8")
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            runtimeSessionId=session_id,
            contentType="application/json",
            accept="application/json",
            payload=input_payload,
        )

        agent_response = ""
        if "response" in response and hasattr(response["response"], "read"):
            raw_bytes = response["response"].read()
            agent_response = raw_bytes.decode("utf-8")

        # CRITICAL FIX: Extract just the response text
        try:
            parsed_response = json.loads(agent_response)
            clean_message = parsed_response.get("response", agent_response)
        except:
            clean_message = agent_response

        # Return CLEAN response
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "sessionId": session_id,
                "message": clean_message.strip()
            })
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e), "sessionId": session_id})
        }
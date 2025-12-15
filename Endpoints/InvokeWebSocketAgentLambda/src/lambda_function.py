import logging
from utils.auth import validate_api_key
from utils.websocket_handler import handle_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_token_from_subprotocol(event):
    headers = event.get("headers") or {}

    proto = headers.get("Sec-WebSocket-Protocol") or headers.get("sec-websocket-protocol")
    if not proto:
        return None

    parts = [p.strip() for p in proto.split(",") if p.strip()]

    if len(parts) >= 2 and parts[0].lower() == "auth":
        return parts[1]

    return None


def lambda_handler(event, context):
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")

    logger.info(f"Route: {route_key}, Connection: {connection_id}")

    if route_key == "$connect":
        token = get_token_from_subprotocol(event)

        if not token:
            logger.error(f"Connection {connection_id}: Missing auth token in subprotocol")
            return {"statusCode": 401, "body": "Auth token required"}

        if not validate_api_key(token):
            logger.error(f"Connection {connection_id}: Invalid auth token")
            return {"statusCode": 403, "body": "Invalid token"}

        logger.info(f"Connection {connection_id}: Valid token")

        return {
            "statusCode": 200,
            "headers": {
                "Sec-WebSocket-Protocol": "auth"
            }
        }

    elif route_key == "$disconnect":
        logger.info(f"Disconnected: {connection_id}")
        return {"statusCode": 200}

    elif route_key == "sendMessage":
        return handle_message(event, connection_id)

    logger.warning(f"Unknown routeKey: {route_key}")
    return {"statusCode": 404, "body": "Not found"}

import json
import boto3
import logging
import time
import os
import ast
from .session_client import get_session_id

logger = logging.getLogger(__name__)


def handle_message(event, connection_id):
    AGENTCORE_RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN")
    WEBSOCKET_URL = os.environ.get("WEBSOCKET_URL")
    
    api_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=WEBSOCKET_URL
    )

    try:
        body = json.loads(event.get('body', '{}'))
        user_prompt = (body.get('message') or "").strip()
        
        # Required fields for session management
        broker_id = (body.get('brokerId') or "").strip()
        sys_user_id = (body.get('sysUserId') or "").strip()
        
        # Optional fields
        nmls_id = body.get('nmlsId')
        loan_id = body.get('loanId')  # If present, creates Loan session; if not, Portal session
        oauth_token = body.get('token')

        # Validate required fields
        if not broker_id:
            logger.error("Missing brokerId")
            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'error': 'brokerId is required'})
            )
            return {'statusCode': 400}

        if not sys_user_id:
            logger.error("Missing sysUserId")
            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'error': 'sysUserId is required'})
            )
            return {'statusCode': 400}

        if not user_prompt:
            logger.error("Missing message")
            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'error': 'message is required'})
            )
            return {'statusCode': 400}

        # Get or create session
        session_id = get_session_id(
            broker_id=broker_id,
            sys_user_id=sys_user_id,
            nmls_id=nmls_id,
            loan_id=loan_id,
            oauth_token=oauth_token
        )

        logger.info(
            f"Processing - Session: {session_id}, sysUserId: {sys_user_id}, "
            f"Message: {user_prompt[:50]}..."
        )

        client = boto3.client("bedrock-agentcore", region_name="us-east-1")
        t0 = time.time()

        agent_payload = {
            "prompt": user_prompt,
            "sysUserId": sys_user_id
        }

        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENTCORE_RUNTIME_ARN,
            runtimeSessionId=session_id,
            contentType="application/json",
            accept="text/event-stream",
            payload=json.dumps(agent_payload).encode("utf-8"),
        )
        logger.info(f"invoke_agent_runtime returned in {time.time() - t0:.3f}s")

        content_type = response.get("contentType") or response.get("ContentType") or ""
        logger.info(f"AgentCore contentType: {content_type}")

        chunk_count = 0
        first_chunk_time = None

        if "text/event-stream" in content_type:
            logger.info("Entering SSE streaming loop...")

            last_text_sent = None

            for raw_line in response["response"].iter_lines():
                if not raw_line:
                    continue

                decoded = raw_line.decode("utf-8")
                logger.info(f"SSE line: {decoded}")

                if not decoded.startswith("data: "):
                    continue

                data = decoded[6:].strip()
                if not data:
                    continue

                text = ""
                meta = {}

                try:
                    evt = json.loads(data)

                    if isinstance(evt, str):
                        try:
                            evt = ast.literal_eval(evt)
                        except Exception:
                            evt = {"data": evt}

                    if isinstance(evt, dict):
                        if "event" in evt:
                            cbd = evt["event"].get("contentBlockDelta")
                            if cbd and "delta" in cbd and "text" in cbd["delta"]:
                                text = cbd["delta"]["text"]

                        if text == "" and "data" in evt:
                            text = evt.get("data", "")

                        meta = {
                            "chunk_index": evt.get("chunk_index"),
                            "chunk_verbosity_chars": evt.get("chunk_verbosity_chars"),
                        }

                except json.JSONDecodeError:
                    text = data
                    meta = {}

                if not text:
                    continue

                if text == last_text_sent:
                    logger.info(f"Skipping duplicate chunk: {text!r}")
                    continue
                last_text_sent = text

                chunk_count += 1
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    logger.info(f"First streamed chunk after {first_chunk_time - t0:.3f}s")

                api_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps({
                        "chunk": text,
                        "meta": meta,
                        "sessionId": session_id,
                        "sysUserId": sys_user_id
                    })
                )

            logger.info(f"SSE stream ended after {chunk_count} chunks.")

        else:
            logger.info("No SSE detected; falling back to non-streaming read().")

            agent_response = ""
            if "response" in response and hasattr(response["response"], "read"):
                agent_response = response["response"].read().decode("utf-8")

            try:
                parsed_response = json.loads(agent_response)
                clean_message = parsed_response.get("response", agent_response)
            except Exception:
                clean_message = agent_response

            words = clean_message.strip().split()
            chunk = ""
            for i, word in enumerate(words):
                chunk += word + " "
                if len(chunk.split()) >= 5 or i == len(words) - 1:
                    chunk_count += 1

                    api_client.post_to_connection(
                        ConnectionId=connection_id,
                        Data=json.dumps({
                            "chunk": chunk.strip(),
                            "sessionId": session_id,
                            "sysUserId": sys_user_id
                        })
                    )
                    chunk = ""

        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({
                "end": True,
                "sessionId": session_id,
                "sysUserId": sys_user_id
            })
        )

        logger.info(f"Completed streaming for session: {session_id}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        try:
            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({'error': f'Server error: {str(e)}'})
            )
        except Exception:
            pass

    return {'statusCode': 200}

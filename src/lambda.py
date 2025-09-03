import json
import base64
from datetime import datetime, timezone

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",           # adjust for your domain in prod
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Requested-With",
}

def _response(status=200, body=None, headers=None, is_base64=False):
    merged = {**CORS_HEADERS, **(headers or {})}
    if body is None:
        body = ""
    if not isinstance(body, str):
        body = json.dumps(body)
    return {
        "statusCode": status,
        "headers": merged,
        "body": body,
        "isBase64Encoded": is_base64,
    }

def _parse_event(event):
    """
    Normalize API Gateway (REST/HTTP) and Lambda Function URL events.
    Returns (method, path, headers, query, body_bytes, body_json_or_None).
    """
    # Method & path
    method = (
        event.get("requestContext", {})
             .get("http", {})
             .get("method")
        or event.get("httpMethod", "GET")
    )
    path = (
        event.get("rawPath")
        or event.get("path")
        or "/"
    )

    # Headers & query
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    query = event.get("queryStringParameters") or {}
    if query is None:
        query = {}

    # Body (bytes + try json)
    body_b64 = event.get("isBase64Encoded", False)
    body_raw = event.get("body") or ""
    if body_b64 and body_raw:
        body_bytes = base64.b64decode(body_raw)
    else:
        body_bytes = body_raw.encode("utf-8") if isinstance(body_raw, str) else (body_raw or b"")

    body_json = None
    ctype = headers.get("content-type", "")
    if "application/json" in ctype and body_bytes:
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            body_json = None

    return method.upper(), path, headers, query, body_bytes, body_json

# --- Simple router -----------------------------------------------------------

def route(method, path, query, body_json):
    """
    Add/modify routes here. Return a (_response(...)) dict.
    """
    # Health
    if method == "GET" and path == "/health":
        return _response(200, {"ok": True, "time": datetime.now(timezone.utc).isoformat()})

    # Home
    if method == "GET" and path == "/":
        return _response(200, {
            "message": "Hello from Lambda webserver 👋",
            "paths": ["/", "/health", "/echo", "/items/{id}"],
        })

    # Echo JSON
    if method == "POST" and path == "/echo":
        return _response(200, {
            "received": body_json,
            "note": "POST JSON to /echo and I’ll send it back.",
        })

    # Example dynamic path: /items/{id}
    if path.startswith("/items/") and method in {"GET", "PUT", "DELETE"}:
        item_id = path.split("/items/", 1)[1]
        if not item_id:
            return _response(400, {"error": "Missing item id"})
        if method == "GET":
            return _response(200, {"id": item_id, "name": f"Item {item_id}"})
        if method == "PUT":
            return _response(200, {"updated": item_id, "body": body_json})
        if method == "DELETE":
            return _response(204, "")

    # Preflight CORS
    if method == "OPTIONS":
        return _response(204, "")

    # 404
    return _response(404, {"error": "Not found", "method": method, "path": path})

# --- Lambda entrypoint -------------------------------------------------------

def lambda_handler(event, context):
    try:
        method, path, headers, query, body_bytes, body_json = _parse_event(event)
        return route(method, path, query, body_json)
    except Exception as e:
        # Basic error guard with no stack leakage
        return _response(500, {"error": "Internal Server Error", "detail": str(e)})

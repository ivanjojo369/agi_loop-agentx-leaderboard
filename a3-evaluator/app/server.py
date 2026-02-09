import os
import json
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
TASKS: Dict[str, Dict[str, Any]] = {}

# -----------------------------
# Utils básicos
# -----------------------------
def now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()

def public_base_url(port: int, card_url: Optional[str]) -> str:
    if card_url:
        return card_url.rstrip("/")
    return os.getenv("PUBLIC_BASE_URL", f"http://green-agent:{port}").rstrip("/")

def make_agent_card(port: int, card_url: Optional[str]) -> Dict[str, Any]:
    base = public_base_url(port, card_url)
    return {
        "schema_version": "v1",
        "protocolVersion": "0.2.6",
        "name": "AegisForge Agent (Evaluator)",
        "description": "Green evaluator: orchestrates attacker/defender and emits structured JSON results.",
        "url": base,
        "version": "0.3.0",
        "capabilities": {
            # mantenlo en False para que el client no intente SSE si no lo necesitas
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "skills": [
            {
                "id": "general",
                "name": "General Agent Interaction",
                "description": "AgentBeats evaluation (returns JSON results).",
                "tags": ["general", "agentbeats", "evaluation"],
                "examples": ["run the task described in the request"],
                "inputModes": ["application/json", "text/plain"],
                "outputModes": ["application/json", "text/plain"],
            }
        ],
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "endpoints": {
            "health": f"{base}/healthz",
            "agent_card": f"{base}/.well-known/agent-card.json",
            "agent_json": f"{base}/.well-known/agent.json",
            "jsonrpc": f"{base}/",
            "rpc": f"{base}/rpc",
            "jsonrpc2": f"{base}/jsonrpc2",
        },
        "runtime": {"host": "green-agent", "port": port},
    }

@app.get("/healthz")
async def healthz():
    return {"ok": True, "ts": now_iso()}

@app.get("/health")
async def health():
    return {"ok": True, "ts": now_iso()}

@app.get("/.well-known/agent-card.json")
async def agent_card():
    port = int(os.getenv("PORT", "9009"))
    card_url = os.getenv("CARD_URL")
    return JSONResponse(make_agent_card(port, card_url))

@app.get("/.well-known/agent.json")
async def agent_json():
    port = int(os.getenv("PORT", "9009"))
    card_url = os.getenv("CARD_URL")
    return JSONResponse(make_agent_card(port, card_url))

def _jsonrpc_ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}

def _jsonrpc_err(req_id: Any, code: int, msg: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

def _extract_assessment_request(message: Dict[str, Any]) -> Dict[str, Any]:
    parts = (message or {}).get("parts") or []
    # preferimos data
    for p in parts:
        if p.get("kind") == "data" and isinstance(p.get("data"), dict):
            return p["data"]
    # fallback: texto json
    for p in parts:
        if p.get("kind") == "text":
            try:
                j = json.loads((p.get("text") or "").strip())
                if isinstance(j, dict):
                    return j
            except Exception:
                pass
    return {}

def _is_uuidish(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 16:
        return False
    # heurística simple para IDs tipo 019c1163-b141-...
    return all(ch.isalnum() or ch in "-_" for ch in s) and ("-" in s)

def _normalize_endpoint(val: Optional[str], fallback_url: str) -> str:
    """
    - Si val es URL -> úsala.
    - Si val es ID/uuid -> usa fallback.
    - Si val es host:port -> prefix http://
    """
    if not val:
        return fallback_url
    s = val.strip()
    if _is_uuidish(s):
        return fallback_url
    if s.startswith("http://") or s.startswith("https://"):
        return s.rstrip("/") + "/"
    # host:port o hostname
    return ("http://" + s).rstrip("/") + "/"

async def _resolve_jsonrpc_endpoint(base_or_card: str) -> str:
    """
    Si nos pasan agent-card URL, lo resolvemos; si no, intentamos descubrirlo.
    """
    s = (base_or_card or "").strip()
    if not s:
        return ""
    if s.endswith("/.well-known/agent-card.json"):
        async with httpx.AsyncClient(timeout=10) as c:
            card = (await c.get(s)).json()
        ep = (card.get("endpoints") or {}).get("jsonrpc") or card.get("url") or s
        return str(ep).rstrip("/") + "/"

    base = s.rstrip("/") + "/"
    card_url = base + ".well-known/agent-card.json"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            card = (await c.get(card_url)).json()
        ep = (card.get("endpoints") or {}).get("jsonrpc") or card.get("url")
        if ep:
            return str(ep).rstrip("/") + "/"
    except Exception:
        pass
    return base

async def _a2a_message_send(target_jsonrpc: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "data", "data": payload}],
            },
            "metadata": {},
        },
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(target_jsonrpc, json=req)
        r.raise_for_status()
        return r.json()

def _make_artifact(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifactId": str(uuid.uuid4()),
        "name": "results",
        "description": "AgentBeats results payload (JSON).",
        "parts": [{"kind": "data", "data": payload}],
        "metadata": {"mimeType": "application/json"},
    }

def _make_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    # El client valida que existan role/messageId/parts
    return {
        "role": "assistant",
        "messageId": str(uuid.uuid4()),
        "parts": [
            {"kind": "data", "data": payload},
            {"kind": "text", "text": "evaluation complete"},
        ],
    }

def _make_task(task_id: str, context_id: str, message: Dict[str, Any], artifacts: list) -> Dict[str, Any]:
    # CLAVE: incluir "message" y devolver Task directo en result
    return {
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "completed", "timestamp": now_iso()},
        "message": message,
        "artifacts": artifacts,
        "history": [],
    }

async def _run_eval(assessment_request: Dict[str, Any]) -> Dict[str, Any]:
    participants = assessment_request.get("participants") or {}

    attacker_in = participants.get("attacker")
    defender_in = participants.get("defender")

    # fallbacks (override con env vars si quieres)
    attacker_fallback = os.getenv("ATTACKER_URL", "http://attacker:9009/")
    defender_fallback = os.getenv("DEFENDER_URL", "http://defender:9009/")

    attacker = _normalize_endpoint(attacker_in, attacker_fallback)
    defender = _normalize_endpoint(defender_in, defender_fallback)

    result: Dict[str, Any] = {
        "success": True,
        "score": 1.0,
        "ts": now_iso(),
        "participants": {"attacker": attacker_in, "defender": defender_in},
        "resolved_endpoints": {"attacker": attacker, "defender": defender},
        "notes": [],
    }

    # intenta resolver agent-card -> jsonrpc endpoint (si aplica)
    attacker_ep = await _resolve_jsonrpc_endpoint(attacker)
    defender_ep = await _resolve_jsonrpc_endpoint(defender)

    try:
        attacker_resp = await _a2a_message_send(attacker_ep, {"role": "attacker", "assessment_request": assessment_request})
        defender_resp = await _a2a_message_send(defender_ep, {"role": "defender", "assessment_request": assessment_request})
        result["attacker_called"] = True
        result["defender_called"] = True
        # puedes comentar estos raw si se vuelven enormes
        result["attacker_raw"] = attacker_resp
        result["defender_raw"] = defender_resp
        return result
    except Exception as e:
        result["success"] = False
        result["score"] = 0.0
        result["error"] = str(e)
        return result

async def _handle_jsonrpc(body: Dict[str, Any]):
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    if method == "message/send":
        inbound_msg = params.get("message") or {}
        assessment_request = _extract_assessment_request(inbound_msg)

        eval_result = await _run_eval(assessment_request)

        # IMPORTANTE: payload con "results": [...]
        payload = {"results": [eval_result]}

        artifact = _make_artifact(payload)
        out_message = _make_message(payload)

        task_id = str(uuid.uuid4())
        ctx_id = str(uuid.uuid4())
        task = _make_task(task_id, ctx_id, out_message, [artifact])
        TASKS[task_id] = task

        # CLAVE: result = Task DIRECTO
        return JSONResponse(_jsonrpc_ok(req_id, task))

    if method == "tasks/get":
        tid = (params.get("id") or params.get("taskId") or "").strip()
        task = TASKS.get(tid)
        if not task:
            return JSONResponse(_jsonrpc_err(req_id, -32004, "Task not found"))
        return JSONResponse(_jsonrpc_ok(req_id, task))

    return JSONResponse(_jsonrpc_err(req_id, -32601, f"Method not found: {method}"))

@app.post("/")
async def jsonrpc_root(request: Request):
    body = await request.json()
    return await _handle_jsonrpc(body)

@app.post("/rpc")
async def jsonrpc_rpc(request: Request):
    body = await request.json()
    return await _handle_jsonrpc(body)

@app.post("/jsonrpc2")
async def jsonrpc2(request: Request):
    body = await request.json()
    return await _handle_jsonrpc(body)

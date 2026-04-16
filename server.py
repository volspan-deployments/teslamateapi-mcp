from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
import json
from typing import Optional

mcp = FastMCP("TeslaMateApi")

BASE_URL = os.environ.get("TESLAMATE_API_BASE_URL", "http://localhost:8080")
API_TOKEN = os.environ.get("API_TOKEN", "")


def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


@mcp.tool()
async def get_cars() -> dict:
    """Retrieve a list of all Tesla vehicles tracked by TeslaMate. Use this as the starting point to discover available car IDs before querying any car-specific data."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars",
            headers=get_headers()
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_status(car_id: int) -> dict:
    """Get the current real-time status of a specific Tesla vehicle from MQTT, including location, battery level, charging state, doors, climate, and other live telemetry. Use this when the user asks about the current state of their car."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/status",
            headers=get_headers()
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_drives(
    car_id: int,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
) -> dict:
    """Retrieve a paginated list of past driving sessions for a specific Tesla vehicle, including distance, duration, start/end locations, and efficiency. Use this when the user wants to review their driving history."""
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/drives",
            headers=get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_drive_details(car_id: int, drive_id: int) -> dict:
    """Get detailed information about a specific drive session, including full route data, speed, power usage, and efficiency breakdown. Use this when the user wants to inspect a particular trip in depth."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/drives/{drive_id}",
            headers=get_headers()
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_charges(
    car_id: int,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
) -> dict:
    """Retrieve a paginated list of past charging sessions for a specific Tesla vehicle, including energy added, cost, duration, and charging location. Use this to review charging history or analyze energy costs."""
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/charges",
            headers=get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_charge_details(car_id: int, charge_id: int) -> dict:
    """Get detailed data about a specific charging session, including charge curves, power levels over time, and efficiency metrics. Use this when the user wants to inspect a particular charge event."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/charges/{charge_id}",
            headers=get_headers()
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_battery_health(car_id: int) -> dict:
    """Retrieve battery health history for a Tesla vehicle, showing degradation over time, usable vs rated range, and capacity estimates. Use this when the user asks about battery condition or long-term degradation."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/battery_health",
            headers=get_headers()
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def send_car_command(
    car_id: int,
    command: str,
    body: Optional[str] = None
) -> dict:
    """Send a command to a Tesla vehicle through TeslaMate, such as locking/unlocking doors, honking the horn, flashing lights, enabling sentry mode, controlling climate, or waking the car. Use this when the user wants to remotely control their Tesla. Requires commands to be enabled via environment variables on the server.

    Available command paths:
    - /wake_up
    - /command/door_lock
    - /command/door_unlock
    - /command/honk_horn
    - /command/flash_lights
    - /command/set_sentry_mode
    - /command/auto_conditioning_start
    - /command/auto_conditioning_stop
    - /logging/resume
    - /logging/suspend
    - And many more (charging, climate, trunk, windows, etc.)
    """
    headers = get_headers()
    url = f"{BASE_URL}/api/v1/cars/{car_id}{command}"

    json_body = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON body provided: {body}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if json_body is not None:
            response = await client.post(
                url,
                headers=headers,
                json=json_body
            )
        else:
            response = await client.post(
                url,
                headers=headers
            )
        response.raise_for_status()
        try:
            return response.json()
        except Exception:
            return {"status": response.status_code, "message": response.text}




_SERVER_SLUG = "teslamateapi"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

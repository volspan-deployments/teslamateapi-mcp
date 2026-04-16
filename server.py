from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
from typing import Optional, List, Any

mcp = FastMCP("TeslaMateApi")

BASE_URL = os.environ.get("TESLAMATE_API_URL", "http://localhost:8080")
API_TOKEN = os.environ.get("API_TOKEN", "")


def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


@mcp.tool()
async def get_cars() -> dict:
    """Retrieve a list of all Tesla vehicles registered in TeslaMate. Use this as the starting point to discover available car IDs before querying car-specific data."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars",
            headers=get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_status(car_id: int) -> dict:
    """Get the current real-time status of a specific Tesla vehicle, including location, battery level, charging state, speed, and other live data sourced from MQTT. Use this when the user wants to know what their car is doing right now."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/status",
            headers=get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_battery_health(car_id: int) -> dict:
    """Retrieve historical battery health data for a specific Tesla vehicle, showing battery degradation over time. Use this when the user wants to understand how their battery capacity has changed."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/battery_health",
            headers=get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_charges(
    car_id: int,
    page: Optional[int] = 1,
    per_page: Optional[int] = 25
) -> dict:
    """Retrieve a paginated list of past charging sessions for a specific Tesla vehicle. Use this when the user wants an overview of their charging history, costs, or energy added."""
    params = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/charges",
            headers=get_headers(),
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_charge_details(car_id: int, charge_id: int) -> dict:
    """Retrieve detailed information about a specific charging session, including energy added, cost, duration, and charge curve data. Use this when the user wants to inspect a particular charge event."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/charges/{charge_id}",
            headers=get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_drives(
    car_id: int,
    page: Optional[int] = 1,
    per_page: Optional[int] = 25
) -> dict:
    """Retrieve a paginated list of past driving sessions for a specific Tesla vehicle, including distance, duration, energy used, and efficiency. Use this when the user wants to review their driving history."""
    params = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/drives",
            headers=get_headers(),
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_car_drive_details(car_id: int, drive_id: int) -> dict:
    """Retrieve detailed information about a specific driving session, including route, speed, energy consumption, and efficiency metrics. Use this when the user wants to inspect a particular trip."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/cars/{car_id}/drives/{drive_id}",
            headers=get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def send_car_command(
    car_id: int,
    command: str,
    parameters: Optional[List[Any]] = None
) -> dict:
    """Send a command to a Tesla vehicle through the TeslaMate API. Supported commands include wake_up, door_lock, door_unlock, honk_horn, flash_lights, set_sentry_mode, climate controls, charging controls, and TeslaMate logging controls. Use this when the user wants to remotely control their vehicle. Requires commands to be enabled via environment variables on the server."""
    # Normalize command path: strip leading slash for URL building
    command_path = command.lstrip("/")

    url = f"{BASE_URL}/api/v1/cars/{car_id}/{command_path}"

    # Build request body if parameters provided
    body = None
    if parameters is not None and len(parameters) > 0:
        # If parameters is a list with a single dict, use that dict as the body
        if len(parameters) == 1 and isinstance(parameters[0], dict):
            body = parameters[0]
        else:
            body = {"parameters": parameters}

    async with httpx.AsyncClient() as client:
        if body is not None:
            response = await client.post(
                url,
                headers=get_headers(),
                json=body,
                timeout=60.0
            )
        else:
            response = await client.post(
                url,
                headers=get_headers(),
                timeout=60.0
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

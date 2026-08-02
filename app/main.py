import os
import time
import httpx
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

HERMES_URL = os.environ.get("HERMES_INTERNAL_URL", "http://127.0.0.1:9119")
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
COOKIE_SECRET = os.environ.get("COOKIE_SECRET", "")
SESSION_TTL = 60 * 60 * 12
COOKIE_NAME = "gw_session"

if not DASHBOARD_PASSWORD:
    raise RuntimeError("DASHBOARD_PASSWORD wajib diisi")
if not COOKIE_SECRET:
    raise RuntimeError("COOKIE_SECRET wajib diisi")

serializer = URLSafeTimedSerializer(COOKIE_SECRET)

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def make_session_cookie() -> str:
    return serializer.dumps({"user": DASHBOARD_USER})


def verify_session(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        serializer.loads(token, max_age=SESSION_TTL)
        return True
    except (BadSignature, SignatureExpired):
        return False


async def require_auth(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if verify_session(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if username != DASHBOARD_USER or password != DASHBOARD_PASSWORD:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Username atau password salah"},
            status_code=401,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        make_session_cookie(),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


async def hermes_get(path: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{HERMES_URL}{path}")
        r.raise_for_status()
        return r.json()


async def hermes_put(path: str, body: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.put(f"{HERMES_URL}{path}", json=body)
        r.raise_for_status()
        return r.json()


async def hermes_post(path: str, body: dict | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{HERMES_URL}{path}", json=body or {})
        r.raise_for_status()
        return r.json()


async def safe_status():
    try:
        return await hermes_get("/api/status")
    except Exception:
        return {"gateway": {"running": False}, "version": "?"}


@app.get("/", response_class=HTMLResponse)
async def setup_page(request: Request, _=Depends(require_auth)):
    status = await safe_status()
    try:
        config = await hermes_get("/api/config")
    except Exception:
        config = {}
    providers = config.get("providers", {})
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "status": status,
            "providers": providers,
            "hermes_url": HERMES_URL,
            "saved": None,
        },
    )


@app.get("/fragments/status", response_class=HTMLResponse)
async def status_fragment(request: Request, _=Depends(require_auth)):
    status = await safe_status()
    return templates.TemplateResponse("_status_pill.html", {"request": request, "status": status})


@app.post("/provider/save", response_class=HTMLResponse)
async def provider_save(
    request: Request,
    provider_key: str = Form(...),
    display_name: str = Form(""),
    base_url: str = Form(...),
    api_key: str = Form(""),
    transport: str = Form("chat_completions"),
    default_model: str = Form(...),
    _=Depends(require_auth),
):
    key_env = f"HERMES_PROVIDER_{provider_key.upper()}_KEY"

    if api_key:
        await hermes_put("/api/env", {"key": key_env, "value": api_key})

    config = await hermes_get("/api/config")
    providers = config.get("providers", {})
    providers[provider_key] = {
        "api": base_url,
        "name": display_name or provider_key,
        "key_env": key_env,
        "transport": transport,
        "default_model": default_model,
        "enabled": True,
    }
    config["providers"] = providers
    config.setdefault("model", {})
    config["model"]["provider"] = provider_key
    config["model"]["default"] = default_model
    await hermes_put("/api/config", {"config": config})

    status = await safe_status()
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "status": status,
            "providers": providers,
            "hermes_url": HERMES_URL,
            "saved": provider_key,
        },
    )


@app.post("/gateway/restart", response_class=HTMLResponse)
async def gateway_restart(request: Request, _=Depends(require_auth)):
    try:
        await hermes_post("/api/gateway/restart")
    except Exception:
        pass
    time.sleep(1)
    status = await safe_status()
    return templates.TemplateResponse("_status_pill.html", {"request": request, "status": status})


@app.api_route("/dashboard/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def dashboard_proxy(request: Request, path: str, _=Depends(require_auth)):
    url = f"{HERMES_URL}/{path}"
    body = await request.body()
    async with httpx.AsyncClient(timeout=30) as client:
        upstream = await client.request(
            request.method,
            url,
            params=request.query_params,
            content=body,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
        )
    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)

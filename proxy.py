import os, json, logging, mimetypes
from pathlib import Path
from aiohttp import web, ClientSession, ClientTimeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("proxy")

API_KEY  = os.environ.get("API_KEY", "")
UPSTREAM = os.environ.get("UPSTREAM", "http://copilot-api:4141").rstrip("/")
DASH_DIR = Path(os.environ.get("DASH_DIR", "/app/dashboard"))
HOP_HDRS = {"host", "content-length", "connection", "transfer-encoding", "content-encoding"}


def needs_rewrite(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3")


async def serve_static(rel: str) -> web.Response:
    rel = rel.lstrip("/") or "index.html"
    fp = (DASH_DIR / rel).resolve()
    try:
        fp.relative_to(DASH_DIR.resolve())
    except ValueError:
        return web.Response(status=403, text="forbidden")
    if not fp.exists():
        fp = DASH_DIR / "index.html"
    if not fp.exists():
        return web.Response(status=404, text="dashboard not deployed")
    ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
    return web.Response(body=fp.read_bytes(), content_type=ctype)


async def proxy_upstream(request: web.Request) -> web.StreamResponse:
    if request.headers.get("Authorization", "") != f"Bearer {API_KEY}":
        return web.json_response({"error": "unauthorized"}, status=401)

    body = await request.read()
    if body:
        try:
            j = json.loads(body)
            model = j.get("model", "")
            if needs_rewrite(model) and "max_tokens" in j and "max_completion_tokens" not in j:
                j["max_completion_tokens"] = j.pop("max_tokens")
                body = json.dumps(j).encode()
                log.info("rewrote max_tokens -> max_completion_tokens for %s", model)
        except Exception as e:
            log.warning("body rewrite skipped: %s", e)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HDRS}
    timeout = ClientTimeout(total=600)
    async with ClientSession(timeout=timeout, auto_decompress=False) as session:
        async with session.request(
            request.method,
            UPSTREAM + request.path_qs,
            headers=headers,
            data=body if body else None,
        ) as up:
            resp_headers = {k: v for k, v in up.headers.items() if k.lower() not in HOP_HDRS}
            response = web.StreamResponse(status=up.status, headers=resp_headers)
            await response.prepare(request)
            async for chunk in up.content.iter_any():
                await response.write(chunk)
            await response.write_eof()
            return response


async def handler(request: web.Request) -> web.StreamResponse:
    path = request.path
    if path == "/":
        raise web.HTTPFound("/dashboard/")
    if path == "/dashboard" or path == "/dashboard/":
        return await serve_static("index.html")
    if path.startswith("/dashboard/"):
        return await serve_static(path[len("/dashboard/"):])
    return await proxy_upstream(request)


app = web.Application(client_max_size=64 * 1024 * 1024)
app.router.add_route("*", "/{tail:.*}", handler)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=4141)

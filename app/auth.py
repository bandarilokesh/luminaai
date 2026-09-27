"""Optional shared access code. Active only when ACCESS_CODE is set in .env."""
import hashlib
import hmac

from fastapi import Request

from app.config import settings

COOKIE_NAME = "lumina_access"
OPEN_PATHS = ("/health", "/api/auth/login", "/static/")


def session_token() -> str:
    return hashlib.sha256(f"lumina:{settings.ACCESS_CODE}".encode()).hexdigest()


def is_authorized(request: Request) -> bool:
    if not settings.ACCESS_CODE:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE_NAME, ""), session_token())


def check_code(code: str) -> bool:
    return bool(settings.ACCESS_CODE) and hmac.compare_digest(code, settings.ACCESS_CODE)


LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Lumina AI - Access Required</title>
<style>
  body { font-family: system-ui, sans-serif; background:#0b1326; color:#dae2fd; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
  .box { background:#171f33; padding:2.5rem; border-radius:12px; width:min(320px, calc(100vw - 32px)); box-sizing:border-box; text-align:center; }
  p { color:#908fa0; font-size:.9rem; }
  input, button { width:100%; padding:.7rem; border-radius:8px; box-sizing:border-box; font-size:1rem; }
  input { border:1px solid #464555; background:#0b1326; color:#dae2fd; }
  button { margin-top:1rem; border:none; background:#8083ff; color:#fff; cursor:pointer; }
  #err { color:#ffb4ab; font-size:.85rem; margin-top:.75rem; min-height:1rem; }
</style>
</head>
<body>
  <form class="box" id="f">
    <h1>Lumina AI</h1>
    <p>Enter the access code to continue.</p>
    <input id="code" type="password" placeholder="Access code" autofocus required />
    <button type="submit">Enter</button>
    <div id="err"></div>
  </form>
  <script>
    document.getElementById('f').addEventListener('submit', async (e) => {
      e.preventDefault();
      const res = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: document.getElementById('code').value })
      });
      if (res.ok) window.location.reload();
      else document.getElementById('err').textContent = 'Incorrect code, try again.';
    });
  </script>
</body>
</html>
"""

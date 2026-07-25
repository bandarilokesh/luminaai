import hmac

from fastapi import Request

from config.settings import settings

COOKIE_NAME = "lumina_access"

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Lumina AI - Access Required</title>
<style>
  body { font-family: system-ui, sans-serif; background:#0f1115; color:#eee; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }
  .box { background:#1a1d24; padding:2.5rem; border-radius:12px; width:320px; text-align:center; box-shadow:0 10px 30px rgba(0,0,0,.4); }
  h1 { font-size:1.3rem; margin-bottom:.5rem; }
  p { color:#999; font-size:.9rem; margin-bottom:1.5rem; }
  input { width:100%; padding:.7rem; border-radius:8px; border:1px solid #333; background:#0f1115; color:#eee; box-sizing:border-box; font-size:1rem; }
  button { width:100%; margin-top:1rem; padding:.7rem; border-radius:8px; border:none; background:#6c5ce7; color:#fff; font-size:1rem; cursor:pointer; }
  button:hover { background:#5a4bd6; }
  #err { color:#ff6b6b; font-size:.85rem; margin-top:.75rem; min-height:1rem; }
</style>
</head>
<body>
  <div class="box">
    <h1>Lumina AI</h1>
    <p>Enter the access code to continue.</p>
    <form id="f">
      <input id="code" type="password" placeholder="Access code" autofocus required />
      <button type="submit">Enter</button>
      <div id="err"></div>
    </form>
  </div>
  <script>
    document.getElementById('f').addEventListener('submit', async (e) => {
      e.preventDefault();
      const code = document.getElementById('code').value;
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      if (res.ok) {
        window.location.reload();
      } else {
        document.getElementById('err').textContent = 'Incorrect code, try again.';
      }
    });
  </script>
</body>
</html>
"""


def is_authorized(request: Request) -> bool:
    """Return True if no access code is configured, or the visitor's cookie matches it."""
    if not settings.ACCESS_CODE:
        return True
    cookie_value = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(cookie_value, settings.ACCESS_CODE)

# Production Tasks

Checklist of items to address before deploying to production.

---

## Security Headers

### `frame-ancestors 'none'` (Clickjacking Protection)

**Status:** ⚠️ Not currently active — removed from `<meta>` tag in `apps/a2ui-chat/index.html` because browsers ignore `frame-ancestors` when delivered via `<meta>`. Must be set as an HTTP response header at the server/CDN level.

**Why it matters:** Prevents attackers from embedding your app in a hidden `<iframe>` to trick authenticated users into performing unintended actions (clickjacking). Especially relevant because the app uses Auth0 authentication and sends user input to LLMs.

**What to add** (pick one based on your hosting):

#### Nginx
```nginx
add_header Content-Security-Policy "frame-ancestors 'none'" always;
add_header X-Frame-Options "DENY" always;
```

#### Cloudflare Pages (`public/_headers`)
```
/*
  Content-Security-Policy: frame-ancestors 'none'
  X-Frame-Options: DENY
```

#### Vercel (`vercel.json`)
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Content-Security-Policy", "value": "frame-ancestors 'none'" },
        { "key": "X-Frame-Options", "value": "DENY" }
      ]
    }
  ]
}
```

#### Netlify (`_headers` or `netlify.toml`)
```
/*
  Content-Security-Policy: frame-ancestors 'none'
  X-Frame-Options: DENY
```

#### FastAPI (Python backend)
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware import Middleware
from starlette.responses import Response

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

> **Note:** `X-Frame-Options: DENY` is included as a fallback for older browsers that don't support CSP `frame-ancestors`.
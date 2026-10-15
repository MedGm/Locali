# Locali web app

Next.js (App Router, TypeScript, Tailwind) in front of the FastAPI backend. The browser only talks
to Next.js; `src/app/api/[...path]/route.ts` forwards `/api/*` to FastAPI on the server side and
adds the API token, so the token never reaches the browser.

```
# backend (from the repository root)
LOCALI_API_TOKEN=<token> uv run uvicorn backend.app:default_app --factory --port 8000

# web app (here)
LOCALI_API_TOKEN=<same token> npm run dev
```

`LOCALI_API_URL` changes the backend address (default `http://127.0.0.1:8000`). Page plan:
`docs/ui-design.md`.

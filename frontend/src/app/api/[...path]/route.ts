// Forwards /api/* to the FastAPI backend from the server side, adding the API token.
// The browser never sees the token, and FastAPI can stay bound to localhost.
// Only content-type/accept go upstream and only content-type comes back, so no headers leak
// either way. Bodies are streamed through, which keeps Server-Sent Events working.

const BACKEND = process.env.LOCALI_API_URL ?? "http://127.0.0.1:8000";

async function forward(request: Request, ctx: RouteContext<"/api/[...path]">) {
  const token = process.env.LOCALI_API_TOKEN;
  if (!token) {
    return Response.json({ detail: "LOCALI_API_TOKEN is not set for the web app" }, { status: 500 });
  }
  const { path } = await ctx.params;
  const url = new URL(path.map(encodeURIComponent).join("/"), BACKEND + "/");
  url.search = new URL(request.url).search;

  const headers = new Headers({ authorization: `Bearer ${token}` });
  for (const name of ["content-type", "accept"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(url, { method: request.method, headers, body, cache: "no-store" });
  } catch {
    return Response.json({ detail: "backend unreachable" }, { status: 502 });
  }
  const out = new Headers();
  const type = upstream.headers.get("content-type");
  if (type) out.set("content-type", type);
  if (type?.startsWith("text/event-stream")) out.set("cache-control", "no-cache");
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST, forward as DELETE };

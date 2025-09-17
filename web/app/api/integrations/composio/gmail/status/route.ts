export const runtime = 'nodejs';

export async function POST(req: Request) {
  let body: any = {};
  try { body = await req.json(); } catch {}
  const userId = body?.userId || '';
  const connectionRequestId = body?.connectionRequestId || '';

  const serverBase = process.env.PY_SERVER_URL || 'http://localhost:8001';
  const base = serverBase.replace(/\/$/, '');
  const statusPath = process.env.PY_GMAIL_STATUS_PATH || '/api/v1/integrations/composio/gmail/status';
  const url = `${base}${statusPath}`;
  const payload: any = {};
  if (userId) payload.user_id = userId;
  if (connectionRequestId) payload.connection_request_id = connectionRequestId;

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    return new Response(JSON.stringify(data), {
      status: resp.status,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  } catch (e: any) {
    return new Response(
      JSON.stringify({ ok: false, error: 'Upstream error', detail: e?.message || String(e) }),
      { status: 502, headers: { 'Content-Type': 'application/json; charset=utf-8' } }
    );
  }
}

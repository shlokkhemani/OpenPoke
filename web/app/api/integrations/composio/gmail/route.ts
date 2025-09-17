export const runtime = 'nodejs';

export async function POST(req: Request) {
  let body: any = {};
  try {
    body = await req.json();
  } catch {}
  const userId = body?.userId || '';
  const authConfigId = body?.authConfigId || process.env.COMPOSIO_GMAIL_AUTH_CONFIG_ID || '';

  const serverBase = process.env.PY_SERVER_URL || 'http://localhost:8001';
  const base = serverBase.replace(/\/$/, '');
  const connectPath = process.env.PY_GMAIL_CONNECT_PATH || '/api/v1/integrations/composio/gmail/connect';
  const url = `${base}${connectPath}`;

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ user_id: userId, auth_config_id: authConfigId }),
    });
    const data = await resp.json().catch(() => ({}));
    const status = resp.status;
    return new Response(JSON.stringify(data), {
      status,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  } catch (e: any) {
    return new Response(
      JSON.stringify({ ok: false, error: 'Upstream error', detail: e?.message || String(e) }),
      { status: 502, headers: { 'Content-Type': 'application/json; charset=utf-8' } }
    );
  }
}

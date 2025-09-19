export const runtime = 'nodejs';

// Proxy chat requests to a Python backend that performs generation and streams text.
// Converts UI messages to {role, content} and normalizes SSE to plain text.

type UIMsgPart = { type: string; text?: string };
type UIMessage = { role: string; parts?: UIMsgPart[]; content?: string };

function uiToOpenAIContent(messages: UIMessage[]): { role: string; content: string }[] {
  const out: { role: string; content: string }[] = [];
  for (const m of messages || []) {
    const role = m?.role;
    if (!role) continue;
    let content = '';
    if (Array.isArray(m.parts)) {
      content = m.parts.filter((p) => p?.type === 'text').map((p) => p.text || '').join('');
    } else if (typeof m.content === 'string') {
      content = m.content;
    }
    out.push({ role, content });
  }
  return out;
}

export async function POST(req: Request) {
  const rid = Math.random().toString(36).slice(2);
  let body: any;
  try {
    body = await req.json();
  } catch (e) {
    console.error(`[chat-proxy][${rid}] invalid json`, e);
    return new Response('Invalid JSON', { status: 400 });
  }

  const { messages, apiKey, model } = body || {};
  if (!Array.isArray(messages)) {
    return new Response('Missing messages', { status: 400 });
  }

  const serverBase = process.env.PY_SERVER_URL || 'http://localhost:8001';
  const serverPath = process.env.PY_CHAT_PATH || '/api/v1/chat/send';
  const urlBase = `${serverBase.replace(/\/$/, '')}${serverPath}`;

  const configuredMethod = (process.env.PY_SERVER_METHOD || 'POST').toUpperCase();
  const promptParam = process.env.PY_PROMPT_PARAM || 'prompt';
  const modelParam = process.env.PY_MODEL_PARAM || 'model';
  const keyParam = process.env.PY_KEY_PARAM || 'api_key';
  const systemParam = process.env.PY_SYSTEM_PARAM || 'system';

  const payload = {
    model: model || process.env.OPENROUTER_MODEL || 'openrouter/auto',
    system: '',
    messages: uiToOpenAIContent(messages),
    stream: true,
    api_key: apiKey || process.env.OPENROUTER_API_KEY,
  };

  console.log(`[chat-proxy][${rid}] targeting`, {
    messages: payload.messages.length,
    model: payload.model,
    hasKey: !!payload.api_key,
    method: configuredMethod,
    url: urlBase,
  });

  function buildPromptFromMessages(ms: { role: string; content: string }[]): string {
    // Prefer last user message; fallback to all messages concatenated
    const lastUser = [...ms].reverse().find((m) => m.role === 'user' && m.content);
    if (lastUser?.content) return lastUser.content;
    return ms.map((m) => `${m.role}: ${m.content}`).join('\n');
  }

  async function requestPOST(url: string): Promise<Response> {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, text/plain, */*' },
      body: JSON.stringify(payload),
    });
  }

  async function requestGET(url: string): Promise<Response> {
    const u = new URL(url);
    const prompt = buildPromptFromMessages(payload.messages);
    u.searchParams.set(promptParam, prompt);
    u.searchParams.set(modelParam, String(payload.model || ''));
    if (payload.api_key) u.searchParams.set(keyParam, String(payload.api_key));
    if (payload.system != null) u.searchParams.set(systemParam, String(payload.system));
    return fetch(u.toString(), { method: 'GET', headers: { Accept: 'text/event-stream, text/plain, */*' } });
  }

  let resp: Response;
  try {
    resp = configuredMethod === 'GET' ? await requestGET(urlBase) : await requestPOST(urlBase);
    if (resp.status === 405 || resp.status === 501) {
      console.warn(`[chat-proxy][${rid}] ${resp.status} from upstream; retrying with alternate method`);
      resp = configuredMethod === 'GET' ? await requestPOST(urlBase) : await requestGET(urlBase);
    }
  } catch (e: any) {
    console.error(`[chat-proxy][${rid}] upstream error`, e);
    return new Response(e?.message || 'Upstream error', { status: 502 });
  }

  const contentType = resp.headers.get('content-type') || '';
  if (!contentType.includes('text/event-stream')) {
    return new Response(resp.body, {
      status: resp.status,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }

  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  const readable = new ReadableStream<Uint8Array>({
    start(controller) {
      const reader = (resp.body as any).getReader();
      let shouldClose = false;
      let closed = false;
      let buf = '';
      function pushText(t: string) {
        if (!t) return;
        controller.enqueue(encoder.encode(t));
      }
      function parseSseChunk(chunk: string) {
        const lines = chunk.split(/\r?\n/);
        for (const line of lines) {
          if (!line) continue;
          if (line.startsWith('data:')) {
            const data = line.slice(5).trim();
            if (!data) continue;
            if (data === '[DONE]') {
              // mark for closure; actual close happens in read loop
              shouldClose = true;
              return;
            }
            try {
              const j = JSON.parse(data);
              const choices = j?.choices || [];
              const delta = choices[0]?.delta || {};
              if (typeof delta.content === 'string') pushText(delta.content);
              if (typeof (j as any)?.text === 'string') pushText((j as any).text);
            } catch {
              pushText(data + '\n');
            }
          }
        }
      }
      function doClose() {
        if (closed) return;
        closed = true;
        try { reader.cancel(); } catch {}
        try { controller.close(); } catch {}
      }
      function read() {
        reader
          .read()
          .then(({ done, value }: any) => {
            if (done) {
              doClose();
              return;
            }
            if (shouldClose) {
              doClose();
              return;
            }
            buf += decoder.decode(value, { stream: true });
            let idx;
            while ((idx = buf.indexOf('\n\n')) !== -1) {
              const eventChunk = buf.slice(0, idx);
              buf = buf.slice(idx + 2);
              parseSseChunk(eventChunk);
            }
            if (shouldClose) {
              doClose();
              return;
            }
            read();
          })
          .catch((err: any) => {
            if (closed || shouldClose) return;
            console.error(`[chat-proxy][${rid}] stream read error`, err);
            try { controller.error(err); } catch {}
          });
      }
      read();
    },
  });

  return new Response(readable, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}

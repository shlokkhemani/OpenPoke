'use client';

import { useChat } from '@ai-sdk/react';
import { TextStreamChatTransport } from 'ai';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import SettingsModal, { useSettings } from '@/components/SettingsModal';
import clsx from 'clsx';

export default function Page() {
  const { settings, setSettings, settingsRef } = useSettings();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');

  // Provide settings to each request via transport body
  const transport = useMemo(() => new TextStreamChatTransport({
    api: '/api/chat',
    body: () => ({
      apiKey: settingsRef.current.apiKey,
      model: settingsRef.current.model,
    }),
  }), [settingsRef]);

  const { messages, sendMessage, status, stop, error, setMessages, clearError } = useChat({
    transport,
  });

  const loadHistory = useCallback(
    async ({ signal }: { signal?: AbortSignal } = {}) => {
      try {
        const res = await fetch('/api/chat/history', { cache: 'no-store', signal });
        if (!res.ok) return;
        const data = await res.json();
        if (!Array.isArray(data?.messages)) return;
        if (signal?.aborted) return;
        const stamp = Date.now();
        const hydrated = data.messages
          .filter(
            (m: any) =>
              typeof m?.role === 'string' &&
              typeof m?.content === 'string' &&
              m.content.trim().length > 0,
          )
          .map((m: any, idx: number) => ({
            id: `history-${stamp}-${idx}-${m.role}`,
            role: m.role,
            parts: [{ type: 'text', text: m.content }],
          }));
        setMessages(hydrated);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.error('Failed to load chat history', err);
      }
    },
    [setMessages],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadHistory({ signal: controller.signal });
    return () => controller.abort();
  }, [loadHistory]);

  const previousStatusRef = useRef(status);

  useEffect(() => {
    const previous = previousStatusRef.current;
    previousStatusRef.current = status;
    if (previous !== status && previous !== 'ready' && status === 'ready') {
      const controller = new AbortController();
      loadHistory({ signal: controller.signal });
      return () => controller.abort();
    }
    return undefined;
  }, [status, loadHistory]);

  const canSubmit = status === 'ready' && settings.apiKey.trim().length > 0;

  const renderMessages = () => {
    return (
      <div className="flex h-[70vh] flex-col gap-2 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mx-auto my-12 max-w-sm text-center text-gray-500">
            <h2 className="mb-2 text-xl font-semibold text-gray-700">Start a conversation</h2>
            <p className="text-sm">Your messages will appear here. Configure your OpenRouter key and model in Settings.</p>
          </div>
        )}
        {messages.map((m, idx) => {
          const isUser = m.role === 'user';
          const isDraft = m.role === 'draft';
          const next = messages[idx + 1];
          const tail = !next || next.role !== m.role;
          const text = m.parts.map((p, i) => {
            if (p.type !== 'text') return null;
            return (
              <span
                key={i}
                className={isDraft ? 'block whitespace-pre-wrap' : undefined}
              >
                {p.text}
              </span>
            );
          });
          return (
            <div key={m.id} className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
              <div
                className={clsx(
                  isUser ? 'bubble-out' : 'bubble-in',
                  tail ? (isUser ? 'bubble-tail-out' : 'bubble-tail-in') : '',
                  isDraft && 'whitespace-pre-wrap'
                )}
              >
                {text}
              </div>
            </div>
          );
        })}
        {(status === 'submitted' || status === 'streaming') && (messages[messages.length - 1]?.role === 'user') && (
          <div className="flex justify-start">
            <div className="typing">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="chat-bg min-h-screen p-4 sm:p-6">
      <div className="chat-wrap flex flex-col">
        <header className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-brand-600 text-white grid place-items-center font-semibold">OP</div>
          <div>
            <h1 className="text-lg font-semibold">OpenPoke Chat</h1>
            <p className="text-xs text-gray-500">OpenRouter + Vercel AI SDK</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50"
            onClick={() => setOpen(true)}
          >
            Settings
          </button>
          <button
            className="rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50"
            onClick={async () => {
              let cleared = false;
              try {
                const res = await fetch('/api/chat/history', { method: 'DELETE' });
                cleared = res.ok;
                if (!res.ok) {
                  console.error('Failed to clear chat history', res.statusText);
                }
              } catch (err) {
                console.error('Failed to clear chat history', err);
              }
              if (cleared) {
                setMessages([]);
              }
            }}
          >
            Clear
          </button>
        </div>
        </header>

        <div className="card flex-1 overflow-hidden">
          {renderMessages()}
          <div className="border-t border-gray-200 p-3">
            {error && (
              <div className="mb-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                <div className="flex items-center justify-between">
                  <span>Something went wrong.</span>
                  <button className="underline" onClick={() => clearError()}>Dismiss</button>
                </div>
                <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-xs text-red-600">{String(error.message || error)}</pre>
              </div>
            )}
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (input.trim()) {
                  sendMessage({ text: input });
                  setInput('');
                }
              }}
            >
              <input
                className="input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!canSubmit}
                placeholder={settings.apiKey ? 'iMessage…' : 'Add your OpenRouter API key in Settings to start'}
              />
              {status === 'streaming' || status === 'submitted' ? (
                <button type="button" className="rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50" onClick={() => stop()}>
                  Stop
                </button>
              ) : (
                <button type="submit" className="btn" disabled={!canSubmit}>
                  Send
                </button>
              )}
            </form>
            <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
              <div>
                Status: <span className="chip">{status}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="chip">Model: {settings.model || 'openrouter/auto'}</span>
              </div>
            </div>
          </div>
        </div>

        <SettingsModal
          open={open}
          onClose={() => setOpen(false)}
          settings={settings}
          onSave={(s) => setSettings(s)}
        />
      </div>
    </main>
  );
}

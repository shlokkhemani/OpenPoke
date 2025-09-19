'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import SettingsModal, { useSettings } from '@/components/SettingsModal';
import clsx from 'clsx';

type ChatBubble = {
  id: string;
  role: string;
  text: string;
};

const POLL_INTERVAL_MS = 1500;

const isRenderableMessage = (entry: any) =>
  typeof entry?.role === 'string' &&
  typeof entry?.content === 'string' &&
  entry.content.trim().length > 0;

const toBubbles = (payload: any): ChatBubble[] => {
  if (!Array.isArray(payload?.messages)) return [];

  return payload.messages
    .filter(isRenderableMessage)
    .map((message: any, index: number) => ({
      id: `history-${index}`,
      role: message.role,
      text: message.content,
    }));
};

export default function Page() {
  const { settings, setSettings } = useSettings();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/chat/history', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      setMessages(toBubbles(data));
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      console.error('Failed to load chat history', err);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);


  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void loadHistory();
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [loadHistory]);

  const hasApiKey = settings.apiKey.trim().length > 0;
  const canSubmit = hasApiKey && input.trim().length > 0;

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      setError(null);
      setIsWaitingForResponse(true);

      // Optimistically add the user message immediately
      const userMessage: ChatBubble = {
        id: `user-${Date.now()}`,
        role: 'user',
        text: trimmed,
      };
      setMessages(prev => {
        const newMessages = [...prev, userMessage];
        return newMessages;
      });

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: [{ role: 'user', content: trimmed }],
            apiKey: settings.apiKey,
            model: settings.model,
          }),
        });

        if (!(res.ok || res.status === 202)) {
          const detail = await res.text();
          throw new Error(detail || `Request failed (${res.status})`);
        }
      } catch (err: any) {
        console.error('Failed to send message', err);
        setError(err?.message || 'Failed to send message');
        // Remove the optimistic message on error
        setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
        setIsWaitingForResponse(false);
        throw err instanceof Error ? err : new Error('Failed to send message');
      } finally {
        // Poll until we get the assistant's response
        let pollAttempts = 0;
        const maxPollAttempts = 30; // Max 30 attempts (30 seconds)
        
        const pollForAssistantResponse = async () => {
          pollAttempts++;
          
          try {
            const res = await fetch('/api/chat/history', { cache: 'no-store' });
            if (res.ok) {
              const data = await res.json();
              const currentMessages = toBubbles(data);
              
              // Check if the last message is from assistant and contains our user message
              const lastMessage = currentMessages[currentMessages.length - 1];
              const hasUserMessage = currentMessages.some(msg => msg.text === trimmed && msg.role === 'user');
              const hasAssistantResponse = lastMessage?.role === 'assistant' && hasUserMessage;
              
              if (hasAssistantResponse) {
                // We got the assistant response, update messages and stop loading
                setMessages(currentMessages);
                setIsWaitingForResponse(false);
                return;
              }
            }
          } catch (err) {
            console.error('Error polling for response:', err);
          }
          
          // Continue polling if we haven't exceeded max attempts
          if (pollAttempts < maxPollAttempts) {
            setTimeout(pollForAssistantResponse, 1000); // Poll every second
          } else {
            // Timeout - stop loading and update messages anyway
            setIsWaitingForResponse(false);
            await loadHistory();
          }
        };
        
        // Start polling after a brief delay
        setTimeout(pollForAssistantResponse, 1000);
      }
    },
    [loadHistory, settings.apiKey, settings.model],
  );

  const clearError = useCallback(() => setError(null), []);

  return (
    <main className="chat-bg min-h-screen p-4 sm:p-6">
      <div className="chat-wrap flex flex-col">
        <header className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-600 font-semibold text-white">
              OP
            </div>
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
                try {
                  const res = await fetch('/api/chat/history', { method: 'DELETE' });
                  if (!res.ok) {
                    console.error('Failed to clear chat history', res.statusText);
                    return;
                  }
                  setMessages([]);
                } catch (err) {
                  console.error('Failed to clear chat history', err);
                }
              }}
            >
              Clear
            </button>
          </div>
        </header>

        <div className="card flex-1 overflow-hidden">
          <div className="flex h-[70vh] flex-col gap-2 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="mx-auto my-12 max-w-sm text-center text-gray-500">
                <h2 className="mb-2 text-xl font-semibold text-gray-700">Start a conversation</h2>
                <p className="text-sm">
                  Your messages will appear here. Configure your OpenRouter key and model in Settings.
                </p>
              </div>
            )}
            {messages.map((message, index) => {
              const isUser = message.role === 'user';
              const isDraft = message.role === 'draft';
              const next = messages[index + 1];
              const tail = !next || next.role !== message.role;

              return (
                <div key={message.id} className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
                  <div
                    className={clsx(
                      isUser ? 'bubble-out' : 'bubble-in',
                      tail ? (isUser ? 'bubble-tail-out' : 'bubble-tail-in') : '',
                      isDraft && 'whitespace-pre-wrap',
                    )}
                  >
                    <span className={isDraft ? 'block whitespace-pre-wrap' : undefined}>{message.text}</span>
                  </div>
                </div>
              );
            })}
            {isWaitingForResponse && (
              <div className="flex justify-start">
                <div className="bubble-in bubble-tail-in">
                  <div className="flex items-center space-x-1">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-gray-200 p-3">
            {error && (
              <div className="mb-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                <div className="flex items-center justify-between">
                  <span>Something went wrong.</span>
                  <button className="underline" onClick={clearError}>
                    Dismiss
                  </button>
                </div>
                <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-xs text-red-600">{error}</pre>
              </div>
            )}

            <form
              className="flex items-center gap-2"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!canSubmit) return;
                const value = input;
                setInput('');
                try {
                  await sendMessage(value);
                } catch {
                  setInput(value);
                }
              }}
            >
              <input
                className="input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={settings.apiKey ? 'iMessage…' : 'Add your OpenRouter API key in Settings to start'}
              />
              <button type="submit" className="btn" disabled={!canSubmit}>
                Send
              </button>
            </form>

            <div className="mt-2 flex items-center justify-end text-xs text-gray-500">
              <span className="chip">Model: {settings.model || 'openrouter/auto'}</span>
            </div>
          </div>
        </div>

        <SettingsModal
          open={open}
          onClose={() => setOpen(false)}
          settings={settings}
          onSave={(next) => setSettings(next)}
        />
      </div>
    </main>
  );
}

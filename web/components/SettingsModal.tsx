"use client";
import { useEffect, useRef, useState } from 'react';

export type Settings = {
  apiKey: string;
  model: string;
};

export function useSettings() {
  const [settings, setSettings] = useState<Settings>({ apiKey: '', model: 'openrouter/auto' });
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  useEffect(() => {
    try {
      const apiKey = localStorage.getItem('openrouter_api_key') || '';
      const model = localStorage.getItem('openrouter_model') || 'openrouter/auto';
      setSettings({ apiKey, model });
    } catch {}
  }, []);

  const persist = (s: Settings) => {
    setSettings(s);
    try {
      localStorage.setItem('openrouter_api_key', s.apiKey);
      localStorage.setItem('openrouter_model', s.model);
    } catch {}
  };

  return { settings, setSettings: persist, settingsRef } as const;
}

export default function SettingsModal({
  open,
  onClose,
  settings,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  settings: Settings;
  onSave: (s: Settings) => void;
}) {
  const [apiKey, setApiKey] = useState(settings.apiKey);
  const [model, setModel] = useState(settings.model);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [gmailStatus, setGmailStatus] = useState<string>("");
  const [gmailConnected, setGmailConnected] = useState<boolean>(false);
  const [gmailEmail, setGmailEmail] = useState<string>("");
  const [gmailConnId, setGmailConnId] = useState<string>("");

  useEffect(() => {
    try {
      const savedConnected = localStorage.getItem('gmail_connected') === 'true';
      const savedConnId = localStorage.getItem('gmail_connection_request_id') || '';
      const savedEmail = localStorage.getItem('gmail_email') || '';
      setGmailConnected(savedConnected);
      setGmailConnId(savedConnId);
      setGmailEmail(savedEmail);
    } catch {}
  }, []);

  async function handleConnectGmail() {
    try {
      setConnectingGmail(true);
      setGmailStatus("");
      // stable-ish client-side user id; not sensitive
      const key = 'openpoke_user_id';
      let userId = '';
      try {
        userId = localStorage.getItem(key) || '';
        if (!userId) {
          userId = 'web-' + Math.random().toString(36).slice(2);
          localStorage.setItem(key, userId);
        }
      } catch {}
      const resp = await fetch('/api/integrations/composio/gmail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      });
      const data = await resp.json();
      if (!resp.ok || !data?.ok) {
        const msg = data?.error || `Failed (${resp.status})`;
        setGmailStatus(msg);
        return;
      }
      const url = data?.redirect_url;
      const connId = data?.connection_request_id || '';
      if (connId) {
        try {
          localStorage.setItem('gmail_connection_request_id', connId);
        } catch {}
        setGmailConnId(connId);
      }
      if (url) {
        window.open(url, '_blank', 'noopener');
        setGmailStatus('Opened Gmail connect in a new tab.');
      } else {
        setGmailStatus('No redirect URL returned.');
      }
    } catch (e: any) {
      setGmailStatus(e?.message || 'Failed to connect Gmail');
    } finally {
      setConnectingGmail(false);
    }
  }

  async function handleVerifyGmail() {
    try {
      setGmailStatus('Checking connection…');
      const key = 'openpoke_user_id';
      let userId = '';
      try { userId = localStorage.getItem(key) || ''; } catch {}
      const connectionRequestId = gmailConnId || (typeof window !== 'undefined' ? localStorage.getItem('gmail_connection_request_id') || '' : '');
      const resp = await fetch('/api/integrations/composio/gmail/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, connectionRequestId }),
      });
      const data = await resp.json();
      if (data?.ok && data?.connected) {
        setGmailConnected(true);
        const email = (data?.email as string) || '';
        setGmailEmail(email);
        setGmailStatus(email ? `Connected as ${email}` : 'Gmail connected');
        try {
          localStorage.setItem('gmail_connected', 'true');
          if (email) localStorage.setItem('gmail_email', email);
        } catch {}
      } else {
        setGmailConnected(false);
        setGmailStatus(data?.status ? `Status: ${data.status}` : 'Not connected yet');
      }
    } catch (e: any) {
      setGmailStatus(e?.message || 'Failed to check status');
    }
  }

  useEffect(() => {
    setApiKey(settings.apiKey);
    setModel(settings.model);
  }, [settings]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="card w-full max-w-lg p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button onClick={onClose} className="rounded-md p-2 hover:bg-gray-100" aria-label="Close settings">
            ✕
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">OpenRouter API Key</label>
            <input
              className="input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-or-v1-..."
            />
            <p className="mt-1 text-xs text-gray-500">Stored locally in your browser.</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Model</label>
            <input
              className="input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. openrouter/auto or anthropic/claude-3.5-sonnet"
            />
          </div>
          <div className="pt-2">
            <div className="mb-1 text-sm font-medium text-gray-700">Integrations</div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <div className="font-medium">Gmail (via Composio)</div>
                <div className="text-xs text-gray-500">Connect your Gmail account to enable email tools.</div>
                <div className="mt-1 flex items-center gap-2">
                  {gmailConnected ? (
                    <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                      {gmailEmail ? `Connected · ${gmailEmail}` : 'Connected'}
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">Not connected</span>
                  )}
                  {gmailStatus && (
                    <span className="text-[11px] text-gray-600">{gmailStatus}</span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn"
                  onClick={handleConnectGmail}
                  disabled={connectingGmail}
                  aria-busy={connectingGmail}
                >
                  {connectingGmail ? 'Connecting…' : (gmailConnected ? 'Reconnect' : 'Connect Gmail')}
                </button>
                <button className="rounded-md px-3 py-2 text-sm hover:bg-gray-100" onClick={handleVerifyGmail}>Verify</button>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Cancel</button>
          <button
            className="btn"
            onClick={() => {
              onSave({ apiKey, model });
              onClose();
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

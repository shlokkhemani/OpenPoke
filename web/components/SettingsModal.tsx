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


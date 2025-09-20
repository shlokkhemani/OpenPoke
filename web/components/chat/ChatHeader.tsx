interface ChatHeaderProps {
  onOpenSettings: () => void;
  onClearHistory: () => void;
}

export function ChatHeader({ onOpenSettings, onClearHistory }: ChatHeaderProps) {
  return (
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
          onClick={onOpenSettings}
        >
          Settings
        </button>
        <button
          className="rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50"
          onClick={onClearHistory}
        >
          Clear
        </button>
      </div>
    </header>
  );
}


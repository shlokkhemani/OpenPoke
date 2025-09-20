interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="mb-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
      <div className="flex items-center justify-between">
        <span>Something went wrong.</span>
        <button className="underline" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
      <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-xs text-red-600">{message}</pre>
    </div>
  );
}


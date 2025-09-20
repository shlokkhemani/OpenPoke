import { FormEvent } from 'react';

interface ChatInputProps {
  value: string;
  canSubmit: boolean;
  placeholder: string;
  onChange: (value: string) => void;
  onSubmit: () => Promise<void> | void;
}

export function ChatInput({ value, canSubmit, placeholder, onChange, onSubmit }: ChatInputProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    void onSubmit();
  };

  return (
    <form className="flex items-center gap-2" onSubmit={handleSubmit}>
      <input className="input" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
      <button type="submit" className="btn" disabled={!canSubmit}>
        Send
      </button>
    </form>
  );
}


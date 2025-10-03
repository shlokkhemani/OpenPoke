import clsx from 'clsx';
import { RefObject, useEffect, useState } from 'react';

import type { ChatBubble } from './types';

interface ChatMessagesProps {
  messages: ReadonlyArray<ChatBubble>;
  isWaitingForResponse: boolean;
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  showNotificationIndicator?: boolean;
  onNotificationIndicatorReset?: () => void;
}

export function ChatMessages({ messages, isWaitingForResponse, scrollContainerRef, onScroll, showNotificationIndicator, onNotificationIndicatorReset }: ChatMessagesProps) {
  const [notificationVisible, setNotificationVisible] = useState(false);

  // Show notification indicator briefly when showNotificationIndicator becomes true
  useEffect(() => {
    if (showNotificationIndicator) {
      setNotificationVisible(true);
      const timer = setTimeout(() => {
        setNotificationVisible(false);
        onNotificationIndicatorReset?.();
      }, 2000); // Show for 2 seconds
      return () => clearTimeout(timer);
    }
  }, [showNotificationIndicator, onNotificationIndicatorReset]);

  return (
    <div ref={scrollContainerRef} onScroll={onScroll} className="flex h-[70vh] flex-col gap-2 overflow-y-auto p-4 relative">
      {notificationVisible && <NotificationIndicator />}
      {messages.length === 0 && <EmptyState />}

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
              <span className={isDraft ? 'block whitespace-pre-wrap' : 'whitespace-pre-wrap'}>{message.text}</span>
            </div>
          </div>
        );
      })}

      {isWaitingForResponse && <TypingIndicator />}
    </div>
  );
}

function NotificationIndicator() {
  return (
    <div className="absolute top-4 right-4 z-10 animate-pulse">
      <div className="flex items-center space-x-2 rounded-full bg-brand-600 px-3 py-2 text-white shadow-lg">
        <div className="h-2 w-2 rounded-full bg-white animate-ping"></div>
        <span className="text-xs font-medium">New message</span>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bubble-in bubble-tail-in">
        <div className="flex items-center space-x-1">
          <div className="flex space-x-1">
            <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]"></div>
            <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]"></div>
            <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto my-12 max-w-sm text-center text-gray-500">
      <h2 className="mb-2 text-xl font-semibold text-gray-700">Start a conversation</h2>
      <p className="text-sm">
        Your messages will appear here. Send something to get started.
      </p>
    </div>
  );
}

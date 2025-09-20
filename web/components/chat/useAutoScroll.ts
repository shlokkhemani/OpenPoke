import { useCallback, useEffect, useRef } from 'react';

interface AutoScrollOptions {
  items: ReadonlyArray<unknown>;
  isWaiting: boolean;
}

export const useAutoScroll = ({ items, isWaiting }: AutoScrollOptions) => {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const isUserNearBottomRef = useRef(true);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const threshold = 80;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    isUserNearBottomRef.current = distanceFromBottom <= threshold;
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = scrollContainerRef.current;
    if (!container) return;

    container.scrollTo({ top: container.scrollHeight, behavior });
  }, []);

  useEffect(() => {
    if (isUserNearBottomRef.current) {
      const behavior = items.length === 0 ? 'auto' : 'smooth';
      scrollToBottom(behavior);
    }
  }, [items, isWaiting, scrollToBottom]);

  return {
    scrollContainerRef,
    handleScroll,
    scrollToBottom,
  };
};


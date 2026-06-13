"use client";

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

const LOADING_MESSAGES = [
  'Searching PubMed...',
  'Ranking Papers...',
  'Searching Abstracts...',
  'Generating Answer...',
  'Analyzing References...',
];

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message }: LoadingStateProps) {
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);

  useEffect(() => {
    if (message) return;

    const interval = setInterval(() => {
      setCurrentMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 2000);

    return () => clearInterval(interval);
  }, [message]);

  const displayMessage = message || LOADING_MESSAGES[currentMessageIndex];

  return (
    <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
      <Loader2 className="h-5 w-5 animate-spin text-primary" />
      <span className="text-sm text-muted-foreground">{displayMessage}</span>
    </div>
  );
}

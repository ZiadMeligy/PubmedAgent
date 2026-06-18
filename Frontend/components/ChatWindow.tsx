"use client";

import { useRef, useEffect, useState } from 'react';
import { Message } from '@/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { LoadingState } from './LoadingState';
import { Stethoscope, RefreshCw, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  loadingMessage?: string;
  error?: string | null;
  onSendMessage: (message: string) => void;
  onRetry?: () => void;
}

export function ChatWindow({
  messages,
  isLoading,
  loadingMessage,
  error,
  onSendMessage,
  onRetry,
}: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries.filter((entry) => entry.isIntersecting);
        if (visibleEntries.length > 0) {
          const topEntry = visibleEntries.reduce((prev, curr) => 
            prev.boundingClientRect.top < curr.boundingClientRect.top ? prev : curr
          );
          setActiveMessageId(topEntry.target.id);
        }
      },
      { rootMargin: '-10% 0px -50% 0px', threshold: 0.1 }
    );

    const elements = document.querySelectorAll('.ai-message');
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [messages]);

  const aiMessages = messages.filter(m => m.type === 'ai');

  const scrollToMessage = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading && !error) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <div className="h-20 w-20 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
              <Stethoscope className="h-10 w-10 text-primary" />
            </div>
            <h2 className="text-2xl font-semibold mb-2">Biomedical Literature Assistant</h2>
            <p className="text-muted-foreground mb-4">
              Search PubMed papers and ask questions about biomedical literature.
            </p>
            <div className="text-sm text-muted-foreground space-y-2">
              <p className="font-medium">Try asking:</p>
              <div className="space-y-1">
                <p className="p-2 bg-muted rounded-lg cursor-pointer hover:bg-muted/80 transition-colors"
                   onClick={() => onSendMessage('Find papers about diabetic kidney disease')}>
                  "Find papers about diabetic kidney disease"
                </p>
                <p className="p-2 bg-muted rounded-lg cursor-pointer hover:bg-muted/80 transition-colors"
                   onClick={() => onSendMessage('What therapies reduced albuminuria?')}>
                  "What therapies reduced albuminuria?"
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="max-w-[900px] mx-auto w-full px-8 pb-4">
          <ChatInput onSend={onSendMessage} disabled={isLoading} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1">
        <div className="flex h-full">
          <div className="flex-1 relative">
            <div className="max-w-[900px] mx-auto w-full px-8 py-4 space-y-1">
              {messages.map((message) => (
                <div key={message.id} id={`msg-${message.id}`} className={message.type === 'ai' ? 'ai-message' : ''}>
                  <MessageBubble message={message} />
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start mb-4">
                  <LoadingState message={loadingMessage} />
                </div>
              )}
              {error && (
                <div className="flex justify-center mb-4">
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20 max-w-md">
                    <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-destructive">{error}</p>
                      {onRetry && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 h-auto p-0 text-destructive hover:bg-transparent"
                          onClick={onRetry}
                        >
                          <RefreshCw className="h-3 w-3 mr-1" />
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          </div>
          
          {/* Right Chat Navigator */}
          {aiMessages.length > 0 && (
            <div className="hidden md:flex flex-col items-center justify-center w-12 sticky top-0 h-full border-l bg-background/50 backdrop-blur">
              <div className="space-y-4 py-8 max-h-[80vh] overflow-y-auto">
                {aiMessages.map((msg) => (
                  <div 
                    key={msg.id}
                    onClick={() => scrollToMessage(`msg-${msg.id}`)}
                    className={`w-3 h-3 rounded-full cursor-pointer transition-colors ${activeMessageId === `msg-${msg.id}` ? 'bg-primary scale-125' : 'bg-muted-foreground/30 hover:bg-muted-foreground/60'}`}
                    title="Jump to response"
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
      <div className="max-w-[900px] mx-auto w-full px-8">
        <ChatInput onSend={onSendMessage} disabled={isLoading} />
      </div>
    </div>
  );
}

"use client";

import { Message } from '@/types';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PaperCard } from './PaperCard';
import { ReferencesPanel } from './ReferencesPanel';
import { RetrievalConfigCard } from './RetrievalConfigCard';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.type === 'user';

  return (
    <div
      className={cn(
        'flex w-full mb-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={cn(
          'max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-md'
            : 'bg-muted rounded-bl-md'
        )}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="space-y-3">
            {message.retrievalConfig && (
              <RetrievalConfigCard 
                params={[
                  { key: 'similarity', label: 'Semantic Similarity', value: message.retrievalConfig.similarity, colorClass: 'bg-blue-500' },
                  { key: 'recency', label: 'Recency', value: message.retrievalConfig.recency, colorClass: 'bg-green-500' },
                  { key: 'citation', label: 'Citation Count', value: message.retrievalConfig.citation, colorClass: 'bg-amber-500' }
                ]}
                journalQualityEnabled={message.retrievalConfig.journal_quality_enabled}
                minimumSjr={message.retrievalConfig.minimum_sjr}
              />
            )}
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node, ...props }) => {
                    const childrenText = String(props.children);
                    // Check if it's a citation like "1" (from [1](url)) or "[1]"
                    if (/^\[?\d+\]?$/.test(childrenText)) {
                      const num = childrenText.replace('[', '').replace(']', '');
                      return (
                        <a 
                          {...props} 
                          className="inline-flex items-center justify-center w-4 h-4 ml-1 text-[10px] font-bold text-white bg-primary rounded-[4px] no-underline hover:opacity-70 transition-opacity align-super"
                          target="_blank"
                          rel="noopener noreferrer"
                          title={props.href}
                        >
                          {num}
                        </a>
                      );
                    }
                    // Default link styling
                    return (
                      <a 
                        {...props} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-primary hover:underline font-medium" 
                      />
                    );
                  }
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
            {message.papers && message.papers.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-3 mt-4 not-prose">
                {message.papers.slice(0, 5).map((paper) => (
                  <PaperCard key={paper.rank} paper={paper} />
                ))}
              </div>
            )}
            {message.references && message.references.length > 0 && (
              <ReferencesPanel references={message.references} />
            )}
          </div>
        )}
        <p
          className={cn(
            'text-xs mt-2',
            isUser ? 'text-primary-foreground/70' : 'text-muted-foreground'
          )}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}

"use client";

import { Message } from '@/types';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink } from 'lucide-react';
import { PaperCard } from './PaperCard';
import { ReferencesPanel } from './ReferencesPanel';
import { RetrievalConfigCard } from './RetrievalConfigCard';
import { Button } from './ui/button';
import { Loader2, Database } from 'lucide-react';
import { checkFullText } from '@/lib/api';
import { useConversationStore } from '@/lib/store';
import { useState } from 'react';

interface MessageBubbleProps {
  message: Message;
  conversationId?: string;
}

export function MessageBubble({ message, conversationId }: MessageBubbleProps) {
  const isUser = message.type === 'user';
  const { updateMessage, currentConversationId } = useConversationStore();
  const [isChecking, setIsChecking] = useState(false);
  const [isAddingAll, setIsAddingAll] = useState(false);
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleAddAllToDB = () => {
    const targetConvId = conversationId || currentConversationId;
    if (!targetConvId || !message.papers || message.papers.length === 0) return;

    setIsAddingAll(true);
    
    // Find all papers that are AVAILABLE and not already INDEXING or INDEXED
    const eligiblePapers = message.papers.filter(p => 
      p.fullTextStatus === 'AVAILABLE' && 
      (!p.indexStatus || p.indexStatus === 'NONE' || p.indexStatus === 'ERROR')
    );
    
    if (eligiblePapers.length === 0) {
      setIsAddingAll(false);
      return;
    }

    eligiblePapers.forEach(paper => {
      // Start indexing state
      updateMessage(targetConvId, message.id, (msg) => ({
        ...msg,
        papers: msg.papers?.map(p => 
          p.pubmed_id === paper.pubmed_id 
            ? { ...p, indexStatus: 'INDEXING', indexMessage: 'Connecting...' } 
            : p
        )
      }));

      const url = new URL(`${API_BASE_URL}/api/fulltext/index/stream`);
      url.searchParams.append('pmid', paper.pubmed_id);
      if (paper.doi) url.searchParams.append('doi', paper.doi);
      if (paper.title) url.searchParams.append('title', paper.title);
      if (paper.journal) url.searchParams.append('journal', paper.journal);
      if (paper.publication_year) url.searchParams.append('year', paper.publication_year.toString());

      const source = new EventSource(url.toString());

      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.status === 'ERROR') {
            source.close();
            updateMessage(targetConvId, message.id, (msg) => ({
              ...msg,
              papers: msg.papers?.map(p => 
                p.pubmed_id === paper.pubmed_id 
                  ? { ...p, indexStatus: 'ERROR', indexMessage: data.message } 
                  : p
              )
            }));
          } else if (data.status === 'INDEXED' || data.status === 'ALREADY_INDEXED') {
            source.close();
            updateMessage(targetConvId, message.id, (msg) => ({
              ...msg,
              papers: msg.papers?.map(p => 
                p.pubmed_id === paper.pubmed_id 
                  ? { ...p, indexStatus: data.status, indexMessage: data.message } 
                  : p
              )
            }));
          } else {
            updateMessage(targetConvId, message.id, (msg) => ({
              ...msg,
              papers: msg.papers?.map(p => 
                p.pubmed_id === paper.pubmed_id 
                  ? { ...p, indexStatus: 'INDEXING', indexMessage: data.message } 
                  : p
              )
            }));
          }
        } catch (err) {
          console.error('Failed to parse SSE message', err);
        }
      };

      source.onerror = (err) => {
        console.error('EventSource failed', err);
        source.close();
        updateMessage(targetConvId, message.id, (msg) => ({
          ...msg,
          papers: msg.papers?.map(p => 
            p.pubmed_id === paper.pubmed_id 
              ? { ...p, indexStatus: 'ERROR', indexMessage: 'Connection lost' } 
              : p
          )
        }));
      };
    });
    
    // We can reset the spinner since the individual papers show their own progress
    setTimeout(() => setIsAddingAll(false), 1000);
  };

  const handleCheckFullText = async () => {
    const targetConvId = conversationId || currentConversationId;
    if (!targetConvId || !message.papers || message.papers.length === 0) return;

    setIsChecking(true);
    
    // Mark all papers as checking initially
    updateMessage(targetConvId, message.id, (msg) => ({
      ...msg,
      papers: msg.papers?.map(p => ({ ...p, fullTextStatus: 'CHECKING' }))
    }));

    try {
      const response = await checkFullText(message.papers);
      
      updateMessage(targetConvId, message.id, (msg) => {
        const newPapers = msg.papers?.map(p => {
          const res = response.papers?.find((r: any) => r.pmid === p.pubmed_id);
          if (res) {
            return {
              ...p,
              fullTextStatus: res.available ? 'AVAILABLE' : 'NOT_AVAILABLE',
              pdfUrl: res.pdf_url
            };
          }
          return { ...p, fullTextStatus: 'NOT_AVAILABLE' };
        });
        return { ...msg, papers: newPapers as any };
      });
    } catch (error) {
      console.error('Failed to check full text:', error);
      // Reset status on error so they can try again, or mark as not available
      updateMessage(targetConvId, message.id, (msg) => ({
        ...msg,
        papers: msg.papers?.map(p => ({ ...p, fullTextStatus: 'NOT_AVAILABLE' }))
      }));
    } finally {
      setIsChecking(false);
    }
  };

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
                    // Extract text safely from children
                    let childrenText = "";
                    if (Array.isArray(props.children)) {
                      childrenText = props.children.map(c => typeof c === 'string' ? c : '').join('');
                    } else if (typeof props.children === 'string' || typeof props.children === 'number') {
                      childrenText = String(props.children);
                    }
                    
                    // Check if it's a citation like "1" (from [1](url)) or "[1]"
                    if (childrenText && /^\[?\s*\d+\s*\]?$/.test(childrenText.trim())) {
                      const num = childrenText.replace(/\[|\]/g, '').trim();
                      return (
                        <a 
                          {...props} 
                          className="inline-flex items-center justify-center ml-1 text-primary hover:text-primary/80 no-underline transition-colors align-baseline"
                          target="_blank"
                          rel="noopener noreferrer"
                          title={props.href || `Reference ${num}`}
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      );
                    }
                    // Default link styling
                    return (
                      <a 
                        {...props} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-primary hover:underline font-medium break-words" 
                      />
                    );
                  }
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
            {message.papers && message.papers.length > 0 && (
              <div className="mt-4 not-prose">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-3 mb-3">
                  {message.papers.slice(0, 5).map((paper) => (
                    <PaperCard 
                      key={paper.rank} 
                      paper={paper} 
                      conversationId={conversationId || currentConversationId}
                      messageId={message.id}
                    />
                  ))}
                </div>
                
                {/* Full Text Action Buttons */}
                {message.type === 'assistant' && (
                  <div className="flex justify-start mt-2 gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={handleCheckFullText}
                      disabled={isChecking || message.papers.every(p => p.fullTextStatus === 'AVAILABLE' || p.fullTextStatus === 'NOT_AVAILABLE')}
                      className="text-xs"
                    >
                      {isChecking && <Loader2 className="w-3 h-3 mr-2 animate-spin" />}
                      Check Full Text Availability
                    </Button>
                    
                    {/* Render Add All to DB button only if check is fully done and at least 1 paper is available */}
                    {message.papers.every(p => p.fullTextStatus !== 'CHECKING') && 
                     message.papers.some(p => p.fullTextStatus) && 
                     message.papers.some(p => p.fullTextStatus === 'AVAILABLE') && (
                      <Button 
                        variant="default" 
                        size="sm" 
                        onClick={handleAddAllToDB}
                        disabled={isAddingAll || message.papers.every(p => 
                          p.fullTextStatus !== 'AVAILABLE' || 
                          p.indexStatus === 'INDEXED' || 
                          p.indexStatus === 'ALREADY_INDEXED' || 
                          p.indexStatus === 'INDEXING'
                        )}
                        className="text-xs bg-primary text-primary-foreground hover:bg-primary/90"
                      >
                        {isAddingAll ? <Loader2 className="w-3 h-3 mr-2 animate-spin" /> : <Database className="w-3 h-3 mr-2" />}
                        Add All Available to DB
                      </Button>
                    )}
                  </div>
                )}
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

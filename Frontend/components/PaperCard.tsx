"use client";

import { Paper } from '@/types';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ExternalLink, Calendar, Quote, TrendingUp, BarChart3, FileText, Loader2, CheckCircle2, XCircle, Download, Database, RefreshCw } from 'lucide-react';
import { useConversationStore } from '@/lib/store';
import { useState, useRef, useEffect } from 'react';
import { PaperTools } from './PaperTools';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PaperCardProps {
  paper: Paper;
  conversationId?: string;
  messageId?: string;
}

export function PaperCard({ paper, conversationId, messageId }: PaperCardProps) {
  const { updateMessage } = useConversationStore();
  const eventSourceRef = useRef<EventSource | null>(null);
  const isIndexed = paper.indexStatus === 'INDEXED' || paper.indexStatus === 'ALREADY_INDEXED';

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleAddFullText = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!conversationId || !messageId) return;

    // Start indexing state
    updateMessage(conversationId, messageId, (msg) => ({
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
    eventSourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === 'ERROR') {
          source.close();
          updateMessage(conversationId, messageId, (msg) => ({
            ...msg,
            papers: msg.papers?.map(p => 
              p.pubmed_id === paper.pubmed_id 
                ? { ...p, indexStatus: 'ERROR', indexMessage: data.message } 
                : p
            )
          }));
        } else if (data.status === 'INDEXED' || data.status === 'ALREADY_INDEXED') {
          source.close();
          updateMessage(conversationId, messageId, (msg) => ({
            ...msg,
            papers: msg.papers?.map(p => 
              p.pubmed_id === paper.pubmed_id 
                ? { ...p, indexStatus: data.status, indexMessage: data.message } 
                : p
            )
          }));
        } else {
          // Progress update
          updateMessage(conversationId, messageId, (msg) => ({
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
      updateMessage(conversationId, messageId, (msg) => ({
        ...msg,
        papers: msg.papers?.map(p => 
          p.pubmed_id === paper.pubmed_id 
            ? { ...p, indexStatus: 'ERROR', indexMessage: 'Connection lost' } 
            : p
        )
      }));
    };
  };
  return (
    <Card className="flex flex-col h-full hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-2">
          <span className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
            {paper.rank}
          </span>
          <CardTitle className="text-base font-semibold leading-tight line-clamp-3">
            {paper.title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="flex-grow">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4 flex-shrink-0" />
            <span>Year: <span className="font-medium text-foreground">{paper.publication_year}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Quote className="h-4 w-4 flex-shrink-0" />
            <span>Citations: <span className="font-medium text-foreground">{paper.citation_count}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingUp className="h-4 w-4 flex-shrink-0" />
            <span>Similarity: <span className="font-medium text-foreground">{paper.similarity_score.toFixed(2)}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <BarChart3 className="h-4 w-4 flex-shrink-0" />
            <span>Score: <span className="font-medium text-foreground">{paper.composite_score.toFixed(2)}</span></span>
          </div>
        </div>
      </CardContent>
      <CardFooter className="pt-0 flex flex-col gap-2">
        {paper.fullTextStatus && (
          <div className="w-full text-xs font-medium bg-muted/50 rounded p-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {paper.fullTextStatus === 'CHECKING' && (
                <><Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" /> <span className="text-blue-500">Checking PDF...</span></>
              )}
              {paper.fullTextStatus === 'AVAILABLE' && (
                <><CheckCircle2 className="h-3.5 w-3.5 text-green-600" /> <span className="text-green-600">PDF Available</span></>
              )}
              {paper.fullTextStatus === 'NOT_AVAILABLE' && (
                <><XCircle className="h-3.5 w-3.5 text-red-500" /> <span className="text-red-500">PDF Not Available</span></>
              )}
            </div>
            {paper.fullTextStatus === 'AVAILABLE' && (
              <div className="flex items-center gap-1">
                <Button 
                  variant="default" 
                  size="sm" 
                  className="h-6 text-[10px] px-2 bg-green-600 hover:bg-green-700 text-white"
                  onClick={(e) => {
                    e.stopPropagation();
                    window.open(`${API_BASE_URL}/api/fulltext/download/${paper.pubmed_id}?doi=${paper.doi || ''}`, '_blank');
                  }}
                >
                  <Download className="h-3 w-3 mr-1" />
                  Download
                </Button>
                
                {(!paper.indexStatus || paper.indexStatus === 'NONE' || paper.indexStatus === 'ERROR') && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-6 text-[10px] px-2 border-primary/20 text-primary hover:bg-primary/5"
                    onClick={handleAddFullText}
                  >
                    <Database className="h-3 w-3 mr-1" />
                    Add to DB
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
        
        {paper.indexStatus && paper.indexStatus !== 'NONE' && (
          <div className="w-full text-xs bg-primary/5 border border-primary/10 rounded p-2 flex items-center justify-between mt-1">
            <div className="flex items-center gap-1.5 text-primary">
              {paper.indexStatus === 'INDEXING' && (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" /> <span>{paper.indexMessage || 'Indexing...'}</span></>
              )}
              {(paper.indexStatus === 'INDEXED' || paper.indexStatus === 'ALREADY_INDEXED') && (
                <><Database className="h-3.5 w-3.5" /> <span className="font-medium">{paper.indexMessage || 'Already Indexed'}</span></>
              )}
              {paper.indexStatus === 'ERROR' && (
                <><XCircle className="h-3.5 w-3.5 text-red-500" /> <span className="text-red-500">{paper.indexMessage || 'Error Indexing'}</span></>
              )}
            </div>
          </div>
        )}
        {isIndexed && conversationId && (
          <>
            <PaperTools paper={paper} conversationId={conversationId} />
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-full text-xs text-muted-foreground"
              onClick={handleAddFullText}
            >
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              Refresh paper index
            </Button>
          </>
        )}
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => window.open(paper.url, '_blank', 'noopener,noreferrer')}
        >
          <ExternalLink className="h-4 w-4 mr-2" />
          Open PubMed
        </Button>
      </CardFooter>
    </Card>
  );
}

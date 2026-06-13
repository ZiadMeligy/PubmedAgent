"use client";

import { useState, useCallback } from 'react';
import { sendMessage } from '@/lib/api';
import { useConversationStore } from '@/lib/store';
import { Message, APIResponse } from '@/types';

const generateId = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

const LOADING_MESSAGES_MAP: Record<string, string> = {
  paper_search: 'Searching PubMed...',
  qa: 'Generating Answer...',
  chat: 'Processing...',
};

export function useChat(conversationId: string | null) {
  const [error, setError] = useState<string | null>(null);
  const [backendConversationId, setBackendConversationId] = useState<string | null>(null);
  const { addMessage, setLoading, isLoading, loadingMessage } = useConversationStore();

  const handleSendMessage = useCallback(async (message: string) => {
    if (!message.trim() || isLoading) return;

    const currentConversationId = conversationId || backendConversationId;
    setError(null);

    const userMessage: Message = {
      id: generateId(),
      type: 'user',
      content: message,
      timestamp: new Date(),
    };

    if (conversationId) {
      addMessage(conversationId, userMessage);
    }

    setLoading(true, 'Sending message...');

    try {
      const response: APIResponse = await sendMessage(currentConversationId, message);

      if (response.type === 'error') {
        setError(response.message);
        return;
      }

      if (!backendConversationId && response.conversation_id) {
        setBackendConversationId(response.conversation_id);
      }

      let assistantContent = '';
      let papers = undefined;
      let references = undefined;

      switch (response.type) {
        case 'paper_search':
          assistantContent = response.papers_found
            ? `Found ${response.papers.length} relevant papers:`
            : 'No papers found matching your query.';
          papers = response.papers;
          setLoading(true, 'Ranking Papers...');
          break;
        case 'qa':
          assistantContent = response.response;
          references = response.references;
          setLoading(true, 'Analyzing References...');
          break;
        case 'chat':
          assistantContent = response.response;
          break;
      }

      const assistantMessage: Message = {
        id: generateId(),
        type: 'assistant',
        content: assistantContent,
        timestamp: new Date(),
        responseType: response.type,
        papers,
        references,
      };

      if (conversationId) {
        addMessage(conversationId, assistantMessage);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unable to contact backend.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [conversationId, backendConversationId, isLoading, addMessage, setLoading]);

  const retry = useCallback(() => {
    setError(null);
  }, []);

  return {
    sendMessage: handleSendMessage,
    isLoading,
    loadingMessage,
    error,
    retry,
    backendConversationId,
  };
}

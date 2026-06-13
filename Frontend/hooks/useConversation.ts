"use client";

import { useCallback, useMemo } from 'react';
import { useConversationStore } from '@/lib/store';

export function useConversation() {
  const {
    conversations,
    currentConversationId,
    createConversation,
    setCurrentConversation,
    deleteConversation,
    clearAllConversations,
  } = useConversationStore();

  const currentConversation = useMemo(() => {
    return conversations.find((c) => c.id === currentConversationId) || null;
  }, [conversations, currentConversationId]);

  const messages = useMemo(() => {
    return currentConversation?.messages || [];
  }, [currentConversation]);

  const sortedConversations = useMemo(() => {
    return [...conversations].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  }, [conversations]);

  const handleCreateConversation = useCallback(() => {
    const id = createConversation();
    return id;
  }, [createConversation]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setCurrentConversation(id);
    },
    [setCurrentConversation]
  );

  const handleDeleteConversation = useCallback(
    (id: string) => {
      deleteConversation(id);
    },
    [deleteConversation]
  );

  return {
    conversations: sortedConversations,
    currentConversation,
    currentConversationId,
    messages,
    createConversation: handleCreateConversation,
    selectConversation: handleSelectConversation,
    deleteConversation: handleDeleteConversation,
    clearAllConversations,
  };
}

"use client";

import { Conversation } from '@/types';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageSquare, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ConversationListProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ConversationList({
  conversations,
  currentConversationId,
  onSelect,
  onDelete,
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-3 opacity-30" />
        <p className="text-sm">No conversations yet</p>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="space-y-1 p-2">
        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className={cn(
              'group flex items-center gap-2 rounded-lg p-3 cursor-pointer transition-colors',
              currentConversationId === conversation.id
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-muted'
            )}
            onClick={() => onSelect(conversation.id)}
          >
            <MessageSquare className="h-4 w-4 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{conversation.title}</p>
              <p className="text-xs text-muted-foreground truncate">
                {conversation.messages.length} message{conversation.messages.length !== 1 ? 's' : ''}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conversation.id);
              }}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}

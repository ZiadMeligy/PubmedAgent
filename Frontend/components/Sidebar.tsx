"use client";

import { Conversation } from '@/types';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ConversationList } from './ConversationList';
import { Plus, Stethoscope, Settings, User } from 'lucide-react';
import Link from 'next/link';

interface SidebarProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
}

export function Sidebar({
  conversations,
  currentConversationId,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
}: SidebarProps) {
  return (
    <div className="flex flex-col h-full bg-card border-r">
      {/* Header */}
      <div className="p-4">
        <Link href="/" className="flex items-center gap-3 mb-4">
          <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
            <Stethoscope className="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">BioMed Assistant</h1>
            <p className="text-xs text-muted-foreground">Literature Search</p>
          </div>
        </Link>
        <Button onClick={onNewConversation} className="w-full" variant="default">
          <Plus className="h-4 w-4 mr-2" />
          New Conversation
        </Button>
      </div>

      <Separator />

      {/* Conversation List */}
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelect={onSelectConversation}
        onDelete={onDeleteConversation}
      />

      <Separator />

      {/* Footer with settings link */}
      <div className="p-4">
        <Link href="/settings">
          <Button variant="outline" size="sm" className="w-full">
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
        </Link>
      </div>
    </div>
  );
}

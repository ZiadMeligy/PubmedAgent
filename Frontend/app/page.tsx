"use client";

import { Sidebar } from '@/components/Sidebar';
import { ChatWindow } from '@/components/ChatWindow';
import { useConversation } from '@/hooks/useConversation';
import { useChat } from '@/hooks/useChat';
import { useConversationStore, useAuthStore } from '@/lib/store';
import { Menu, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  const {
    conversations,
    currentConversationId,
    messages,
    createConversation,
    selectConversation,
    deleteConversation,
  } = useConversation();

  const { isLoading, loadingMessage } = useConversationStore();
  const { sendMessage, error, retry } = useChat(currentConversationId);

  useEffect(() => {
    if (!token) {
      router.push('/login');
    }
  }, [token, router]);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth >= 768) {
        setSidebarOpen(true);
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (conversations.length === 0) {
      createConversation();
    }
  }, [conversations.length, createConversation]);

  const handleNewConversation = () => {
    createConversation();
    if (isMobile) {
      setSidebarOpen(false);
    }
  };

  const handleSelectConversation = (id: string) => {
    selectConversation(id);
    if (isMobile) {
      setSidebarOpen(false);
    }
  };

  if (!token) return null;

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed md:static inset-y-0 left-0 z-50 w-72 flex-shrink-0 transition-transform duration-300',
          isMobile && !sidebarOpen && '-translate-x-full md:translate-x-0'
        )}
      >
        <Sidebar
          conversations={conversations}
          currentConversationId={currentConversationId}
          onNewConversation={handleNewConversation}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={deleteConversation}
        />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        {isMobile && (
          <div className="flex items-center gap-2 p-4 border-b md:hidden">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </Button>
            <h1 className="text-lg font-semibold">BioMed Assistant</h1>
          </div>
        )}

        {/* Chat window */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            loadingMessage={loadingMessage}
            error={error}
            onSendMessage={sendMessage}
            onRetry={retry}
          />
        </div>
      </main>
    </div>
  );
}

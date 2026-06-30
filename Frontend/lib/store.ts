import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Conversation, Message } from '@/types';

interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;
  isLoading: boolean;
  loadingMessage: string;

  createConversation: () => string;
  setCurrentConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  addMessage: (conversationId: string, message: Message) => void;
  updateMessage: (conversationId: string, messageId: string, updater: (msg: Message) => Message) => void;
  updateConversationTitle: (id: string, title: string) => void;
  setLoading: (isLoading: boolean, message?: string) => void;
  clearAllConversations: () => void;
}

const generateId = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

export const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      isLoading: false,
      loadingMessage: '',

      createConversation: () => {
        const id = generateId();
        const newConversation: Conversation = {
          id,
          title: 'New Conversation',
          messages: [],
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        set((state) => ({
          conversations: [newConversation, ...state.conversations],
          currentConversationId: id,
        }));

        return id;
      },

      setCurrentConversation: (id: string) => {
        set({ currentConversationId: id });
      },

      deleteConversation: (id: string) => {
        set((state) => {
          const newConversations = state.conversations.filter((c) => c.id !== id);
          const newCurrentId = state.currentConversationId === id
            ? (newConversations[0]?.id || null)
            : state.currentConversationId;

          return {
            conversations: newConversations,
            currentConversationId: newCurrentId,
          };
        });
      },

      addMessage: (conversationId: string, message: Message) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id === conversationId) {
              const updatedMessages = [...c.messages, message];
              const title = c.messages.length === 0 && message.type === 'user'
                ? message.content.substring(0, 50) + (message.content.length > 50 ? '...' : '')
                : c.title;

              return {
                ...c,
                messages: updatedMessages,
                title,
                updatedAt: new Date(),
              };
            }
            return c;
          }),
        }));
      },

      updateMessage: (conversationId: string, messageId: string, updater: (msg: Message) => Message) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id === conversationId) {
              return {
                ...c,
                messages: c.messages.map((m) => (m.id === messageId ? updater(m) : m)),
              };
            }
            return c;
          }),
        }));
      },

      updateConversationTitle: (id: string, title: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title } : c
          ),
        }));
      },

      setLoading: (isLoading: boolean, message: string = '') => {
        set({ isLoading, loadingMessage: message });
      },

      clearAllConversations: () => {
        set({ conversations: [], currentConversationId: null });
      },
    }),
    {
      name: 'biomedical-chat-conversations',
      partialize: (state) => ({
        conversations: state.conversations,
        currentConversationId: state.currentConversationId,
      }),
    }
  )
);

export interface UserProfile {
  id: string;
  email: string;
  username: string;
}

export interface AuthState {
  token: string | null;
  user: UserProfile | null;
  setToken: (token: string | null) => void;
  setUser: (user: UserProfile | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    {
      name: 'auth-storage',
    }
  )
);

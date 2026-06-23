import { Paper, Reference } from './paper';
import { RetrievalConfig } from './api';

export type MessageType = 'user' | 'assistant';

export type ResponseType = 'paper_search' | 'qa' | 'chat' | 'error';

export interface Message {
  id: string;
  type: MessageType;
  content: string;
  timestamp: Date;
  responseType?: ResponseType;
  papers?: Paper[];
  references?: Reference[];
  retrievalConfig?: RetrievalConfig;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

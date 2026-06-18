import { ChatRequest, APIResponse } from '@/types';
import { useAuthStore } from './store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class APIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'APIError';
  }
}

export async function sendMessage(
  conversationId: string | null,
  message: string
): Promise<APIResponse> {
  const request: ChatRequest = {
    conversation_id: conversationId,
    message,
  };

  const token = useAuthStore.getState().token;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (response.status === 401) {
    useAuthStore.getState().logout();
    throw new APIError('Unauthorized. Please log in again.');
  }

  if (!response.ok) {
    throw new APIError(`Failed to send message: ${response.status} ${response.statusText}`);
  }

  const data: APIResponse = await response.json();
  return data;
}

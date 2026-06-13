import { ChatRequest, APIResponse } from '@/types';

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

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new APIError(`Failed to send message: ${response.status} ${response.statusText}`);
  }

  const data: APIResponse = await response.json();
  return data;
}

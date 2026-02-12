import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { ChatRequest, ChatResponse } from '../models/chat.model';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly chatEndpoint = `${environment.apiUrl}chat/`;

  sendMessage(question: string, history: string[]): Observable<ChatResponse> {
    const body: ChatRequest = {
      user_question: question,
      conversation_history: { messages: history },
    };
    return this.http.post<ChatResponse>(this.chatEndpoint, body);
  }
}

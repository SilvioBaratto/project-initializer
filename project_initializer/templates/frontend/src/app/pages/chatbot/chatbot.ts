import {
  Component,
  signal,
  inject,
  viewChild,
  ElementRef,
  DestroyRef,
  ChangeDetectionStrategy,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ChatService } from '../../services/chat.service';
import { ChatMessage } from '../../models/chat.model';

@Component({
  selector: 'app-chatbot',
  templateUrl: './chatbot.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { style: 'flex:1; display:flex; flex-direction:column; min-height:0' },
})
export class ChatbotComponent {
  private readonly chatService = inject(ChatService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly scrollContainer = viewChild<ElementRef<HTMLElement>>('scrollContainer');
  private readonly inputEl = viewChild<ElementRef<HTMLTextAreaElement>>('inputEl');

  messages = signal<ChatMessage[]>([]);
  isLoading = signal(false);
  userInput = signal('');

  onInputChange(event: Event) {
    const textarea = event.target as HTMLTextAreaElement;
    this.userInput.set(textarea.value);

    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  }

  onKeydown(event: Event) {
    const keyEvent = event as KeyboardEvent;
    if (!keyEvent.shiftKey) {
      event.preventDefault();
      this.onSend();
    }
  }

  onSend() {
    const question = this.userInput().trim();
    if (!question || this.isLoading()) return;

    this.messages.update((msgs) => [
      ...msgs,
      { id: crypto.randomUUID(), role: 'user', content: question },
    ]);
    this.userInput.set('');
    this.isLoading.set(true);
    this.scrollToBottom();

    const textarea = this.inputEl()?.nativeElement;
    if (textarea) textarea.style.height = 'auto';

    const history = this.messages().map((m) => `${m.role}: ${m.content}`);

    this.chatService
      .sendMessage(question, history)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.messages.update((msgs) => [
            ...msgs,
            { id: crypto.randomUUID(), role: 'assistant', content: response.answer },
          ]);
          this.isLoading.set(false);
          this.scrollToBottom();
        },
        error: () => {
          this.messages.update((msgs) => [
            ...msgs,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: 'Something went wrong. Please try again.',
              isError: true,
            },
          ]);
          this.isLoading.set(false);
          this.scrollToBottom();
        },
      });
  }

  private scrollToBottom() {
    setTimeout(() => {
      const el = this.scrollContainer()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, 0);
  }
}

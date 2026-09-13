import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { LucideAngularModule } from 'lucide-angular';
import { ChatService } from '../../services/chat';
import { ChatMessage } from '../../models/chat';

/** Shown in place of an answer when the request fails: what happened and how to recover. */
const ERROR_MESSAGE = "Couldn't get a response. Send your message again.";

/**
 * Chat view. A message log that scrolls on its own above an outlined Material
 * composer; the composer stays at the bottom of the view, so it sits directly
 * above the shell's compact navigation bar (which the shell renders outside main).
 */
@Component({
  selector: 'app-chatbot',
  templateUrl: './chatbot.html',
  styleUrl: './chatbot.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatFormFieldModule, MatInputModule, LucideAngularModule],
})
export class ChatbotComponent {
  private readonly chatService = inject(ChatService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly scrollContainer = viewChild<ElementRef<HTMLElement>>('scrollContainer');
  private readonly autosize = viewChild(CdkTextareaAutosize);
  private readonly inputEl = viewChild.required<ElementRef<HTMLTextAreaElement>>('inputEl');

  /**
   * Source of message ids, which only need to be unique within this view for `@for` tracking.
   * A counter, not `crypto.randomUUID()`: that exists only in secure contexts, so on a plain-HTTP
   * origin other than localhost (a dev server opened from a phone by LAN IP) sending would throw.
   */
  private nextMessageId = 0;

  messages = signal<ChatMessage[]>([]);
  isLoading = signal(false);
  userInput = signal('');

  onInputChange(event: Event) {
    // Height follows the content through cdkTextareaAutosize (1–7 rows).
    this.userInput.set((event.target as HTMLTextAreaElement).value);
  }

  onKeydown(event: Event) {
    const keyEvent = event as KeyboardEvent;
    // Shift+Enter inserts a newline; Enter that confirms an IME composition is not a send.
    if (keyEvent.shiftKey || keyEvent.isComposing) return;
    event.preventDefault();
    this.onSend();
  }

  onSend() {
    const question = this.userInput().trim();
    if (!question || this.isLoading()) return;

    this.messages.update((msgs) => [
      ...msgs,
      { id: this.newMessageId(), role: 'user', content: question },
    ]);
    this.userInput.set('');
    this.isLoading.set(true);
    // Send turns disabled on the next render, and a focused button that becomes disabled drops
    // keyboard focus to <body>. Hand focus to the composer first (a no-op when Enter was pressed there).
    this.inputEl().nativeElement.focus();
    // Shrink the composer back to one row once the cleared value has rendered.
    afterNextRender(() => this.autosize()?.resizeToFitContent(true), { injector: this.injector });
    this.scrollToBottom();

    const history = this.messages().map((m) => `${m.role}: ${m.content}`);

    this.chatService
      .sendMessage(question, history)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.messages.update((msgs) => [
            ...msgs,
            { id: this.newMessageId(), role: 'assistant', content: response.answer },
          ]);
          this.isLoading.set(false);
          this.scrollToBottom();
        },
        error: () => {
          this.messages.update((msgs) => [
            ...msgs,
            {
              id: this.newMessageId(),
              role: 'assistant',
              content: ERROR_MESSAGE,
              isError: true,
            },
          ]);
          this.isLoading.set(false);
          // The error asks the user to send the message again, so put it back in the composer:
          // resending is one keypress, not retyping. Text typed while waiting is never replaced.
          if (!this.userInput().trim()) {
            this.userInput.set(question);
            afterNextRender(() => this.autosize()?.resizeToFitContent(true), { injector: this.injector });
          }
          this.scrollToBottom();
        },
      });
  }

  private newMessageId(): string {
    return String(this.nextMessageId++);
  }

  private scrollToBottom() {
    afterNextRender(
      () => {
        const el = this.scrollContainer()?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      },
      { injector: this.injector },
    );
  }
}

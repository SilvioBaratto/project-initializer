/**
 * Tests for ChatbotComponent (Angular Material outlined composer + message log).
 * Criteria: one visually hidden h1; an empty state until the first message; the
 * history is a polite, labelled, keyboard-scrollable log; the composer is an
 * outlined form field with an autosizing textarea; Send is disabled only while the
 * message is empty or a reply is pending, and activating it moves focus to the
 * composer so focus is not lost when Send turns disabled; Enter sends and
 * Shift+Enter does not; replies, errors and the typing status render in the log.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { Subject } from 'rxjs';
import { vi } from 'vitest';
import { ICON_PROVIDER } from '../../icons';
import { ChatResponse } from '../../models/chat';
import { ChatService } from '../../services/chat';
import { ChatbotComponent } from './chatbot';

describe('ChatbotComponent', () => {
  let fixture: ComponentFixture<ChatbotComponent>;
  let component: ChatbotComponent;
  let el: HTMLElement;
  let loader: HarnessLoader;
  let reply: Subject<ChatResponse>;
  let sendMessage: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    reply = new Subject<ChatResponse>();
    sendMessage = vi.fn(() => reply.asObservable());

    await TestBed.configureTestingModule({
      imports: [ChatbotComponent],
      providers: [ICON_PROVIDER, { provide: ChatService, useValue: { sendMessage } }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatbotComponent);
    component = fixture.componentInstance;
    el = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  const log = () => el.querySelector<HTMLElement>('[role="log"]')!;
  const textarea = () => el.querySelector<HTMLTextAreaElement>('textarea')!;
  const input = () => loader.getHarness(MatInputHarness);
  const sendButton = () =>
    loader.getHarness(MatButtonHarness.with({ selector: '[aria-label="Send message"]' }));

  async function type(value: string): Promise<void> {
    await (await input()).setValue(value);
  }

  function pressEnter(init: KeyboardEventInit = {}): KeyboardEvent {
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, ...init });
    textarea().dispatchEvent(event);
    return event;
  }

  describe('structure', () => {
    it('renders exactly one h1, naming the view for assistive technology', () => {
      const headings = el.querySelectorAll('h1');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('Chat');
      expect(headings[0].classList).toContain('cdk-visually-hidden');
    });

    it('shows the empty state with an h2 while there are no messages', () => {
      const h2 = el.querySelector('h2');
      expect(h2?.textContent?.trim()).toBe('Start a conversation');
      expect(el.querySelector('.empty-text')?.textContent?.trim()).toBe('Ask anything to get started');
    });

    it('exposes the history as a polite, labelled log that the keyboard can scroll', () => {
      expect(log().getAttribute('aria-live')).toBe('polite');
      expect(log().getAttribute('aria-label')).toBe('Chat messages');
      expect(log().getAttribute('tabindex')).toBe('0');
    });

    it('hides decorative icons from assistive technology', () => {
      const icons = Array.from(el.querySelectorAll('lucide-icon'));
      expect(icons.length).toBeGreaterThan(0);
      for (const icon of icons) {
        expect(icon.getAttribute('aria-hidden')).toBe('true');
      }
    });
  });

  describe('composer', () => {
    it('is an outlined Material form field with an autosizing, labelled textarea', async () => {
      const field = await loader.getHarness(MatFormFieldHarness);
      expect(await field.getAppearance()).toBe('outline');
      expect(await field.hasLabel()).toBe(false);

      const control = await input();
      expect(await control.getPlaceholder()).toBe('Type a message');
      expect(textarea().getAttribute('aria-label')).toBe('Chat message');
      expect(textarea().classList).toContain('cdk-textarea-autosize');
    });

    it('offers Send as an icon button with an arrow-up icon', async () => {
      const button = await sendButton();
      expect(await button.getVariant()).toBe('icon');
      expect(await button.getType()).toBe('submit');
      const host = el.querySelector('button[aria-label="Send message"]')!;
      expect(host.querySelector('lucide-icon')?.getAttribute('name')).toBe('arrow-up');
    });

    it('keeps Send disabled while the message is empty or only whitespace', async () => {
      expect(await (await sendButton()).isDisabled()).toBe(true);

      await type('   ');
      expect(await (await sendButton()).isDisabled()).toBe(true);

      await type('Hello');
      expect(await (await sendButton()).isDisabled()).toBe(false);
    });

    it('prevents the native form submission so the page never navigates', async () => {
      const form = el.querySelector('form')!;
      const event = new Event('submit', { bubbles: true, cancelable: true });
      form.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);
    });
  });

  describe('sending', () => {
    it('sends the trimmed message with the history when Send is clicked', async () => {
      await type('  Hello  ');
      await (await sendButton()).click();

      expect(sendMessage).toHaveBeenCalledWith('Hello', ['user: Hello']);
      const bubble = el.querySelector('.message-user');
      expect(bubble?.querySelector('.message-text')?.textContent).toBe('Hello');
      expect(await (await input()).getValue()).toBe('');
      expect(el.querySelector('h2')).toBeNull();
    });

    it('labels each message with its sender for assistive technology', async () => {
      await type('Hello');
      await (await sendButton()).click();
      reply.next({ answer: 'Hi there' });
      await fixture.whenStable();

      expect(el.querySelector('.message-user .cdk-visually-hidden')?.textContent).toBe('You');
      expect(el.querySelector('.message-assistant .cdk-visually-hidden')?.textContent).toBe('Assistant');
    });

    it('shows the typing status and disables Send while waiting, keeping the textarea editable', async () => {
      await type('Hello');
      await (await sendButton()).click();

      const status = el.querySelector('[role="status"]');
      expect(status?.textContent).toContain('Assistant is typing…');
      expect(status?.querySelector('.typing-dots')?.getAttribute('aria-hidden')).toBe('true');
      expect(component.isLoading()).toBe(true);

      await type('Next question');
      expect(await (await input()).isDisabled()).toBe(false);
      expect(await (await sendButton()).isDisabled()).toBe(true);
    });

    it('appends the answer and removes the typing status when the reply arrives', async () => {
      await type('Hello');
      await (await sendButton()).click();

      reply.next({ answer: 'Hi there' });
      await fixture.whenStable();

      expect(el.querySelector('.message-assistant .message-text')?.textContent).toBe('Hi there');
      expect(el.querySelector('[role="status"]')).toBeNull();
      expect(component.isLoading()).toBe(false);
      expect(component.messages().map((m) => m.role)).toEqual(['user', 'assistant']);
    });

    it('appends an error message with recovery copy when the request fails', async () => {
      await type('Hello');
      await (await sendButton()).click();

      reply.error(new Error('network'));
      await fixture.whenStable();

      const error = el.querySelector('.message-error');
      expect(error?.querySelector('.message-text')?.textContent).toBe(
        "Couldn't get a response. Send your message again.",
      );
      expect(error?.querySelector('lucide-icon')?.getAttribute('name')).toBe('circle-alert');
      expect(component.messages().at(-1)?.isError).toBe(true);
      expect(component.isLoading()).toBe(false);
    });

    it('puts the failed message back in the composer so sending it again is one action', async () => {
      await type('Hello');
      await (await sendButton()).click();
      expect(await (await input()).getValue()).toBe('');

      reply.error(new Error('network'));
      await fixture.whenStable();

      expect(await (await input()).getValue()).toBe('Hello');
      expect(await (await sendButton()).isDisabled()).toBe(false);

      await (await sendButton()).click();
      expect(sendMessage).toHaveBeenLastCalledWith('Hello', [
        'user: Hello',
        "assistant: Couldn't get a response. Send your message again.",
        'user: Hello',
      ]);
    });

    it('keeps a message typed while waiting instead of restoring the failed one', async () => {
      await type('Hello');
      await (await sendButton()).click();
      await type('Next question');

      reply.error(new Error('network'));
      await fixture.whenStable();

      expect(await (await input()).getValue()).toBe('Next question');
    });

    it('sends and shows the reply without crypto.randomUUID, which non-secure origins lack', async () => {
      // Plain HTTP on any origin other than localhost is not a secure context, so randomUUID is undefined there.
      Object.defineProperty(crypto, 'randomUUID', { configurable: true, value: undefined });
      try {
        await type('Hello');
        await (await sendButton()).click();
        reply.next({ answer: 'Hi there' });
        await fixture.whenStable();

        expect(sendMessage).toHaveBeenCalledWith('Hello', ['user: Hello']);
        expect(component.messages().map((m) => m.content)).toEqual(['Hello', 'Hi there']);
        const ids = component.messages().map((m) => m.id);
        expect(new Set(ids).size).toBe(ids.length);
      } finally {
        Reflect.deleteProperty(crypto, 'randomUUID');
      }
    });

    it('moves focus to the composer when Send is activated, so focus survives Send turning disabled', async () => {
      await type('Hello');
      const host = el.querySelector<HTMLButtonElement>('button[aria-label="Send message"]')!;
      host.focus();
      expect(document.activeElement).toBe(host);

      await (await sendButton()).click();

      expect(sendMessage).toHaveBeenCalledTimes(1);
      expect(await (await sendButton()).isDisabled()).toBe(true);
      expect(document.activeElement).toBe(textarea());
    });

    it('does not send another message while a reply is pending', async () => {
      await type('First');
      component.onSend();
      component.userInput.set('Second');
      component.onSend();

      expect(sendMessage).toHaveBeenCalledTimes(1);
    });

    it('scrolls the log to the newest message after it renders', async () => {
      const scroller = log();
      let scrollTop = 0;
      Object.defineProperty(scroller, 'scrollHeight', { configurable: true, get: () => 480 });
      Object.defineProperty(scroller, 'scrollTop', {
        configurable: true,
        get: () => scrollTop,
        set: (value: number) => (scrollTop = value),
      });

      await type('Hello');
      await (await sendButton()).click();
      await fixture.whenStable();

      expect(scrollTop).toBe(480);
    });
  });

  describe('keyboard', () => {
    it('sends on Enter and suppresses the newline', async () => {
      await type('Hello');
      const event = pressEnter();
      await fixture.whenStable();

      expect(event.defaultPrevented).toBe(true);
      expect(sendMessage).toHaveBeenCalledWith('Hello', ['user: Hello']);
    });

    it('inserts a newline on Shift+Enter instead of sending', async () => {
      await type('Hello');
      const event = pressEnter({ shiftKey: true });

      expect(event.defaultPrevented).toBe(false);
      expect(sendMessage).not.toHaveBeenCalled();
    });

    it('ignores Enter that confirms an IME composition', async () => {
      await type('こんにちは');
      const event = pressEnter({ isComposing: true });

      expect(event.defaultPrevented).toBe(false);
      expect(sendMessage).not.toHaveBeenCalled();
    });

    it('does nothing on Enter while the message is empty', async () => {
      pressEnter();
      expect(sendMessage).not.toHaveBeenCalled();
    });
  });
});

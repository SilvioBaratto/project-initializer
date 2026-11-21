/**
 * Validates src/modules/chatbot/sse.ts.
 */
import type { Response } from 'express';
import { applySseHeaders, SSE_HEADERS, writeSseEvent } from './sse';

function makeResponse() {
  const written: string[] = [];
  const headers = new Map<string, string>();
  const fake = {
    setHeader: (name: string, value: string) => headers.set(name, value),
    write: (frame: string) => written.push(frame),
  };
  // The helpers touch only setHeader and write, so the rest of the Express response is not faked.
  return { response: fake as unknown as Response, written, headers };
}

describe('writeSseEvent', () => {
  it('when a payload is written, then it is one data line terminated by a blank line', () => {
    const { response, written } = makeResponse();

    writeSseEvent(response, { content: 'Hello', done: false });

    expect(written).toEqual(['data: {"content":"Hello","done":false}\n\n']);
  });

  it('when the payload contains line breaks, then they are escaped so the event stays one frame', () => {
    const { response, written } = makeResponse();

    writeSseEvent(response, { content: 'line one\n\nline two' });

    expect(written).toEqual(['data: {"content":"line one\\n\\nline two"}\n\n']);
  });
});

describe('applySseHeaders', () => {
  it('when applied, then every SSE header is set on the response', () => {
    const { response, headers } = makeResponse();

    applySseHeaders(response);

    expect(Object.fromEntries(headers)).toEqual(SSE_HEADERS);
  });

  it('when inspected, then the headers disable caching and proxy buffering', () => {
    expect(SSE_HEADERS).toMatchObject({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    });
  });
});

import type { Response } from 'express';

/**
 * Headers of a server-sent-events response. `X-Accel-Buffering` stops nginx from holding chunks
 * back, which would make the stream arrive in one piece.
 */
export const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
  'X-Accel-Buffering': 'no',
} as const;

/**
 * Writes one server-sent event whose data line is the JSON form of `payload`.
 *
 * @param res - Response that already carries {@link SSE_HEADERS}.
 * @param payload - Any JSON-serializable value; the caller owns its shape.
 */
export function writeSseEvent(res: Response, payload: unknown): void {
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

/** Sets {@link SSE_HEADERS} on `res` without choosing a status, leaving it at 200. */
export function applySseHeaders(res: Response): void {
  for (const [name, value] of Object.entries(SSE_HEADERS)) {
    res.setHeader(name, value);
  }
}

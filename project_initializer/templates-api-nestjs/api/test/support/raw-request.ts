import { connect, type AddressInfo } from 'node:net';
import type { INestApplication } from '@nestjs/common';
import { httpServerOf } from './create-e2e-app';

const LOOPBACK = '127.0.0.1';

/**
 * Sends one request whose request line is written by hand, for targets an HTTP client library would
 * normalise first, such as the absolute form `GET http://user:pass@host/path HTTP/1.1`.
 *
 * @param app - An initialised application; its server starts listening on a free port if needed.
 * @param requestLine - The first line of the request, without the line break.
 * @returns The raw response, status line, headers and body.
 */
export async function sendRawRequest(app: INestApplication, requestLine: string): Promise<string> {
  const server = httpServerOf(app);
  if (!server.listening) {
    await new Promise<void>((resolve) => server.listen(0, LOOPBACK, resolve));
  }
  const { port } = server.address() as AddressInfo;
  return new Promise((resolve, reject) => {
    let answer = '';
    const socket = connect(port, LOOPBACK, () => {
      socket.write(`${requestLine}\r\nHost: localhost\r\nConnection: close\r\n\r\n`);
    });
    socket.setEncoding('utf8');
    socket.on('data', (chunk: string) => {
      answer += chunk;
    });
    socket.on('end', () => resolve(answer));
    socket.on('error', reject);
  });
}

import type { Params } from 'nestjs-pino';
import type { IncomingMessage, ServerResponse } from 'http';
import { v4 as uuidv4 } from 'uuid';

const REQUEST_ID_HEADER = 'x-request-id';

function genReqId(req: IncomingMessage, res: ServerResponse): string {
  const existing = req.headers[REQUEST_ID_HEADER] as string | undefined;
  const id = existing ?? uuidv4();
  res.setHeader(REQUEST_ID_HEADER, id);
  return id;
}

const devTransport =
  process.env.NODE_ENV !== 'production'
    ? { target: 'pino-pretty', options: { colorize: true, singleLine: true } }
    : undefined;

export const loggerConfig: Params = {
  pinoHttp: {
    level: (process.env.LOG_LEVEL ?? 'info').toLowerCase(),
    redact: ['req.headers.authorization', 'req.headers.cookie'],
    genReqId,
    transport: devTransport,
  },
};

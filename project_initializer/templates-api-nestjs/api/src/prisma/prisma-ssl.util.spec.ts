import { Client } from 'pg';
import { ENCRYPTED_DATABASE_SSLMODES } from '../config/env.base';
import { deriveSslOption, stripSslParameters } from './prisma-ssl.util';

/** Validates src/prisma/prisma-ssl.util.ts. */
describe('deriveSslOption', () => {
  it.each([...ENCRYPTED_DATABASE_SSLMODES])(
    'when the production schema accepts sslmode=%s, then TLS is on even for a single-label host',
    (sslmode) => {
      expect(deriveSslOption(`postgresql://u:p@db:5432/app?sslmode=${sslmode}`)).toBeDefined();
    },
  );

  it('when host is localhost, no ssl is returned', () => {
    const url = 'postgresql://postgres:postgres@localhost:5433/app_db?schema=public';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when host is 127.0.0.1, no ssl is returned', () => {
    const url = 'postgresql://postgres:postgres@127.0.0.1:5433/app_db?schema=public';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when host is the IPv6 loopback, no ssl is returned', () => {
    const url = 'postgresql://postgres:postgres@[::1]:5433/app_db?schema=public';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when host is the Supabase pooler, ssl with rejectUnauthorized false is returned', () => {
    const url =
      'postgresql://postgres.ref:pw@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true&sslmode=require';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  it('when DATABASE_URL is undefined, no ssl is returned', () => {
    expect(deriveSslOption(undefined)).toBeUndefined();
  });

  it('when DATABASE_URL is an empty string, no ssl is returned', () => {
    expect(deriveSslOption('')).toBeUndefined();
  });

  it('when DATABASE_URL is not a valid URL, no ssl is returned', () => {
    expect(deriveSslOption('not-a-url')).toBeUndefined();
  });

  it('when a non-local host contains the substring localhost in the password, ssl is still returned', () => {
    const url = 'postgresql://user:localhost-pw@aws-0-eu-west-1.pooler.supabase.com:6543/postgres';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  // The compose network case: the API reaches Postgres at the *service name*,
  // not localhost, and postgres:16-alpine serves no TLS. Requiring TLS here
  // fails every query with "The server does not support SSL connections", which
  // surfaces as `database: down` in the readiness probe.
  it('when host is the compose service name, no ssl is returned', () => {
    const url = 'postgresql://postgres:postgres@db:5432/app_db?schema=public';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when host is any other single-label hostname, no ssl is returned', () => {
    const url = 'postgresql://postgres:postgres@postgres:5432/app_db';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when sslmode is disable, no ssl is returned even for a remote host', () => {
    const url = 'postgresql://user:pw@db.example.com:5432/postgres?sslmode=disable';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when sslmode is require, ssl without certificate verification is returned even for a single-label host', () => {
    const url = 'postgresql://postgres:postgres@db:5432/app_db?sslmode=require';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  it('when sslmode is verify-full, the certificate is verified', () => {
    const url = 'postgresql://user:pw@db.example.com:5432/postgres?sslmode=verify-full';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: true });
  });

  it('when sslmode is verify-ca, the certificate is verified even for a single-label host', () => {
    const url = 'postgresql://postgres:postgres@db:5432/app_db?sslmode=verify-ca';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: true });
  });

  it('when sslmode is prefer on a single-label host, the host heuristic keeps it plaintext', () => {
    const url = 'postgresql://postgres:postgres@db:5432/app_db?sslmode=prefer';
    expect(deriveSslOption(url)).toBeUndefined();
  });

  it('when sslmode is prefer on a public host, the host heuristic returns unverified ssl', () => {
    const url = 'postgresql://user:pw@db.example.com:5432/postgres?sslmode=prefer';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  it('when a non-loopback IPv6 literal is used, ssl is returned', () => {
    const url = 'postgresql://user:pw@[2001:db8::1]:5432/postgres';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });
});

describe('stripSslParameters', () => {
  const REMOTE = 'postgresql://user:p%40ss@db.example.com:6543/postgres';

  it('when the URL carries TLS parameters, then they are removed and the rest is kept', () => {
    const url = `${REMOTE}?pgbouncer=true&sslmode=require&sslrootcert=/ca.pem&sslcert=/c.pem&sslkey=/k.pem&uselibpqcompat=true&schema=public`;

    expect(stripSslParameters(url)).toBe(`${REMOTE}?pgbouncer=true&schema=public`);
  });

  it('when the URL carries only a TLS parameter, then no query string is left behind', () => {
    expect(stripSslParameters(`${REMOTE}?sslmode=verify-full`)).toBe(REMOTE);
  });

  it('when the URL has no TLS parameters, then it is returned unchanged', () => {
    expect(stripSslParameters(`${REMOTE}?schema=public`)).toBe(`${REMOTE}?schema=public`);
  });

  it('when the value is not a URL, then it is returned unchanged', () => {
    expect(stripSslParameters('not-a-url')).toBe('not-a-url');
  });
});

describe('the ssl option node-postgres ends up with', () => {
  // node-postgres merges what it parses from the connection string over the options given in
  // code, so the derived option only counts when it is what a client really uses.
  function effectiveSslOf(url: string): unknown {
    const client = new Client({
      connectionString: stripSslParameters(url),
      ssl: deriveSslOption(url),
    });
    return (client as unknown as { connectionParameters: { ssl: unknown } }).connectionParameters
      .ssl;
  }

  it.each([
    ['require', 'postgresql://u:p@db.example.com:6543/postgres?sslmode=require'],
    ['prefer', 'postgresql://u:p@db.example.com:6543/postgres?sslmode=prefer'],
    ['no sslmode on a public host', 'postgresql://u:p@db.example.com:6543/postgres'],
  ])(
    'when sslmode is %s, then the pool encrypts without verifying the certificate',
    (_label, url) => {
      expect(effectiveSslOf(url)).toEqual({ rejectUnauthorized: false });
    },
  );

  it('when sslmode is verify-full, then the pool verifies the certificate', () => {
    const url = 'postgresql://u:p@db.example.com:6543/postgres?sslmode=verify-full';

    expect(effectiveSslOf(url)).toEqual({ rejectUnauthorized: true });
  });

  it('when sslmode is disable, then the pool stays in plaintext', () => {
    const url = 'postgresql://u:p@db.example.com:6543/postgres?sslmode=disable';

    expect(effectiveSslOf(url)).toBe(false);
  });

  it('when the URL asks for TLS, then node-postgres prints no security warning', () => {
    const warning = jest.spyOn(process, 'emitWarning').mockImplementation();

    effectiveSslOf('postgresql://u:p@db.example.com:6543/postgres?sslmode=require');

    expect(warning).not.toHaveBeenCalled();
    warning.mockRestore();
  });
});

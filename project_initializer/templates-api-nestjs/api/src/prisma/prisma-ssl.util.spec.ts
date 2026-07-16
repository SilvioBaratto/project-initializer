import { deriveSslOption } from './prisma-ssl.util';

describe('deriveSslOption', () => {
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

  it('when sslmode requires TLS, ssl is returned even for a single-label host', () => {
    const url = 'postgresql://postgres:postgres@db:5432/app_db?sslmode=require';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  it('when sslmode is verify-full, ssl is returned', () => {
    const url = 'postgresql://user:pw@db.example.com:5432/postgres?sslmode=verify-full';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });

  it('when a non-loopback IPv6 literal is used, ssl is returned', () => {
    const url = 'postgresql://user:pw@[2001:db8::1]:5432/postgres';
    expect(deriveSslOption(url)).toEqual({ rejectUnauthorized: false });
  });
});

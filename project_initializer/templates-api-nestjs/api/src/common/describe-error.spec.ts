import { describeError } from './describe-error';

/** Validates src/common/describe-error.ts. */
describe('describeError', () => {
  it('when given an Error, then returns its stack', () => {
    const failure = new Error('boom');

    expect(describeError(failure)).toBe(failure.stack);
  });

  it('when the Error has no stack, then falls back to its message', () => {
    const failure = new Error('boom');
    failure.stack = undefined;

    expect(describeError(failure)).toBe('boom');
  });

  it.each([
    ['a string', 'plain text', 'plain text'],
    ['a number', 42, '42'],
    ['undefined', undefined, 'undefined'],
    ['null', null, 'null'],
  ])('when given %s, then returns String(value)', (_label, thrown, expected) => {
    expect(describeError(thrown)).toBe(expected);
  });
});

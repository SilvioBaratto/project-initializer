import { Reflector } from '@nestjs/core';
import { IS_PUBLIC_KEY, Public } from './public.decorator';

class OpenController {
  @Public()
  handle(): void {}

  guarded(): void {}
}

/** Validates src/common/decorators/public.decorator.ts Public. */
describe('Public', () => {
  const reflector = new Reflector();

  it('when a handler is decorated, then the public flag is set on it', () => {
    expect(reflector.get<boolean>(IS_PUBLIC_KEY, OpenController.prototype.handle)).toBe(true);
  });

  it('when a handler is not decorated, then no flag is set', () => {
    expect(
      reflector.get<boolean | undefined>(IS_PUBLIC_KEY, OpenController.prototype.guarded),
    ).toBe(undefined);
  });
});

import { CustomDecorator, SetMetadata } from '@nestjs/common';

/** Metadata key `AccessTokenGuard` reads to let a route through without a token. */
export const IS_PUBLIC_KEY = 'isPublic';

/** Marks a route, or a whole controller, as reachable without authentication. */
export const Public = (): CustomDecorator<string> => SetMetadata(IS_PUBLIC_KEY, true);

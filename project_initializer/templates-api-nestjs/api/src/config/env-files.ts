/**
 * Dotenv files the application reads, most specific first: the project `.env` at the repository
 * root, one level above `api/`, then a local `api/.env`. Relative to the working directory, like
 * the paths `prisma.config.ts` loads. Where a key is set in both files the first one wins.
 */
export const ENV_FILE_PATHS: readonly string[] = ['../.env', '.env'];

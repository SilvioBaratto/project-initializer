// @ts-check
import eslint from '@eslint/js';
import { defineConfig } from 'eslint/config';
import prettierConfig from 'eslint-config-prettier';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig(
  {
    ignores: ['dist/**', 'generated/**', 'coverage/**', 'eslint.config.mjs'],
  },
  eslint.configs.recommended,
  tseslint.configs.recommendedTypeChecked,
  prettierConfig,
  {
    languageOptions: {
      globals: globals.node,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // A `!` silences the compiler about the very case that crashes at run time; narrow instead.
      '@typescript-eslint/no-non-null-assertion': 'error',
    },
  },
  {
    files: ['**/*.spec.ts', 'test/**/*.ts'],
    languageOptions: { globals: globals.jest },
    rules: {
      // `expect(service.method).toHaveBeenCalled()` reads a jest mock without calling it, which
      // is the intended use and not a lost `this`.
      '@typescript-eslint/unbound-method': 'off',
    },
  },
);

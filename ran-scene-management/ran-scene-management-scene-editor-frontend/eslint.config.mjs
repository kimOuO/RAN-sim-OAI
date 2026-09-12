import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactPlugin from 'eslint-plugin-react';
import reactHooksPlugin from 'eslint-plugin-react-hooks';

export default [
  {
    ignores: ['node_modules/', '.next/', 'dist/', 'build/', 'coverage/'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        React: 'readonly',
        JSX: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      react: reactPlugin,
      'react-hooks': reactHooksPlugin,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs.recommended.rules,
      ...reactPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      'no-undef': 'off', // TS 檔由 tsc 檢查符號;eslint 不認 DOM/Node 全域(要放在 recommended 展開之後)
      'react/react-in-jsx-scope': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
  },

  {
    // frontend_rule Import Boundary:services/ 不可 import hooks/ 或 components/
    files: ['services/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': ['error', { patterns: ['@/components/*', '@/hooks/*'] }] },
  },
];

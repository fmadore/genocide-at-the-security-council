import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

export default ts.config(
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	prettier,
	...svelte.configs.prettier,
	{
		languageOptions: {
			globals: { ...globals.browser, ...globals.node }
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			parserOptions: { projectService: true, extraFileExtensions: ['.svelte'], parser: ts.parser }
		}
	},
	{
		// Rules that need the type checker, wherever `tsconfig.json` can see the
		// file. A promise nobody awaits or catches fails nowhere: its rejection
		// reaches no message on the page and no test. The service worker is
		// excluded from the project by SvelteKit, so it is linted without types.
		//
		// One program built from `tsconfig.json` rather than the project service,
		// which makes the same pass about three times slower on this tree.
		files: ['src/**/*.ts', 'src/**/*.svelte', 'test/**/*.ts'],
		ignores: ['src/service-worker.ts'],
		languageOptions: {
			parserOptions: {
				project: './tsconfig.json',
				projectService: false,
				tsconfigRootDir: import.meta.dirname
			}
		},
		rules: {
			'@typescript-eslint/no-floating-promises': 'error'
		}
	},
	{
		rules: {
			// Every internal *static* route is written with resolve(), which this
			// rule is there to enforce. What is left are links it cannot check
			// statically: external URLs (the UN Digital Library, the DOI) and one
			// reader link whose query string is built at runtime. Leaving the rule
			// on would mean an eslint-disable on each of them and no protection
			// gained, since a wrong route would still slip through a template.
			'svelte/no-navigation-without-resolve': 'off'
		}
	},
	{
		ignores: [
			'build/',
			'.svelte-kit/',
			'static/',
			'node_modules/',
			'test-results/',
			'playwright-report/',
			'coverage/'
		]
	}
);

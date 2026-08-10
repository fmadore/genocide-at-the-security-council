import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

/**
 * The dashboard's unit tests.
 *
 * Kept separate from `vite.config.ts`, and without the SvelteKit plugin, so
 * that running the suite does not depend on the app building. What is tested
 * here is plain modules: which rows a figure shows and why it withholds some,
 * and what the fetch boundary refuses. The node environment is the point —
 * asserting against rendered SVG would test `d3-cloud`'s packing rather than
 * any decision this project makes, and would break on a version bump that
 * changed nothing a reader could see.
 */
export default defineConfig({
	test: {
		environment: 'node',
		include: ['src/**/*.test.ts'],
		alias: {
			// `$app/paths` is a SvelteKit virtual module and has no file behind it.
			// Aliased once here rather than mocked in each spec, so the next person
			// to add a test does not have to rediscover why it fails to resolve.
			'$app/paths': fileURLToPath(new URL('./test/app-paths.ts', import.meta.url))
		}
	}
});

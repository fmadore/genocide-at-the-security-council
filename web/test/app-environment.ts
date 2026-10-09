/**
 * Stands in for `$app/environment` while the tests run.
 *
 * A SvelteKit virtual module, like `$app/paths` beside it. The modules under
 * test run in the browser, so that is what this says; a test about the
 * prerender path mocks it to `browser: false` for itself.
 */
export const browser = true;
export const building = false;
export const dev = false;
export const version = 'test';

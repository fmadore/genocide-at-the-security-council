/**
 * Stands in for `$app/paths` while the tests run.
 *
 * `$app/paths` is a virtual module the SvelteKit Vite plugin creates, so it
 * does not resolve under plain Vitest. The plugin is deliberately not loaded:
 * these tests exercise ordinary modules, and starting the framework to resolve
 * one constant would make the suite slower and more fragile than the code it
 * guards. `base` is empty because nothing under test depends on the subpath the
 * site is deployed at — only on the shape of the URL the cache is keyed by.
 */
export const base = '';

import { describe, expect, it } from 'vitest';
import { DATA_CATALOG, DATA_ENDPOINTS, dataCatalogJson, llmsText } from './catalog';
import { canonicalUrl, PUBLIC_ORIGIN } from './seo';

describe('machine-readable discovery catalog', () => {
	it('resolves every endpoint under the public data origin with unique ids', () => {
		const ids = DATA_ENDPOINTS.map((endpoint) => endpoint.id);
		expect(new Set(ids).size).toBe(DATA_ENDPOINTS.length);
		for (const endpoint of DATA_ENDPOINTS) {
			expect(endpoint.path.startsWith('data/')).toBe(true);
			expect(endpoint.url).toBe(`${PUBLIC_ORIGIN}/${endpoint.path}`);
		}
	});

	it('marks every LLM usage and semantic endpoint as unvalidated', () => {
		const modelEndpoints = DATA_ENDPOINTS.filter(
			(endpoint) =>
				endpoint.path.startsWith('data/usage/') || endpoint.path.startsWith('data/semantic/')
		);
		expect(modelEndpoints.length).toBeGreaterThanOrEqual(4);
		for (const endpoint of modelEndpoints) {
			expect(endpoint.validated).toBe(false);
			expect(endpoint.epistemic_layer).not.toBe('computed_from_record');
			expect(endpoint.caveat).toBeTruthy();
		}
	});

	it('serialises valid JSON containing the corpus DOI and epistemic rules', () => {
		const parsed = JSON.parse(dataCatalogJson());
		expect(parsed.corpus.doi).toBe('10.7910/DVN/CKPTRB');
		expect(parsed.corpus.version).toBe('6.0');
		expect(parsed.epistemic_rules.length).toBeGreaterThanOrEqual(4);
		expect(parsed.endpoints.length).toBe(DATA_CATALOG.endpoints.length);
	});

	it('produces llms.txt pointing to the data catalogue, manifest, and MCP docs', () => {
		const text = llmsText();
		expect(text).toContain(canonicalUrl('/data-catalog.json'));
		expect(text).toContain(`${PUBLIC_ORIGIN}/data/manifest.json`);
		expect(text).toContain('UNVALIDATED PREVIEW');
		expect(text).toContain('docs/MCP.md');
	});
});

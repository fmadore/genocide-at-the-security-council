import { describe, expect, it } from 'vitest';
import {
	canonicalUrl,
	PAGE_METADATA,
	PUBLIC_PAGES,
	robotsText,
	sitemapXml,
	STRUCTURED_DATA_JSON
} from './seo';

describe('public page metadata', () => {
	it('has one unique canonical URL, title and description per public page', () => {
		const canonical = PUBLIC_PAGES.map((page) => canonicalUrl(page.path));
		expect(new Set(canonical).size).toBe(PUBLIC_PAGES.length);
		expect(new Set(PUBLIC_PAGES.map((page) => page.title)).size).toBe(PUBLIC_PAGES.length);
		expect(new Set(PUBLIC_PAGES.map((page) => page.description)).size).toBe(PUBLIC_PAGES.length);
		expect(canonical.every((url) => url.endsWith('/'))).toBe(true);
	});

	it('keeps query state out of canonical route URLs', () => {
		expect(canonicalUrl(PAGE_METADATA['/concordance/'].path)).toBe(
			'https://fmadore.github.io/genocide-at-the-security-council/concordance/'
		);
	});
});

describe('discovery documents', () => {
	it('lists each public route once and no dynamic meeting records', () => {
		const sitemap = sitemapXml();
		const locations = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
		for (const page of PUBLIC_PAGES) {
			expect(locations.filter((location) => location === canonicalUrl(page.path))).toHaveLength(1);
		}
		expect(sitemap).not.toContain('/reader/');
	});

	it('points crawlers to the canonical sitemap', () => {
		expect(robotsText()).toContain(`Sitemap: ${canonicalUrl('/sitemap.xml')}`);
	});

	it('describes one application and one derived dataset without treating figures as datasets', () => {
		const graph = JSON.parse(STRUCTURED_DATA_JSON)['@graph'];
		expect(graph.map((entry: { '@type': string }) => entry['@type'])).toEqual([
			'SoftwareApplication',
			'Dataset'
		]);
		expect(graph[1].isBasedOn['@id']).toBe('https://doi.org/10.7910/DVN/CKPTRB');
	});
});

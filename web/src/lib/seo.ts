export const SITE_NAME = 'Genocide at the Security Council';
export const PUBLIC_ORIGIN = 'https://fmadore.github.io/genocide-at-the-security-council';
export const REPOSITORY = 'https://github.com/fmadore/genocide-at-the-security-council';

export interface PageMetadata {
	path: string;
	title: string;
	description: string;
}

export const PAGE_METADATA = {
	'/': {
		path: '/',
		title: SITE_NAME,
		description:
			'Explore when, how and by whom the vocabulary of genocide was used in UN Security Council debates from 1992 to 2023.'
	},
	'/chronology/': {
		path: '/chronology/',
		title: `Chronology — ${SITE_NAME}`,
		description:
			'Compare the prevalence of genocide-related terms over time, with explicit denominators, reference events and links to the underlying speeches.'
	},
	'/language/': {
		path: '/language/',
		title: `Language — ${SITE_NAME}`,
		description:
			'Examine the words, registers and contexts surrounding genocide-related vocabulary in UN Security Council speeches.'
	},
	'/actors/': {
		path: '/actors/',
		title: `Actors — ${SITE_NAME}`,
		description:
			'Compare which delegations used genocide-related vocabulary, at what rate, and with which denominator and evidence.'
	},
	'/concordance/': {
		path: '/concordance/',
		title: `Concordance — ${SITE_NAME}`,
		description:
			'Search every matched occurrence in context and open the exact sentence and UN Security Council speech behind it.'
	},
	'/usage/': {
		path: '/usage/',
		title: `Usage — ${SITE_NAME}`,
		description:
			'Experimental, model-derived layer: which genocide each delegation invoked, and whether it asserted or rejected the word, with the quotation behind every label.'
	},
	'/methods/': {
		path: '/methods/',
		title: `Methods — ${SITE_NAME}`,
		description:
			'Read how the corpus, lexicon, denominators, statistical comparisons, provenance and validation boundaries are defined.'
	}
} as const satisfies Record<string, PageMetadata>;

export const PUBLIC_PAGES = Object.values(PAGE_METADATA);

export function canonicalUrl(path: string): string {
	const relative = path.replace(/^\/+/, '');
	return new URL(relative, `${PUBLIC_ORIGIN}/`).href;
}

export function sitemapXml(pages: readonly PageMetadata[] = PUBLIC_PAGES): string {
	const urls = pages.map((page) => `  <url><loc>${canonicalUrl(page.path)}</loc></url>`).join('\n');
	return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

export function robotsText(): string {
	return `User-agent: *\nAllow: /\nSitemap: ${canonicalUrl('/sitemap.xml')}\n`;
}

const creator = {
	'@type': 'Person',
	name: 'Frédérick Madore',
	url: 'https://www.frederickmadore.com/',
	sameAs: 'https://orcid.org/0000-0003-0959-2092'
};

export const STRUCTURED_DATA_JSON = JSON.stringify({
	'@context': 'https://schema.org',
	'@graph': [
		{
			'@type': 'SoftwareApplication',
			'@id': `${canonicalUrl('/')}#software`,
			name: SITE_NAME,
			description: PAGE_METADATA['/'].description,
			url: canonicalUrl('/'),
			applicationCategory: 'EducationalApplication',
			operatingSystem: 'Any',
			codeRepository: REPOSITORY,
			license: 'https://opensource.org/license/mit',
			author: creator
		},
		{
			'@type': 'Dataset',
			'@id': `${canonicalUrl('/')}#analytical-data`,
			name: `${SITE_NAME} — analytical data`,
			description:
				'Derived tables supporting the site’s analysis of genocide-related vocabulary in UN Security Council debates, 1992–2023.',
			url: canonicalUrl('/'),
			license: 'https://creativecommons.org/licenses/by/4.0/',
			creator,
			isBasedOn: {
				'@type': 'Dataset',
				name: 'The UN Security Council Debates',
				'@id': 'https://doi.org/10.7910/DVN/KGVSYH',
				version: '6.1',
				license: 'https://creativecommons.org/publicdomain/zero/1.0/'
			}
		}
	]
});

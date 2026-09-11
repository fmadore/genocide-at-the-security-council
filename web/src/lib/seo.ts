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
			'Explore when, how and by whom the vocabulary of genocide was used in UN Security Council debates from 1946 to 2024.'
	},
	'/chronology/': {
		path: '/chronology/',
		title: `Chronology — ${SITE_NAME}`,
		description:
			'Compare the prevalence of genocide-related terms over time, with counts, rates, historical reference dates and links to the speeches.'
	},
	'/language/': {
		path: '/language/',
		title: `Words in context — ${SITE_NAME}`,
		description:
			'Examine the words and phrases surrounding genocide-related vocabulary in UN Security Council speeches.'
	},
	'/actors/': {
		path: '/actors/',
		title: `Actors — ${SITE_NAME}`,
		description:
			'Compare which delegations used genocide-related vocabulary, relative to their own speech totals, with links to the evidence.'
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
			'Explore experimental language-model classifications of the cases mentioned and positions expressed when delegations use genocide.'
	},
	'/methods/': {
		path: '/methods/',
		title: `Methods — ${SITE_NAME}`,
		description:
			'Understand the speech collection, search terms, statistical comparisons and language models, and what has been checked.'
	},
	'/semantic/': {
		path: '/semantic/',
		title: `Semantic map — ${SITE_NAME}`,
		description:
			'Explore speech similarity with a model-derived map, affiliation and agenda filters, and links to related speeches.'
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
				'Derived tables supporting the site’s analysis of genocide-related vocabulary in UN Security Council debates, 1946–2024.',
			url: canonicalUrl('/'),
			license: 'https://creativecommons.org/licenses/by/4.0/',
			creator,
			isBasedOn: {
				'@type': 'Dataset',
				name: 'The UNSC Meetings and Speeches',
				'@id': 'https://doi.org/10.7910/DVN/CKPTRB',
				version: '5.0',
				license: 'https://creativecommons.org/publicdomain/zero/1.0/'
			}
		}
	]
});

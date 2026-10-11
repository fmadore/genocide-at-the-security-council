import { sitemapXml } from '#lib/seo.js';

export const prerender = true;

export const GET = () =>
	new Response(sitemapXml(), {
		headers: { 'content-type': 'application/xml; charset=utf-8' }
	});

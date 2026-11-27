import { dataCatalogJson } from '#lib/catalog.js';

export const prerender = true;

export const GET = () =>
	new Response(dataCatalogJson(), {
		headers: { 'content-type': 'application/json; charset=utf-8' }
	});

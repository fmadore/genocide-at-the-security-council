import { llmsText } from '#lib/catalog.js';

export const prerender = true;

export const GET = () =>
	new Response(llmsText(), {
		headers: { 'content-type': 'text/plain; charset=utf-8' }
	});

import { robotsText } from '#lib/seo.js';

export const prerender = true;

export const GET = () =>
	new Response(robotsText(), {
		headers: { 'content-type': 'text/plain; charset=utf-8' }
	});

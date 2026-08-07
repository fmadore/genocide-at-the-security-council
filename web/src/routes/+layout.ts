// Every page is a static file. The reader route opts out below, because
// prerendering it would mean generating 6,595 pages to show text that is
// already fetched as JSON.
export const prerender = true;
export const trailingSlash = 'always';

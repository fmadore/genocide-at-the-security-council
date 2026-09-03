<script lang="ts">
	import { canonicalUrl, PUBLIC_ORIGIN, SITE_NAME, type PageMetadata } from './seo';

	let {
		meta,
		structuredData
	}: {
		meta: PageMetadata;
		structuredData?: string;
	} = $props();

	const canonical = $derived(canonicalUrl(meta.path));
</script>

<svelte:head>
	<title>{meta.title}</title>
	<meta name="description" content={meta.description} />
	<link rel="canonical" href={canonical} />
	<meta property="og:type" content="website" />
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:title" content={meta.title} />
	<meta property="og:description" content={meta.description} />
	<meta property="og:url" content={canonical} />
	<meta property="og:image" content={`${PUBLIC_ORIGIN}/og.png`} />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={meta.title} />
	<meta name="twitter:description" content={meta.description} />
	<meta name="twitter:image" content={`${PUBLIC_ORIGIN}/og.png`} />
	{#if structuredData}
		<svelte:element this={"script"} type="application/ld+json">{structuredData}</svelte:element>
	{/if}
</svelte:head>

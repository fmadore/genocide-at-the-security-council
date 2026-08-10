import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	ssr: {
		// Lucide ships uncompiled `.svelte` behind its `./icons/*` entries. Node's
		// ESM loader has no opinion about that extension, so the icons have to be
		// bundled for SSR rather than required at runtime.
		noExternal: ['@lucide/svelte']
	},
	build: {
		// ECharts is the only heavy dependency; keeping it in its own chunk means
		// a page that shows no chart does not pay for it.
		rollupOptions: {
			output: {
				manualChunks: (id) =>
					id.includes('echarts') || id.includes('zrender') ? 'echarts' : undefined
			}
		}
	}
});

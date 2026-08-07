import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
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

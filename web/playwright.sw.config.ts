import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.E2E_SW_PORT ?? 4174);
const origin = `http://127.0.0.1:${port}`;
const base = process.env.E2E_BASE_PATH ?? '/genocide-at-the-security-council';

export default defineConfig({
	testDir: './e2e/service-worker',
	outputDir: './test-results/service-worker',
	workers: 1,
	forbidOnly: Boolean(process.env.CI),
	retries: process.env.CI ? 2 : 0,
	reporter: process.env.CI ? 'github' : 'list',
	use: {
		baseURL: origin,
		trace: 'retain-on-failure'
	},
	projects: [
		{
			name: 'chromium-service-worker',
			use: { ...devices['Desktop Chrome'] }
		}
	],
	webServer: {
		command: `npx vite build && npx vite preview --host 127.0.0.1 --port ${port} --strictPort`,
		url: `${origin}${base}/concordance/`,
		timeout: 120_000,
		reuseExistingServer: false,
		env: { ...process.env, E2E_FIXTURES: '1', BASE_PATH: base }
	}
});

export { base };

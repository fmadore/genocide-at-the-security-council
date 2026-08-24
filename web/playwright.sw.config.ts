import { defineConfig, devices } from '@playwright/test';

const origin = 'http://127.0.0.1:4174';
const base = '/genocide-at-the-security-council';

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
		command: 'npx vite build && npx vite preview --host 127.0.0.1 --port 4174 --strictPort',
		url: `${origin}${base}/concordance/`,
		timeout: 120_000,
		reuseExistingServer: !process.env.CI,
		env: { ...process.env, E2E_FIXTURES: '1' }
	}
});

export { base };

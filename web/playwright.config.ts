import { defineConfig, devices } from '@playwright/test';

const origin = 'http://127.0.0.1:4173';
const base = '/genocide-at-the-security-council';

export default defineConfig({
	testDir: './e2e/tests',
	outputDir: './test-results',
	fullyParallel: false,
	workers: 1,
	forbidOnly: Boolean(process.env.CI),
	retries: process.env.CI ? 2 : 0,
	reporter: process.env.CI ? 'github' : 'list',
	use: {
		baseURL: origin,
		// Fixture request interception must see the network directly. A production
		// service-worker journey will run against a built site separately.
		serviceWorkers: 'block',
		trace: 'retain-on-failure'
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] }
		}
	],
	webServer: {
		command: 'npm run dev -- --host 127.0.0.1 --port 4173',
		url: `${origin}${base}/concordance/`,
		timeout: 120_000,
		reuseExistingServer: !process.env.CI,
		env: { ...process.env, E2E_FIXTURES: '1' }
	}
});

export { base };

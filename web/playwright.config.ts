import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.E2E_PORT ?? 4173);
const origin = `http://127.0.0.1:${port}`;
const base = process.env.E2E_BASE_PATH ?? '/genocide-at-the-security-council';

export default defineConfig({
	testDir: './e2e/tests',
	outputDir: './test-results',
	fullyParallel: false,
	workers: 1,
	forbidOnly: Boolean(process.env.CI),
	retries: process.env.CI ? 2 : 0,
	// A test that passes only on a retry is reported as failed in CI rather
	// than as green: the retry is there to say a test is flaky, not to hide it.
	failOnFlakyTests: Boolean(process.env.CI),
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
		},
		{
			// The accessibility scans again, in the scheme a reader whose system is
			// set to dark gets from the first paint. Only the tests tagged @a11y
			// run here: the rest assert behaviour that does not change with colour.
			name: 'chromium-dark',
			grep: /@a11y/,
			use: { ...devices['Desktop Chrome'], colorScheme: 'dark' }
		}
	],
	webServer: {
		command: `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`,
		url: `${origin}${base}/concordance/`,
		timeout: 120_000,
		reuseExistingServer: false,
		env: { ...process.env, E2E_FIXTURES: '1', BASE_PATH: base }
	}
});

export { base };

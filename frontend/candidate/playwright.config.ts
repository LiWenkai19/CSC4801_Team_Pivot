import { defineConfig } from '@playwright/test'
const api = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18019'
const python = process.env.PIVOT_TEST_PYTHON ?? (process.platform === 'win32' ? '../../.venv/Scripts/python.exe' : '../../.venv/bin/python')
export default defineConfig({
  testDir: './e2e', workers: 1, timeout: 30000,
  use: { baseURL: process.env.PIVOT_BROWSER_BASE_URL ?? 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: process.env.PIVOT_BROWSER_BASE_URL ? undefined : [
    { command: `"${python}" ../../backend/candidate_tests/browser_server.py --port ${new URL(api).port}`, url: `${api}/openapi.json`, reuseExistingServer: false, timeout: 30000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort', url: 'http://127.0.0.1:5173', env: { VITE_API_BASE_URL: api }, reuseExistingServer: false, timeout: 30000 },
  ],
})

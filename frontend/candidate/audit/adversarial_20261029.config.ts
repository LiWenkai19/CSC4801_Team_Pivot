import { defineConfig } from '@playwright/test'
import base from '../playwright.config'
import { resolve } from 'node:path'

export default defineConfig({
  ...base,
  testDir: '.',
  testMatch: 'adversarial_20261029.diagnostic.ts',
  outputDir: '../../../../tmp/candidate-adversarial-20261029-browser',
  use: { ...base.use, channel: 'msedge' },
  webServer: Array.isArray(base.webServer)
    ? base.webServer.map(server => ({ ...server, cwd: resolve(import.meta.dirname, '..') }))
    : base.webServer,
})

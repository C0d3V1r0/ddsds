import { defineConfig } from '@playwright/test';
import fs from 'node:fs';

const passwordFile = '/opt/nullius/config/.initial_password';
const password = process.env.NULLIUS_DASHBOARD_PASSWORD
  ?? (fs.existsSync(passwordFile) ? fs.readFileSync(passwordFile, 'utf8').trim() : '');

export default defineConfig({
  testDir: '.',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.NULLIUS_DASHBOARD_URL ?? 'https://127.0.0.1',
    ignoreHTTPSErrors: true,
    httpCredentials: password ? {
      username: process.env.NULLIUS_DASHBOARD_USER ?? 'admin',
      password,
    } : undefined,
  },
});

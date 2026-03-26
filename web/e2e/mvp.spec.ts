import { expect, test } from '@playwright/test';

test.describe('Nullius MVP', () => {
  test('dashboard loads with live data', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByTestId('app-brand')).toContainText('NULLIUS');
    await expect(page.getByTestId('header-agent-status')).toHaveCount(0);
    await expect(page.getByTestId('header-live-status')).toHaveCount(0);

    await expect(page.getByTestId('metric-cpu-card')).toBeVisible();
    await expect(page.getByTestId('metric-ram-card')).toBeVisible();
    await expect(page.getByTestId('metric-disk-card')).toBeVisible();
    await expect(page.getByTestId('metric-network-card')).toBeVisible();
    await expect(page.getByTestId('dashboard-services-list')).not.toContainText('Ошибка загрузки данных');
    await expect(page.getByTestId('dashboard-events-list')).not.toContainText('Ошибка загрузки данных');
  });

  test('navigation pages render without data-load errors', async ({ page }) => {
    await page.goto('/');

    await page.getByTestId('nav-security').click();
    await expect(page.getByTestId('page-security')).toBeVisible();
    await expect(page.getByTestId('security-events-card')).toBeVisible();
    await expect(page.getByTestId('security-blocked-card')).toBeVisible();

    await page.getByTestId('nav-processes').click();
    await expect(page.getByTestId('page-processes')).toBeVisible();
    await expect(page.getByTestId('processes-table')).toBeVisible();
    await expect(page.getByTestId('processes-error')).toHaveCount(0);

    await page.getByTestId('nav-logs').click();
    await expect(page.getByTestId('page-logs')).toBeVisible();
    await expect(page.getByTestId('logs-card')).toBeVisible();
    await expect(page.getByTestId('logs-error')).toHaveCount(0);

    await page.getByTestId('nav-settings').click();
    await expect(page.getByTestId('page-settings')).toBeVisible();
    await expect(page.getByTestId('settings-system-status')).toContainText('API Сервер');
    await expect(page.getByTestId('settings-system-status')).toContainText('Агент');
    await expect(page.getByTestId('settings-system-status')).toContainText('База данных');
    await expect(page.getByTestId('settings-health-error')).toHaveCount(0);
  });

  test('security UI can block and unblock an IP', async ({ page }) => {
    const ip = '203.0.113.249';
    const reason = `playwright-mvp-${Date.now()}`;

    await page.goto('/security');

    await page.getByTestId('security-block-ip').fill(ip);
    await page.getByTestId('security-block-reason').fill(reason);
    await page.getByTestId('security-block-submit').click();

    const blockedTable = page.getByTestId('security-blocked-table');
    await expect(blockedTable).toContainText(ip);
    await expect(blockedTable).toContainText(reason);

    const row = page.locator('tr').filter({ hasText: ip });
    await row.getByRole('button', { name: 'Разблокировать' }).click();
    await expect(blockedTable).not.toContainText(ip);
  });

  test('theme toggle works on settings page', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByTestId('settings-theme-toggle')).toBeVisible();
    await page.getByTestId('settings-theme-toggle').click();
  });
});

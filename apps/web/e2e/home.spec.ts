import { test, expect } from '@playwright/test';

test('home page loads', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/MBA/i);
});

test('login form accepts email', async ({ page }) => {
  await page.goto('/');
  const emailInput = page.getByRole('textbox', { name: /email/i });
  await expect(emailInput).toBeVisible();
  await emailInput.fill('test@example.com');
  await expect(emailInput).toHaveValue('test@example.com');
});

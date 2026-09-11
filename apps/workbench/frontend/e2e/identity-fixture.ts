import { test as base, expect } from 'playwright/test';
export { expect };
export type { Page } from 'playwright/test';
export const test = base.extend<{ localIdentity: void }>({
  localIdentity: [async ({ page }, use) => {
    await page.route('**/auth/status', route => route.fulfill({ json: {
      mode: 'local', authenticated: true, browser_login: false, owner: null,
    } }));
    await use();
  }, { auto: true }],
});

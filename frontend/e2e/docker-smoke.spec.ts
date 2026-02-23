import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://localhost/api';
const RAG_URL = 'http://localhost/rag';

test.describe('Docker 환경 스모크 테스트', () => {
  test('프론트엔드가 정상적으로 로드된다', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const body = await page.textContent('body');
    const hasExpectedText =
      body?.includes('Bizi') || body?.includes('AI 상담') || body?.includes('비지');

    expect(hasExpectedText).toBeTruthy();
  });

  test('로그인 페이지에 Google 로그인 버튼이 있다', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    const body = await page.textContent('body');
    const hasLoginButton =
      body?.includes('Google') || body?.includes('로그인') || body?.includes('google');

    expect(hasLoginButton).toBeTruthy();
  });

  test('Backend API 헬스체크가 정상이다', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/health`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('status');
  });

  test('RAG API 헬스체크가 정상이다', async ({ request }) => {
    const response = await request.get(`${RAG_URL}/health`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('status');
  });

  test('메인 페이지에 채팅 입력창이 존재한다', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const inputSelectors = [
      'textarea',
      'input[type="text"]',
      '[placeholder*="메시지"]',
      '[placeholder*="질문"]',
      '[placeholder*="입력"]',
    ];

    let found = false;
    for (const selector of inputSelectors) {
      const element = await page.$(selector);
      if (element) {
        found = true;
        break;
      }
    }

    expect(found).toBeTruthy();
  });
});

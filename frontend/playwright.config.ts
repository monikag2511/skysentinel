import { defineConfig } from "@playwright/test";
export default defineConfig({
  testMatch: process.env.SKY_PRODUCTION_TEST ? ["production.spec.ts", "e2e.spec.ts"] : "e2e.spec.ts",
  workers: 1,
  timeout: 120000,
  expect: { timeout: 25000 },
  use: {
    baseURL: process.env.FRONTEND_URL || "http://127.0.0.1:5173",
    httpCredentials: process.env.SKY_PRODUCTION_TEST
      ? { username: "operator", password: process.env.SKY_OPERATOR_PASSWORD! }
      : undefined,
    channel: process.env.CI ? "chromium" : "msedge",
    reducedMotion: "reduce",
  },
});

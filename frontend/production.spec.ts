import { test, expect } from "@playwright/test";

test("viewer searches persisted incidents and exports results", async ({ browser, baseURL }) => {
  const context = await browser.newContext({baseURL, httpCredentials:{
    username:"viewer", password:process.env.SKY_VIEWER_PASSWORD!
  }});
  try {
    const page = await context.newPage();
    await page.goto("/");
    await expect(page.getByRole("button",{name:"Run scenario"})).toBeDisabled();
    await page.getByText("Investigate past incidents").click();
    await page.getByLabel("Search history").fill("Flight online");
    await page.getByRole("button",{name:"Search archive"}).click();
    await expect(page.locator(".archive li")).toHaveCount(3);
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button",{name:"Export loaded records"}).click();
    expect((await downloaded).suggestedFilename()).toBe("skysentinel-incidents.json");
    await page.getByLabel("Search history").fill("missing-record-9f8");
    await page.getByRole("button",{name:"Search archive"}).click();
    await expect(page.getByText("No matching incidents")).toBeVisible();
  } finally {
    await context.close();
  }
});

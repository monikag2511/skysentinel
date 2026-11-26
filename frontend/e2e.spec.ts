import { test, expect } from "@playwright/test";

test("continuous patrol advances the selected flight and pauses", async ({ page }) => {
  await page.goto("/");
  const strip = page.locator("aside");
  await expect(strip.getByRole("heading")).toHaveText("Alpha-Wing");
  const longitude = strip.locator("dl div").filter({ hasText: "Longitude" }).locator("dd");
  const initial = await longitude.innerText();
  await strip.getByRole("button", { name: "Start continuous patrol" }).click();
  await expect(longitude).not.toHaveText(initial);
  await strip.getByRole("button", { name: "Pause patrol" }).click();
  await expect(strip.getByRole("button", { name: "Start continuous patrol" })).toBeVisible();
});

test("select aircraft, reject a message, recover a flight and reload its history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Flight watch." }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Beta-Rotor/ }).click();
  await expect(page.locator("aside h2")).toHaveText("Beta-Rotor");
  await page.getByLabel("Filter ledger").selectOption("Selected aircraft");
  const scenario = page.getByLabel("Demo scenario");
  await scenario.selectOption("duplicate");
  await page.getByRole("button", { name: "Run scenario" }).click();
  const entry = page
    .locator("li")
    .filter({ hasText: "Duplicate sequence" })
    .first();
  await expect(entry).toBeVisible();
  await entry.getByRole("button", { name: "Acknowledge" }).click();
  await scenario.selectOption("gps");
  await page.getByRole("button", { name: "Run scenario" }).click();
  await page.getByRole("button", { name: "Return to base" }).click();
  await page.getByRole("button", { name: "Resume patrol" }).click();
  await page.reload();
  await expect(
    page.getByText("Returned to base", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "View test results" }).click();
  await expect(page.getByText(/400 held-out samples/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByLabel("Interactive flight trajectory chart"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

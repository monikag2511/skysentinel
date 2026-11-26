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

test("integrated cybersecurity modules: drone CRUD, attack simulation, recovery, ML, alerts, analytics, and reports", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");

  // 1. Security Dashboard KPIs visible
  await expect(page.getByText("REGISTERED DRONES")).toBeVisible();

  // 2. Drone Management: register & delete a drone
  await page.getByRole("button", { name: "Drone Management" }).click();
  await page.getByPlaceholder("e.g. Delta-Hawk").fill("Echo-Scout");
  await page.getByRole("button", { name: "Register Drone" }).click();
  await expect(page.getByText(/Registered Echo-Scout/)).toBeVisible();
  const echoRow = page.locator("tr").filter({ hasText: "Echo-Scout" });
  await echoRow.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText(/Deleted Echo-Scout/)).toBeVisible();

  // 3. Attack Simulation -> GPS spoofing -> Recovery -> Alerts
  await page.getByRole("button", { name: "Attack Simulation" }).click();
  await page.getByRole("button", { name: "Simulate GPS Spoofing Attack" }).click();
  await expect(page.getByText(/Completed: GPS Spoofing Attack/)).toBeVisible();
  await page.getByRole("button", { name: "Open Recovery Console" }).click();
  await expect(page.getByText("Incident Recovery & Operator Override")).toBeVisible();
  await page.locator(".card").filter({ hasText: "Active Recovery Recommendations" }).getByRole("button", { name: "Return to Home" }).first().click();
  await expect(page.getByText(/Simulated recovery 'Return to Home' completed/)).toBeVisible();

  // 4. Verify ML Analysis, Network, Analytics, Logs, Reports, and Admin pages load cleanly
  await page.getByRole("button", { name: "ML & Spoofing Analysis" }).click();
  await expect(page.getByText("Confusion Matrix")).toBeVisible();
  await expect(page.getByText("Feature Importance")).toBeVisible();

  await page.getByRole("button", { name: "Network & Comms" }).click();
  await expect(page.getByText("Trusted & Blocked Devices")).toBeVisible();

  await page.getByRole("button", { name: "Security Alerts" }).click();
  await expect(page.getByText(/Live Alerts & Notification History/)).toBeVisible();

  await page.getByRole("button", { name: "Multi-Drone Health" }).click();
  await expect(page.getByText("Fleet Health & Security Matrix")).toBeVisible();

  await page.getByRole("button", { name: "Security Analytics" }).click();
  await expect(page.getByText("Threat Trends & Telemetry Distribution")).toBeVisible();

  await page.getByRole("button", { name: "Security Logs" }).click();
  await expect(page.getByText(/Complete Audit & Security Log/)).toBeVisible();

  await page.getByRole("button", { name: "Report Generation" }).click();
  await expect(page.getByRole("button", { name: "Download PDF Report" })).toBeVisible();

  await page.getByRole("button", { name: "Admin Management" }).click();
  await expect(page.getByText("Security & ML Thresholds")).toBeVisible();

  expect(errors).toEqual([]);
});

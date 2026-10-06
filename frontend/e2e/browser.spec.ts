import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

test("extraction shows source units and keeps all-page evidence navigable", async ({
  page,
}) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  const audit = await (
    await page.request.get(
      `http://127.0.0.1:8000/api/audits/${process.env.E2E_AUDIT_ID || rows[0].id}`,
    )
  ).json();
  const document = audit.documents.find(
    (doc: { role: string }) => doc.role === "invoice",
  );
  const quantities = document?.extraction?.observations.filter(
    (obs: { field_key: string; unit: string | null }) =>
      obs.field_key === "item.quantity" && obs.unit,
  );
  test.skip(!quantities?.length, "Requires saved item units");
  await page.goto(`/?audit=${audit.id}&stage=extraction`);
  await page
    .locator(".document-list button")
    .filter({ hasText: "Hóa đơn" })
    .click();
  await expect(page.locator(".results-main")).toContainText(
    "Thông tin của tất cả các trang",
  );
  const quantityRows = page
    .locator(".extraction-table tbody tr")
    .filter({ hasText: "Số lượng" });
  await expect(quantityRows).toHaveCount(quantities.length);
  for (const [index, observation] of quantities.entries()) {
    await expect(quantityRows.nth(index)).toContainText(
      `Đơn vị: ${observation.unit}`,
    );
  }
  const secondPageRow = page
    .locator(".extraction-table tbody tr")
    .filter({ hasText: "Trang 2" })
    .first();
  await secondPageRow.getByRole("button", { name: "Trang 2" }).click();
  await expect(page.locator(".page-preview")).toHaveAttribute(
    "src",
    /pages\/2$/,
  );
  await page.screenshot({
    path: path.resolve(
      "..",
      "data",
      "screenshots",
      "extraction-source-units.png",
    ),
  });
});

test("saved numerical finding exposes its verified source formulas", async ({
  page,
}) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  const audit = await (
    await page.request.get(
      `http://127.0.0.1:8000/api/audits/${process.env.E2E_AUDIT_ID || rows[0].id}`,
    )
  ).json();
  const finding = audit.report.findings.find(
    (item: { scope: string; verified_checks?: unknown[] }) =>
      item.scope === "cross" && item.verified_checks?.length,
  );
  test.skip(!finding, "Requires a source-formula verified cross finding");
  await page.goto(`/?audit=${audit.id}&stage=cross_audit`);
  await page
    .locator(".anomaly-item")
    .filter({ hasText: finding.title })
    .click();
  await page.locator(".verified-checks summary").click();
  await expect(page.locator(".verified-checks li")).toHaveCount(
    finding.verified_checks.length,
  );
  for (const check of finding.verified_checks) {
    await expect(page.locator(".verified-checks")).toContainText(check.purpose);
  }
  await expect(page.locator(".verified-checks p").first()).toContainText(
    "Hóa đơn",
  );
  await page.screenshot({
    path: path.resolve(
      "..",
      "data",
      "screenshots",
      "verified-source-formulas.png",
    ),
  });
});

test("audit stages isolate findings and retain selection", async ({ page }) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  const audit = await (
    await page.request.get(
      `http://127.0.0.1:8000/api/audits/${process.env.E2E_AUDIT_ID || rows[0].id}`,
    )
  ).json();
  const internal = audit.report.findings.filter(
    (finding: { scope: string }) => finding.scope === "internal",
  );
  const cross = audit.report.findings.filter(
    (finding: { scope: string }) => finding.scope === "cross",
  );
  test.skip(!internal.length || !cross.length, "Requires both audit scopes");
  // Preserve compatibility with bookmarks to the former combined audit stage.
  await page.goto(`/?audit=${audit.id}&stage=audit`);
  await expect(page.locator(".workflow-steps button")).toHaveCount(6);
  await expect(page.locator("#internal_audit")).toBeVisible();
  const groups = page.locator(".document-anomalies");
  await expect(groups).toHaveCount(audit.documents.length);
  for (const [index, document] of audit.documents.entries()) {
    const refs = new Set(
      (document.extraction?.observations || []).map(
        (obs: { id: string }) => obs.id,
      ),
    );
    const expected = internal.filter((finding: { observation_ids: string[] }) =>
      finding.observation_ids.some((ref) => refs.has(ref)),
    );
    await expect(groups.nth(index).locator("summary .tag")).toHaveText(
      `${expected.length} vấn đề`,
    );
    await expect(groups.nth(index).locator(".anomaly-item")).toHaveCount(
      expected.length,
    );
    for (const finding of expected) {
      await groups
        .nth(index)
        .locator(`.anomaly-item[data-finding-id="${finding.id}"]`)
        .click();
      await expect(page.locator("#internal_audit .finding h3")).toHaveText(
        finding.title,
      );
      await expect(page.locator(".related-document")).toHaveCount(1);
      await expect(page.locator(".related-document")).toHaveAttribute(
        "data-document-id",
        document.id,
      );
    }
  }
  async function expectAlignedPanels() {
    const bounds = await page
      .locator(".audit-workspace > .panel")
      .evaluateAll((panels) =>
        panels.map((panel) => {
          const { top, height } = panel.getBoundingClientRect();
          return { top, height };
        }),
      );
    expect(bounds).toHaveLength(3);
    for (const bound of bounds) {
      expect(Math.abs(bound.top - bounds[0].top)).toBeLessThan(1);
      expect(Math.abs(bound.height - bounds[0].height)).toBeLessThan(1);
    }
  }
  await expectAlignedPanels();
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(
    internal.length,
  );
  const selected = internal[internal.length - 1];
  await page
    .locator(`.anomaly-list .anomaly-item[data-finding-id="${selected.id}"]`)
    .click();
  await expect(page.locator("#internal_audit .finding h3")).toHaveText(
    selected.title,
  );
  await page.getByRole("button", { name: /04.*Đối chiếu chứng từ/ }).click();
  await expect(page).toHaveURL(/stage=cross_audit/);
  await expect(page.locator("#internal_audit")).toHaveCount(0);
  await expect(page.locator("#cross_audit")).toBeVisible();
  await expectAlignedPanels();
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(
    cross.length,
  );
  await page.screenshot({
    path: path.resolve("..", "data", "screenshots", "cross-audit-stage.png"),
  });
  await page.getByLabel("Tìm vấn đề").fill("xyz no matching issue");
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(0);
  await page.getByRole("button", { name: /03.*Kiểm tra nội bộ/ }).click();
  await expect(page.getByLabel("Tìm vấn đề")).toHaveValue("");
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(
    internal.length,
  );
  await expect(page.locator("#internal_audit .finding h3")).toHaveText(
    selected.title,
  );
  await expect(page.locator(".related-document")).toHaveCount(1);
  await page.screenshot({
    path: path.resolve("..", "data", "screenshots", "internal-audit-stage.png"),
  });
});

test("anomaly navigator opens every cited document and page for the selected finding", async ({
  page,
}) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  const audit = await (
    await page.request.get(
      `http://127.0.0.1:8000/api/audits/${process.env.E2E_AUDIT_ID || rows[0].id}`,
    )
  ).json();
  const observations = audit.documents.flatMap(
    (doc: {
      extraction: {
        observations: { id: string; document_id: string; page_id: string }[];
      };
    }) => doc.extraction?.observations || [],
  );
  const findings = audit.report.findings;
  const cross = findings.find(
    (finding: { observation_ids: string[] }) =>
      new Set(
        observations
          .filter((obs: { id: string }) =>
            finding.observation_ids.includes(obs.id),
          )
          .map((obs: { document_id: string }) => obs.document_id),
      ).size >= 2,
  );
  test.skip(!cross, "Requires a saved cross-document finding");
  await page.goto(`/?audit=${audit.id}&stage=cross_audit`);
  await page
    .locator(".anomaly-list .anomaly-item")
    .filter({ hasText: cross.title })
    .click();
  await expect(page.locator("#cross_audit .finding")).toHaveCount(1);
  await expect(page.locator("#cross_audit .finding h3")).toHaveText(
    cross.title,
  );
  const relatedDocuments = new Set(
    observations
      .filter((obs: { id: string }) => cross.observation_ids.includes(obs.id))
      .map((obs: { document_id: string }) => obs.document_id),
  );
  await expect(page.locator(".related-document")).toHaveCount(
    relatedDocuments.size,
  );
  const pages = new Set(
    observations
      .filter((obs: { id: string }) => cross.observation_ids.includes(obs.id))
      .map((obs: { page_id: string }) => obs.page_id),
  );
  await expect(page.locator(".related-page")).toHaveCount(pages.size);
  for (const pageId of pages)
    await expect(page.locator(`[id="related-${pageId}"] img`)).toHaveCount(1);
  // Every cross finding must open its own cited pages, including identity evidence.
  for (const finding of findings.filter(
    (item: { scope: string }) => item.scope === "cross",
  )) {
    await page
      .locator(".anomaly-list .anomaly-item")
      .filter({ hasText: finding.title })
      .click();
    const cited = observations.filter((obs: { id: string }) =>
      finding.observation_ids.includes(obs.id),
    );
    const citedDocuments = new Set(
      cited.map((obs: { document_id: string }) => obs.document_id),
    );
    const citedPages = new Set(
      cited.map((obs: { page_id: string }) => obs.page_id),
    );
    await expect(page.locator(".related-document")).toHaveCount(
      citedDocuments.size,
    );
    await expect(page.locator(".related-page")).toHaveCount(citedPages.size);
    for (const pageId of citedPages)
      await expect(page.locator(`[id="related-${pageId}"] img`)).toHaveCount(1);
  }
  await page.screenshot({
    path: path.resolve("..", "data", "screenshots", "anomaly-navigator.png"),
  });
  await page.getByLabel("Tìm vấn đề").fill("không có vấn đề tương ứng xyz");
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(0);
  await expect(page.locator(".related-document")).toHaveCount(0);
  await page.getByLabel("Tìm vấn đề").fill("");
  await page.getByRole("button", { name: /03.*Kiểm tra nội bộ/ }).click();
  await page.getByLabel("Lọc mức độ").selectOption("medium");
  await expect(page.locator(".anomaly-list .anomaly-item")).toHaveCount(
    findings.filter(
      (finding: { scope: string; severity: string }) =>
        finding.scope === "internal" && finding.severity === "medium",
    ).length,
  );
  await expect(page.locator(".related-document")).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("stage switching preserves panel and page scrolling until refresh", async ({
  page,
}) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  const audit = await (
    await page.request.get(
      `http://127.0.0.1:8000/api/audits/${process.env.E2E_AUDIT_ID || rows[0].id}`,
    )
  ).json();
  const counts = audit.documents.map(
    (doc: { extraction?: { observations: unknown[] } }) =>
      doc.extraction?.observations.length || 0,
  );
  test.skip(!Math.max(...counts), "Requires saved extracted content to scroll");
  await page.goto(
    `/?audit=${process.env.E2E_AUDIT_ID || rows[0].id}&stage=extraction`,
  );
  // A failed document can be first in history; its empty panel cannot scroll.
  await page
    .locator(".document-list button")
    .nth(counts.indexOf(Math.max(...counts)))
    .click();
  await expect(page.locator(".extraction-table")).toBeVisible();
  await expect(page.locator(".page-preview")).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".page-preview")
        .evaluate(
          (img: HTMLImageElement) => img.complete && img.naturalWidth > 0,
        ),
    )
    .toBeTruthy();
  await page.locator(".results-main").evaluate((panel) => {
    panel.scrollTop = 300;
  });
  const mainBefore = await page
    .locator(".results-main")
    .evaluate((panel) => panel.scrollTop);
  expect(mainBefore).toBeGreaterThan(0);
  await page.locator(".document-viewer").evaluate((panel) => {
    panel.scrollTop = 120;
  });
  const before = await page
    .locator(".document-viewer")
    .evaluate((panel) => panel.scrollTop);
  await page.getByRole("button", { name: /05.*Chi phí/ }).click();
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await expect
    .poll(() =>
      page.locator(".results-main").evaluate((panel) => panel.scrollTop),
    )
    .toBe(mainBefore);
  await expect
    .poll(() =>
      page.locator(".document-viewer").evaluate((panel) => panel.scrollTop),
    )
    .toBe(before);
  await page.reload();
  await expect(page.locator(".page-preview")).toBeVisible();
  expect(
    await page.locator(".results-main").evaluate((panel) => panel.scrollTop),
  ).toBe(0);
  expect(
    await page.locator(".document-viewer").evaluate((panel) => panel.scrollTop),
  ).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 400));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
  await page.getByRole("button", { name: /05.*Chi phí/ }).click();
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
  await page.reload();
  await expect(page.locator(".page-preview")).toBeVisible();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

test("workflow order, automatic preview, evidence and USD/VND logs on latest saved audit", async ({
  page,
}) => {
  const rows = await (
    await page.request.get("http://127.0.0.1:8000/api/audits")
  ).json();
  test.skip(!rows.length, "Requires a saved audit");
  await page.goto(`/?audit=${process.env.E2E_AUDIT_ID || rows[0].id}`);
  await expect(page.locator(".page-preview")).toBeVisible();
  await expect(page.locator("#upload")).toBeVisible();
  await expect(page.locator("#extraction")).toHaveCount(0);
  await expect(page.locator("#internal_audit")).toHaveCount(0);
  await expect(page.locator("#usage")).toHaveCount(0);
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await expect(page.locator("#upload")).toHaveCount(0);
  await expect(page.locator("#extraction")).toBeVisible();
  await page
    .locator(".document-list")
    .getByRole("button", { name: /Hóa đơn/ })
    .click();
  await page.getByLabel("Trang chứng từ").selectOption("2");
  await expect(page.locator(".page-preview")).toHaveAttribute("alt", /trang 2/);
  await page.getByRole("button", { name: /03.*Kiểm tra/ }).click();
  await page.locator("#internal_audit .evidence-list button").first().click();
  await expect(
    page.locator(".document-viewer blockquote").first(),
  ).toBeVisible();
  await page.getByRole("button", { name: /05.*Chi phí/ }).click();
  await expect(page.locator(".document-viewer")).toHaveCount(0);
  await page.locator("#usage summary").click();
  await expect(page.locator("#usage")).not.toContainText("Neuron");
  await expect(page.locator("#usage")).toContainText("VND quy đổi");
  await page.getByLabel("Tỷ giá quy đổi (VND / USD)").fill("26000");
  const shots = path.resolve("..", "data", "screenshots");
  mkdirSync(shots, { recursive: true });
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await page.screenshot({ path: path.join(shots, "workflow-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: path.join(shots, "workflow-mobile.png") });
});

test("overview, upload grouping, saved live results and source evidence", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Kiểm tra trước khi thanh toán." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Phân tích hồ sơ/ }),
  ).toBeDisabled();
  const root = path.resolve("..");
  mkdirSync(path.join(root, "data", "screenshots"), { recursive: true });
  await page.screenshot({
    path: path.join(root, "data", "screenshots", "upload-redesign.png"),
    fullPage: true,
  });
  const samples = path.join(
    root,
    "Expense_Audit_System_Candidate_Pack",
    "Sample",
  );
  await page
    .getByLabel("Chứng từ 1", { exact: true })
    .setInputFiles(path.join(samples, "Sample_Purchase_Order.pdf"));
  await page
    .getByLabel("Chứng từ 2", { exact: true })
    .setInputFiles(path.join(samples, "Sample_Invoice.pdf"));
  await page
    .getByLabel("Chứng từ 3", { exact: true })
    .setInputFiles(path.join(samples, "Sample_Payment_Request.pdf"));
  await expect(
    page.getByRole("button", { name: /Phân tích hồ sơ/ }),
  ).toBeEnabled();
  // Reopen the already-paid-for live evaluation instead of consuming more allowance.
  const result = path.join(root, "data", "evaluations", "original.json");
  if (existsSync(result)) {
    const { audit_id } = JSON.parse(readFileSync(result, "utf8"));
    await page.goto(`/?audit=${audit_id}`);
    await page.getByRole("button", { name: /05.*Chi phí/ }).click();
    await expect(
      page.getByRole("heading", { name: "Sử dụng API & chi phí" }),
    ).toBeVisible();
    await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
    await page
      .locator(".document-list")
      .getByRole("button", { name: /Hóa đơn/ })
      .click();
    await expect(page.locator(".page-preview")).toBeVisible();
    await page.getByLabel("Trang chứng từ").selectOption("2");
    await expect(page.locator(".page-preview")).toHaveAttribute(
      "alt",
      /trang 2/,
    );
    const shots = path.join(root, "data", "screenshots");
    mkdirSync(shots, { recursive: true });
    await page.screenshot({
      path: path.join(shots, "results.png"),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Kiểm tra trước khi thanh toán." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.join(root, "data", "screenshots", "mobile.png"),
    fullPage: true,
  });
});

test("live automatic upload reaches persisted source-linked results", async ({
  page,
}) => {
  test.skip(
    process.env.LIVE_AI_E2E !== "1",
    "Opt in: this test spends the configured AI budget",
  );
  test.setTimeout(600000);
  const root = path.resolve("..");
  const samples = path.join(
    root,
    "Expense_Audit_System_Candidate_Pack",
    "Sample",
  );
  const clean = process.env.LIVE_AI_FIXTURE === "clean";
  await page.goto("/");
  // Deliberately reverse document order: recognition must use content.
  for (const [index, [role, filename]] of [
    ["payment_request", "Sample_Payment_Request.pdf"],
    ["invoice", "Sample_Invoice.pdf"],
    ["purchase_order", "Sample_Purchase_Order.pdf"],
  ].entries()) {
    await page
      .getByLabel(`Chứng từ ${index + 1}`, { exact: true })
      .setInputFiles(
        clean
          ? path.join(root, "data", "fixtures", "clean", role, filename)
          : path.join(samples, filename),
      );
  }
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/audits") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Phân tích hồ sơ/ }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(202);
  const { id } = await response.json();
  let audit;
  await expect
    .poll(
      async () => {
        audit = await (
          await page.request.get(`http://127.0.0.1:8000/api/audits/${id}`)
        ).json();
        return ["completed", "failed", "interrupted"].includes(audit.status);
      },
      { timeout: 540000, intervals: [3000] },
    )
    .toBeTruthy();
  const output = path.join(root, "data", "evaluations");
  mkdirSync(output, { recursive: true });
  const { writeFileSync } = await import("node:fs");
  writeFileSync(
    path.join(output, "browser-live.json"),
    JSON.stringify(audit, null, 2),
  );
  expect(audit.status).toBe("completed");
  expect(audit.assessment).toBe(
    clean ? "no_issues_detected_in_assessed_scope" : "review_required",
  );
  expect(
    audit.documents.map((document: { role: string }) => document.role).sort(),
  ).toEqual(["invoice", "payment_request", "purchase_order"]);
  expect(audit.usage.estimated_neurons).toBeGreaterThan(0);
  // Reopen the persisted result, including page two and actual metered usage.
  await page.goto(`/?audit=${id}`);
  await page.getByRole("button", { name: /05.*Chi phí/ }).click();
  await expect(
    page.getByRole("heading", { name: "Sử dụng API & chi phí" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await page
    .locator(".document-list")
    .getByRole("button", { name: /Hóa đơn/ })
    .click();
  await page.getByLabel("Trang chứng từ").selectOption("2");
  await expect(page.locator(".page-preview")).toHaveAttribute("alt", /trang 2/);
});

test("corrected live report reopens with recognition, source pages and usage", async ({
  page,
}) => {
  const root = path.resolve("..");
  const result = path.join(root, "data", "evaluations", "clean.json");
  test.skip(!existsSync(result), "Run the corrected live evaluation first");
  const { audit_id } = JSON.parse(readFileSync(result, "utf8"));
  const audit = await (
    await page.request.get(`http://127.0.0.1:8000/api/audits/${audit_id}`)
  ).json();
  test.skip(
    audit.status !== "completed",
    "Corrected live fixture has not completed; inspect EVALUATION.md for provider/test blockers",
  );
  expect(audit.status).toBe("completed");
  expect(audit.assessment).toBe("no_issues_detected_in_assessed_scope");
  expect(
    audit.documents.every(
      (document: { role_hint: string | null }) => document.role_hint === null,
    ),
  ).toBeTruthy();
  expect(
    audit.documents.map((document: { role: string }) => document.role).sort(),
  ).toEqual(["invoice", "payment_request", "purchase_order"]);
  await page.goto(`/?audit=${audit_id}`);
  await page.getByRole("button", { name: /05.*Chi phí/ }).click();
  await expect(
    page.getByRole("heading", { name: "Sử dụng API & chi phí" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /02.*Trích xuất/ }).click();
  await page
    .locator(".document-list")
    .getByRole("button", { name: /Hóa đơn/ })
    .click();
  await page.getByLabel("Trang chứng từ").selectOption("2");
  await expect(page.locator(".page-preview")).toHaveAttribute("alt", /trang 2/);
  const shots = path.join(root, "data", "screenshots");
  mkdirSync(shots, { recursive: true });
  await page.screenshot({
    path: path.join(shots, "corrected-results.png"),
    fullPage: true,
  });
});

test("pending source review shows saved extraction alongside source pages", async ({
  page,
}) => {
  const auditId = process.env.E2E_PARTIAL_AUDIT_ID;
  test.skip(!auditId, "Requires an explicit saved partial audit");
  const audit = await (
    await page.request.get(`http://127.0.0.1:8000/api/audits/${auditId}`)
  ).json();
  const document = audit.documents.find(
    (d: { extraction?: { processing_review_status?: string } }) =>
      d.extraction?.processing_review_status === "pending",
  );
  expect(document).toBeTruthy();
  expect(audit.assessment).toBe("incomplete_analysis");
  await page.goto(`/?audit=${auditId}&stage=extraction`);
  const roles: Record<string, string> = {
    purchase_order: "Đơn đặt hàng",
    invoice: "Hóa đơn",
    payment_request: "Đề nghị thanh toán",
  };
  await page
    .locator(".document-list button")
    .filter({ hasText: roles[document.role] })
    .click();
  await expect(page.locator(".document-data")).toContainText(
    "Rà soát ý nghĩa chưa hoàn tất",
  );
  await expect(page.locator(".document-data")).toContainText(
    document.extraction.observations[0].raw_value,
  );
  await expect(page.locator(".page-preview").first()).toBeVisible();
});

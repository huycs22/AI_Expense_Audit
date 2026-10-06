import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { api } from "../../shared/api";
import { assessments, fields, roles, statuses } from "../../shared/labels";
import type {
  Audit,
  DocumentDetail,
  Finding,
  Observation,
  DocumentType,
  ProofExpression,
} from "../../shared/types";
import { UsagePanel } from "../usage/UsagePanel";
import { TimingPanel } from "../usage/TimingPanel";
import { RelatedDocuments } from "./RelatedDocuments";
import { ObservationValue } from "../extraction/ObservationValue";
import {
  WorkflowSteps,
  steps,
  type WorkflowStage,
} from "../../shared/WorkflowSteps";

export function AuditView({ id, onBack }: { id: string; onBack: () => void }) {
  const [stage, setStage] = useState<WorkflowStage>(() => {
    const value = new URLSearchParams(location.search).get("stage");
    if (value === "audit") return "internal_audit";
    return steps.some(([id]) => id === value)
      ? (value as WorkflowStage)
      : "upload";
  });
  const scrollPositions = useRef<
    Partial<
      Record<
        WorkflowStage,
        {
          windowY: number;
          panels: Record<string, { top: number; left: number }>;
        }
      >
    >
  >({});
  const pendingSourceScroll = useRef<number | null>(null);
  const lastWindowY = useRef(0);
  const panelSelectors = [
    ".results-main",
    ".document-viewer",
    ".document-list",
    ".anomaly-list",
  ];
  useLayoutEffect(() => {
    // Keep positions only for this mounted audit; a refresh starts at the top.
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    window.scrollTo({ top: 0, behavior: "instant" });
    return () => {
      window.history.scrollRestoration = previous;
    };
  }, []);
  useLayoutEffect(() => {
    const saved = scrollPositions.current[stage];
    window.scrollTo({
      top: saved?.windowY ?? lastWindowY.current,
      behavior: "instant",
    });
    for (const [selector, position] of Object.entries(saved?.panels || {})) {
      const panel = document.querySelector<HTMLElement>(selector);
      if (panel)
        panel.scrollTo({
          top: position.top,
          left: position.left,
          behavior: "instant",
        });
    }
    pendingSourceScroll.current =
      saved?.panels[".document-viewer"]?.top ?? null;
  }, [stage]);
  function changeStage(next: WorkflowStage) {
    if (next === stage) return;
    lastWindowY.current = window.scrollY;
    scrollPositions.current[stage] = {
      windowY: window.scrollY,
      panels: Object.fromEntries(
        panelSelectors.map((selector) => {
          const panel = document.querySelector<HTMLElement>(selector);
          return [
            selector,
            { top: panel?.scrollTop ?? 0, left: panel?.scrollLeft ?? 0 },
          ];
        }),
      ),
    };
    setEvidence(null);
    setStage(next);
    const url = new URL(location.href);
    url.searchParams.set("stage", next);
    window.history.replaceState({}, "", url);
  }
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState("");
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [page, setPage] = useState(1);
  const [evidence, setEvidence] = useState<Observation | null>(null);
  const [auditFilters, setAuditFilters] = useState<
    Partial<
      Record<
        WorkflowStage,
        {
          severity: string;
          search: string;
          selectedFindingId: string | null;
        }
      >
    >
  >({});
  const { severity, search, selectedFindingId } = auditFilters[stage] || {
    severity: "all",
    search: "",
    selectedFindingId: null,
  };
  function updateAuditFilter(
    patch: Partial<NonNullable<(typeof auditFilters)[WorkflowStage]>>,
  ) {
    setAuditFilters((current) => ({
      ...current,
      [stage]: { severity, search, selectedFindingId, ...patch },
    }));
  }
  const sourceRequest = useRef(0);
  const firstDocumentId = audit?.documents[0]?.id;
  useEffect(() => {
    if (!firstDocumentId) return;
    let active = true;
    const request = ++sourceRequest.current;
    api
      .document(id, doc?.id || firstDocumentId)
      .then((result) => {
        if (active && request === sourceRequest.current) setDoc(result);
      })
      .catch((exc) => {
        if (active) setError(exc.message);
      });
    return () => {
      active = false;
    };
    // Refresh source pages when processing finishes, preserving selection.
  }, [id, firstDocumentId, audit?.status]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result = await api.audit(id);
        if (!active) return;
        setAudit(result);
        setError("");
        if (["queued", "processing"].includes(result.status))
          timer = setTimeout(poll, 2000);
      } catch (exc) {
        if (active)
          setError(exc instanceof Error ? exc.message : "Không mở được hồ sơ");
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id]);
  async function openEvidence(obs: Observation) {
    const request = ++sourceRequest.current;
    try {
      const document = await api.document(id, obs.document_id);
      if (request !== sourceRequest.current) return;
      setDoc(document);
      setPage(Number(obs.page_id.split(":p")[1]));
      setEvidence(obs);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không mở được trang");
    }
  }
  async function openDocument(documentId: string) {
    const request = ++sourceRequest.current;
    setPage(1);
    setEvidence(null);
    if (doc?.id === documentId) return;
    setDoc(null);
    try {
      const document = await api.document(id, documentId);
      if (request !== sourceRequest.current) return;
      setDoc(document);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không mở được chứng từ");
    }
  }
  async function retry() {
    try {
      await api.retry(id);
      setAudit(await api.audit(id));
      window.location.reload();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không thử lại được");
    }
  }
  if (!audit)
    return (
      <section className="panel">
        <p role="status">{error || "Đang mở hồ sơ…"}</p>
      </section>
    );
  const observations = audit.documents.flatMap(
    (d) => d.extraction?.observations || [],
  );
  const byId = Object.fromEntries(observations.map((o) => [o.id, o]));
  const allFindings = audit.report.findings || [];
  const isAuditStage = stage === "internal_audit" || stage === "cross_audit";
  const isCrossAudit = stage === "cross_audit";
  const findings = allFindings.filter(
    (finding) => finding.scope === (isCrossAudit ? "cross" : "internal"),
  );
  const reviews = isCrossAudit
    ? audit.report.cross
      ? [audit.report.cross]
      : []
    : audit.report.internal || [];
  const stageUnresolved = [
    ...new Set(reviews.flatMap((review) => review.unresolved_checks || [])),
  ];
  const stageReviewed = isCrossAudit
    ? !!audit.report.cross
    : reviews.length === audit.documents.length && reviews.length > 0;
  const filtered = findings.filter(
    (f) =>
      (severity === "all" || f.severity === severity) &&
      `${f.title} ${f.explanation}`
        .toLocaleLowerCase("vi-VN")
        .includes(search.toLocaleLowerCase("vi-VN")),
  );
  const selectedFinding =
    filtered.find((finding) => finding.id === selectedFindingId) ||
    filtered[0] ||
    null;
  const running = ["queued", "processing"].includes(audit.status);
  function calculations(finding: Finding) {
    const documentId = byId[finding.observation_ids[0]]?.document_id;
    const review =
      finding.scope === "cross"
        ? audit?.report.cross
        : audit?.report.internal?.find((r) => r.document_id === documentId);
    return (
      review?.calculations.filter((c) =>
        finding.calculation_ids.includes(c.id),
      ) || []
    );
  }
  function proofExpression(expression: ProofExpression): string {
    if ("observation_id" in expression) {
      const source = byId[expression.observation_id];
      if (!source) return "Nguồn chưa xác định";
      const document = audit?.documents.find(
        (item) => item.id === source.document_id,
      );
      return `${document ? roles[document.role] : "Chứng từ"}: ${fields[source.field_key] || source.field_key} (${source.raw_value})`;
    }
    const symbols: Record<string, string> = {
      sum: "+",
      multiply: "×",
      subtract: "−",
      divide: "÷",
      date_add_days: "+ ngày",
    };
    return `(${expression.operands.map(proofExpression).join(` ${symbols[expression.operation] || expression.operation} `)})`;
  }
  function renderFinding(finding: Finding, index: number) {
    return (
      <button
        key={finding.id}
        className={`anomaly-item ${selectedFinding?.id === finding.id ? "selected" : ""}`}
        data-finding-id={finding.id}
        aria-pressed={selectedFinding?.id === finding.id}
        onClick={() => {
          updateAuditFilter({ selectedFindingId: finding.id });
          setEvidence(null);
        }}
      >
        <span className={`severity ${finding.severity}`}>
          {{ high: "Cao", medium: "Trung bình", low: "Thấp" }[finding.severity]}
        </span>
        <strong>
          {index + 1}. {finding.title}
        </strong>
        <small>
          {finding.scope === "cross" ? "Giữa các chứng từ" : "Trong chứng từ"} ·{" "}
          {
            new Set(
              finding.observation_ids
                .map((ref) => byId[ref]?.document_id)
                .filter(Boolean),
            ).size
          }{" "}
          chứng từ
        </small>
      </button>
    );
  }
  return (
    <>
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={16} /> Quay lại tổng quan
      </button>
      <WorkflowSteps active={stage} onChange={changeStage} />
      {audit.verification_outdated && !running && (
        <div className="alert" role="alert">
          <p>
            Báo cáo này dùng phiên bản trích xuất hoặc kiểm chứng cũ. Cần chạy
            lại để áp dụng kiểm tra độ đầy đủ của nguồn, công thức và ý nghĩa
            của kết luận. Các kết luận cũ chưa được rà soát bằng phiên bản mới.
          </p>
          <button className="secondary" onClick={retry}>
            Kiểm tra lại với phiên bản mới
          </button>
        </div>
      )}
      {(error || audit.error) && (
        <p className="alert" role="alert">
          {error || audit.error}
        </p>
      )}
      {running && (
        <p className="alert" role="status">
          Đang xử lý hồ sơ: {statuses[audit.status]}
        </p>
      )}
      {(["upload", "extraction"].includes(stage) || isAuditStage) && (
        <div
          className={`stage-workspace ${isAuditStage ? "audit-workspace" : ""}`}
        >
          {!isAuditStage && (
            <aside
              className="panel document-list"
              aria-label="Danh sách chứng từ"
            >
              <span className="eyebrow">CHỨNG TỪ ĐÃ TẢI LÊN</span>
              {audit.documents.map((document, index) => (
                <button
                  key={document.id}
                  aria-pressed={doc?.id === document.id}
                  className={doc?.id === document.id ? "selected" : ""}
                  onClick={() => void openDocument(document.id)}
                >
                  <span className="document-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <strong>
                    {roles[document.role] || `Chứng từ ${index + 1}`}
                  </strong>
                  <small>{statuses[document.status] || document.status}</small>
                </button>
              ))}
            </aside>
          )}
          {isAuditStage && (
            <aside className="panel anomaly-list" aria-label="Danh sách vấn đề">
              <span className="eyebrow">QUẢN LÝ VẤN ĐỀ</span>
              <h3>
                {isCrossAudit ? "Giữa các chứng từ" : "Trong từng chứng từ"}
              </h3>
              <input
                className="anomaly-search"
                type="search"
                aria-label="Tìm vấn đề"
                placeholder="Tìm vấn đề…"
                value={search}
                onChange={(event) =>
                  updateAuditFilter({ search: event.target.value })
                }
              />
              <div className="filter-row">
                <span>{filtered.length} vấn đề</span>
                <select
                  aria-label="Lọc mức độ"
                  value={severity}
                  onChange={(e) =>
                    updateAuditFilter({ severity: e.target.value })
                  }
                >
                  <option value="all">Tất cả mức độ</option>
                  <option value="high">Mức cao</option>
                  <option value="medium">Mức trung bình</option>
                  <option value="low">Mức thấp</option>
                </select>
              </div>
              {isCrossAudit
                ? filtered.map(renderFinding)
                : audit.documents.map((document) => {
                    const documentFindings = findings.filter((finding) =>
                      finding.observation_ids.some(
                        (ref) => byId[ref]?.document_id === document.id,
                      ),
                    );
                    const visibleFindings = documentFindings.filter((finding) =>
                      filtered.includes(finding),
                    );
                    const internalReview = audit.report.internal?.find(
                      (review) => review.document_id === document.id,
                    );
                    return (
                      <details
                        className="document-anomalies"
                        key={document.id}
                        open
                      >
                        <summary>
                          <strong>{roles[document.role]}</strong>
                          <span
                            className="tag"
                            aria-label={`${roles[document.role]}: ${documentFindings.length} vấn đề`}
                          >
                            {documentFindings.length} vấn đề
                          </span>
                        </summary>
                        {visibleFindings.map(renderFinding)}
                        {!visibleFindings.length && (
                          <p className="muted">
                            {documentFindings.length
                              ? "Không có vấn đề phù hợp bộ lọc."
                              : internalReview?.processing_status ===
                                    "failed" ||
                                  !!internalReview?.unresolved_checks?.length
                                ? "Kiểm tra chưa đầy đủ; xem các nội dung chưa kết luận."
                                : internalReview
                                  ? "Chưa phát hiện vấn đề trong phạm vi đã kiểm tra."
                                  : "Chưa có kết quả kiểm tra chứng từ này."}
                          </p>
                        )}
                      </details>
                    );
                  })}
              {!filtered.length && (
                <p className="empty-state">Không có vấn đề phù hợp.</p>
              )}
            </aside>
          )}
          <section className="panel results-main">
            {stage === "upload" && (
              <section id="upload">
                <span className="eyebrow">BƯỚC 01 · TẢI LÊN</span>
                <h2>Thông tin chứng từ</h2>
                {doc ? (
                  <>
                    <h3>{roles[doc.role]}</h3>
                    <dl className="document-properties">
                      <div>
                        <dt>Loại chứng từ</dt>
                        <dd>{roles[doc.role]}</dd>
                      </div>
                      <div>
                        <dt>Số trang</dt>
                        <dd>{doc.pages.length}</dd>
                      </div>
                      <div>
                        <dt>Số tệp</dt>
                        <dd>{doc.files.length}</dd>
                      </div>
                      <div>
                        <dt>Nhận diện</dt>
                        <dd>
                          {audit.documents.find((d) => d.id === doc.id)
                            ?.role_hint
                            ? "Gợi ý từ người dùng"
                            : "AI tự nhận diện"}
                        </dd>
                      </div>
                    </dl>
                    <h3>Tệp đã tải lên</h3>
                    <div className="original-links">
                      {doc.files.map((file) => (
                        <a
                          key={file.id}
                          href={file.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {file.name}
                          <small>{file.media_type} · Mở bản gốc ↗</small>
                        </a>
                      ))}
                    </div>
                    <p className="muted">
                      Bản xem trước ở bên phải. Chọn Trích xuất để xem thông tin
                      AI đã đọc.
                    </p>
                  </>
                ) : (
                  <p role="status">Đang mở chứng từ…</p>
                )}
              </section>
            )}
            {stage === "extraction" && (
              <section id="extraction" className="workflow-section">
                <span className="eyebrow">BƯỚC 02 · TRÍCH XUẤT</span>
                <h2>Dữ liệu trích xuất</h2>
                <p>Chọn một giá trị để đối chiếu với trang nguồn bên cạnh.</p>

                {audit.documents
                  .filter((document) => document.id === doc?.id)
                  .map((document) => (
                    <div className="document-data" key={document.id}>
                      <div className="section-heading">
                        <h3>{roles[document.role]}</h3>
                        <button
                          className="text-button"
                          onClick={() => void openDocument(document.id)}
                        >
                          Mở chứng từ ↗
                        </button>
                      </div>
                      {doc?.id === document.id && (
                        <>
                          {document.extraction?.processing_review_status ===
                            "pending" && (
                            <p className="warning" role="status">
                              Đã lưu dữ liệu đọc từ chứng từ. Rà soát ý nghĩa
                              chưa hoàn tất; dữ liệu này chưa sẵn sàng để kết
                              luận kiểm tra.
                            </p>
                          )}
                          <p className="muted">
                            {statuses[document.status]} ·{" "}
                            {document.role_hint
                              ? "Có gợi ý loại từ người dùng"
                              : "Loại do AI nhận diện"}
                            {document.extraction &&
                              ` · AI nhận diện: ${roles[document.extraction.document_type as DocumentType] || document.extraction.document_type}`}
                          </p>
                          <p className="muted">
                            Thông tin của tất cả các trang. Chọn nguồn để xem
                            đúng trang PDF. Các thông tin lặp lại được giữ để
                            đối chiếu giữa các trang.
                          </p>
                          {!!document.extraction?.semantic_review?.changes
                            .length && (
                            <details>
                              <summary>
                                Rà soát ý nghĩa từ nguồn ·{" "}
                                {
                                  document.extraction.semantic_review.changes
                                    .length
                                }{" "}
                                cập nhật
                              </summary>
                              <p className="muted">
                                AI diễn giải vai trò và điều khoản từ nguồn gốc.
                                Bạn có thể đối chiếu từng giá trị với trang được
                                trích dẫn.
                              </p>
                              <ul>
                                {document.extraction.semantic_review.changes.map(
                                  (change, index) => (
                                    <li key={index}>
                                      {change.before && change.after
                                        ? `${fields[change.before.field_key] || change.before.field_key} → ${fields[change.after.field_key] || change.after.field_key}`
                                        : `Bổ sung: ${fields[change.added_field || ""] || change.added_field}`}
                                      {` · Trang ${change.page_id.split(":p")[1]}`}
                                    </li>
                                  ),
                                )}
                              </ul>
                            </details>
                          )}
                          <div className="table-scroll">
                            <table className="extraction-table">
                              <thead>
                                <tr>
                                  <th>Thông tin</th>
                                  <th>Giá trị</th>
                                  <th>Nguồn</th>
                                </tr>
                              </thead>
                              <tbody>
                                {document.extraction?.observations.map(
                                  (obs) => (
                                    <tr
                                      key={obs.id}
                                      className={
                                        evidence?.id === obs.id
                                          ? "selected-observation"
                                          : ""
                                      }
                                    >
                                      <td>
                                        {fields[obs.field_key] || obs.field_key}
                                        <small>
                                          {obs.group_key &&
                                            document.extraction?.observations.find(
                                              (item) =>
                                                item.field_key ===
                                                  "item.code" &&
                                                item.group_key ===
                                                  obs.group_key,
                                            )?.raw_value}{" "}
                                          {obs.role}
                                        </small>
                                      </td>
                                      <td>
                                        <ObservationValue observation={obs} />
                                      </td>
                                      <td>
                                        <button
                                          className="text-button"
                                          onClick={() => void openEvidence(obs)}
                                        >
                                          Trang {obs.page_id.split(":p")[1]}
                                        </button>
                                        <small>
                                          {obs.grounding === "text_verified"
                                            ? "Đã xác minh"
                                            : "Cần xác nhận"}
                                        </small>
                                      </td>
                                    </tr>
                                  ),
                                )}
                              </tbody>
                            </table>
                          </div>
                          {!document.extraction && (
                            <p className="muted">Chưa có dữ liệu trích xuất.</p>
                          )}
                          {!!document.extraction?.uncertainties.length && (
                            <div className="alert">
                              <strong>Dữ liệu cần xác nhận</strong>
                              <ul>
                                {document.extraction.uncertainties.map(
                                  (item, index) => (
                                    <li key={index}>{item}</li>
                                  ),
                                )}
                              </ul>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
              </section>
            )}
            {isAuditStage && (
              <section id={stage} className="workflow-section">
                <span className="eyebrow">
                  {isCrossAudit
                    ? "BƯỚC 04 · ĐỐI CHIẾU CHỨNG TỪ"
                    : "BƯỚC 03 · KIỂM TRA NỘI BỘ"}
                </span>
                <h2>
                  {isCrossAudit
                    ? "Đối chiếu giữa các chứng từ"
                    : "Kiểm tra nội bộ từng chứng từ"}
                </h2>
                <p className="muted">
                  {isCrossAudit
                    ? "Kiểm tra liên kết và đối chiếu thông tin giữa Đơn đặt hàng, Hóa đơn và Đề nghị thanh toán."
                    : "Kiểm tra tính nhất quán, phép tính và thông tin trên mọi trang của từng chứng từ."}
                </p>
                <p role="status" className="muted">
                  {stageReviewed ? "Đã có kết quả" : "Chưa hoàn tất kiểm tra"} ·{" "}
                  {findings.length} vấn đề trong bước này
                </p>
                <details className="audit-overview">
                  <summary>
                    Tổng quan hồ sơ · {allFindings.length} vấn đề ·{" "}
                    {statuses[audit.status]}
                  </summary>
                  <section className="panel result-summary">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">
                          HỒ SƠ {audit.id.slice(0, 8).toUpperCase()}
                        </span>
                        <h2>
                          {running
                            ? "Đang đọc & kiểm tra chứng từ…"
                            : assessments[audit.assessment]}
                        </h2>
                        <p>
                          {new Date(audit.created_at).toLocaleString("vi-VN")} ·{" "}
                          {statuses[audit.status]}
                        </p>
                      </div>
                      <span
                        className={`assessment-icon ${allFindings.length ? "warning" : ""}`}
                      >
                        {running ? (
                          <RefreshCw className="spin" />
                        ) : allFindings.length ? (
                          <AlertTriangle />
                        ) : (
                          <CheckCircle2 />
                        )}
                      </span>
                    </div>
                    {running && (
                      <>
                        <div className="progress-bar">
                          <span />
                        </div>
                        <p role="status" className="muted">
                          {audit.current_stage === "cross_document"
                            ? "Đang đối chiếu giữa ba chứng từ"
                            : "Đang trích xuất và kiểm tra từng chứng từ"}
                        </p>
                      </>
                    )}
                    <div className="metrics">
                      <div>
                        <span>Chứng từ</span>
                        <strong>{audit.documents.length}</strong>
                      </div>
                      <div>
                        <span>Vấn đề phát hiện</span>
                        <strong>{allFindings.length}</strong>
                      </div>
                      <div>
                        <span>Mức cao</span>
                        <strong>
                          {
                            allFindings.filter((f) => f.severity === "high")
                              .length
                          }
                        </strong>
                      </div>
                      <div>
                        <span>Chưa kết luận</span>
                        <strong>
                          {audit.report.unresolved_checks?.length || 0}
                        </strong>
                      </div>
                    </div>
                    {audit.error && (
                      <p role="alert" className="alert">
                        {audit.error}
                      </p>
                    )}
                    {error && (
                      <p role="alert" className="alert">
                        {error}
                      </p>
                    )}
                    {(["failed", "interrupted"].includes(audit.status) ||
                      (audit.status === "completed" &&
                        audit.assessment === "incomplete_analysis")) && (
                      <button className="secondary" onClick={retry}>
                        Thử lại từ giai đoạn đã lưu
                      </button>
                    )}
                    <p className="muted">
                      Kết quả hỗ trợ người kiểm tra; không tự phê duyệt thanh
                      toán.
                    </p>
                  </section>{" "}
                </details>

                {(selectedFinding ? [selectedFinding] : []).map((finding) => (
                  <article className="finding" key={finding.id}>
                    <div className="finding-header">
                      <span className={`severity ${finding.severity}`}>
                        {
                          { high: "Cao", medium: "Trung bình", low: "Thấp" }[
                            finding.severity
                          ]
                        }
                      </span>
                      <span className="muted">
                        {finding.scope === "cross"
                          ? "Giữa các chứng từ"
                          : "Trong một chứng từ"}
                      </span>
                    </div>
                    <h3>{finding.title}</h3>
                    <p>{finding.explanation}</p>
                    {finding.semantic_review && (
                      <details>
                        <summary>Rà soát ý nghĩa và kết luận bằng AI</summary>
                        <p>{finding.semantic_review.reason}</p>
                        <p className="muted">
                          Đây là đánh giá của AI dựa trên bằng chứng; cần đối
                          chiếu chứng từ khi quyết định thanh toán.
                        </p>
                      </details>
                    )}
                    {!!finding.verified_checks?.length && (
                      <details className="verified-checks">
                        <summary>
                          Các phép kiểm tra đã xác minh (
                          {finding.verified_checks.length})
                        </summary>
                        <ul>
                          {finding.verified_checks.map((check) => (
                            <li key={check.id}>
                              <strong>{check.purpose}</strong>
                              <p className="muted">
                                Điều kiện cần kiểm tra:{" "}
                                {proofExpression(check.left)}{" "}
                                {
                                  (
                                    {
                                      equals: "=",
                                      lte: "≤",
                                      gte: "≥",
                                    } as Record<string, string>
                                  )[check.relation]
                                }{" "}
                                {proofExpression(check.right)}
                              </p>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {!!finding.supporting_findings?.length && (
                      <details>
                        <summary>
                          Chi tiết được gộp (
                          {finding.supporting_findings.length})
                        </summary>
                        {finding.supporting_findings.map((detail, index) => (
                          <div key={index}>
                            <h4>{detail.title}</h4>
                            <p>{detail.explanation}</p>
                          </div>
                        ))}
                      </details>
                    )}
                    {!!finding.related_issues?.length && (
                      <details>
                        <summary>
                          Vấn đề liên quan ({finding.related_issues.length})
                        </summary>
                        <ul>
                          {finding.related_issues.map((related) => (
                            <li key={related.case_id}>
                              {related.title} ·{" "}
                              {related.scope === "cross"
                                ? "Đối chiếu chứng từ"
                                : "Kiểm tra nội bộ"}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    <div className="evidence-list">
                      {finding.observation_ids.map(
                        (ref) =>
                          byId[ref] && (
                            <button
                              key={ref}
                              onClick={() => void openEvidence(byId[ref])}
                            >
                              <span>
                                {
                                  roles[
                                    audit.documents.find(
                                      (d) => d.id === byId[ref].document_id,
                                    )!.role
                                  ]
                                }{" "}
                                · Trang {byId[ref].page_id.split(":p")[1]}
                              </span>
                              <strong>
                                {fields[byId[ref].field_key] ||
                                  byId[ref].field_key}
                                : {byId[ref].raw_value}
                              </strong>
                            </button>
                          ),
                      )}
                    </div>
                    {calculations(finding).map((calc) => (
                      <div className="calculation" key={calc.id}>
                        {calc.unit === "identity" ? (
                          `Đối chiếu chính xác: ${calc.comparison?.status === "pass" ? "Khớp" : "Không khớp"}`
                        ) : (
                          <>
                            Kết quả tính: {calc.result} {calc.unit}{" "}
                          </>
                        )}
                        {calc.comparison?.difference != null &&
                          `· Chênh lệch ${calc.comparison.difference}`}
                      </div>
                    ))}
                    {finding.policy_refs.length > 0 && (
                      <small className="muted">
                        Cơ sở chính sách demo: {finding.policy_refs.join(", ")}
                      </small>
                    )}
                  </article>
                ))}
                {!findings.length && (
                  <p className="empty-state">
                    {!stageReviewed
                      ? "Bước này chưa hoàn tất; chưa đủ dữ liệu để kết luận."
                      : stageUnresolved.length
                        ? "Chưa phát hiện vấn đề, nhưng vẫn còn nội dung cần xác nhận."
                        : "Chưa phát hiện vấn đề trong phạm vi đã kiểm tra ở bước này."}
                  </p>
                )}
                {!!stageUnresolved.length && (
                  <div className="unresolved">
                    <h3>Những nội dung chưa thể kết luận</h3>
                    <ul>
                      {stageUnresolved.map((check, i) => (
                        <li key={i}>{check}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {isCrossAudit && !!audit.report.cross?.links?.length && (
                  <details>
                    <summary>Liên kết chứng từ</summary>
                    {audit.report.cross.links.map((link, i) => (
                      <p key={i}>
                        {link.status === "supported" ? "✓" : "⚠"}{" "}
                        {link.explanation}
                      </p>
                    ))}
                  </details>
                )}
              </section>
            )}
          </section>
          {isAuditStage ? (
            <RelatedDocuments
              auditId={id}
              finding={selectedFinding}
              observations={observations}
              focused={evidence}
            />
          ) : (
            <aside className="panel document-viewer">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">ĐỐI CHIẾU NGUỒN</span>
                  <h3>Chứng từ nguồn</h3>
                </div>
                {doc && (
                  <select
                    aria-label="Trang chứng từ"
                    value={page}
                    onChange={(e) => {
                      setPage(Number(e.target.value));
                      setEvidence(null);
                    }}
                  >
                    {doc.pages.map((p) => (
                      <option value={p.number} key={p.id}>
                        Trang {p.number}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <select
                aria-label="Chọn chứng từ nguồn"
                value={doc?.id || ""}
                onChange={(event) => void openDocument(event.target.value)}
              >
                <option value="" disabled>
                  Chọn chứng từ
                </option>
                {audit.documents.map((document, index) => (
                  <option key={document.id} value={document.id}>
                    {roles[document.role] || `Chứng từ ${index + 1}`}
                  </option>
                ))}
              </select>
              {doc ? (
                <>
                  <p>{roles[doc.role]}</p>
                  {doc.pages.find((p) => p.number === page) && (
                    <a
                      href={
                        doc.pages.find((p) => p.number === page)!.preview_url
                      }
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        className="page-preview"
                        onLoad={() => {
                          if (pendingSourceScroll.current !== null) {
                            document
                              .querySelector<HTMLElement>(".document-viewer")
                              ?.scrollTo({
                                top: pendingSourceScroll.current,
                                behavior: "instant",
                              });
                            pendingSourceScroll.current = null;
                          }
                        }}
                        alt={`${roles[doc.role]} trang ${page}`}
                        src={
                          doc.pages.find((p) => p.number === page)!.preview_url
                        }
                      />
                    </a>
                  )}
                  {evidence && (
                    <blockquote>
                      <span className="eyebrow">BẰNG CHỨNG</span>
                      <p>{evidence.quote}</p>
                      <small>
                        {evidence.grounding === "text_verified"
                          ? "Đã đối chiếu với văn bản trang nguồn"
                          : "Đọc từ ảnh; chưa được xác minh độc lập"}
                      </small>
                    </blockquote>
                  )}
                  <div className="original-links">
                    {doc.files.map((file) => (
                      <a
                        key={file.id}
                        href={file.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Mở bản gốc: {file.name} ↗
                      </a>
                    ))}
                  </div>
                </>
              ) : (
                <div className="viewer-empty">
                  <FilePlaceholder />
                  <p>Chọn một giá trị hoặc bằng chứng để xem trang nguồn.</p>
                </div>
              )}
            </aside>
          )}
        </div>
      )}
      {stage === "usage" && <UsagePanel usage={audit.usage} />}
      {stage === "timing" && <TimingPanel audit={audit} />}
      <div className="stage-navigation">
        <button
          className="secondary"
          disabled={stage === "upload"}
          onClick={() =>
            changeStage(steps[steps.findIndex(([id]) => id === stage) - 1][0])
          }
        >
          ← Bước trước
        </button>
        <span>
          {steps.findIndex(([id]) => id === stage) + 1} / {steps.length}
        </span>
        <button
          className="secondary"
          disabled={stage === "timing"}
          onClick={() =>
            changeStage(steps[steps.findIndex(([id]) => id === stage) + 1][0])
          }
        >
          Bước tiếp →
        </button>
      </div>
    </>
  );
}
function FilePlaceholder() {
  return (
    <svg width="50" height="60" viewBox="0 0 50 60" fill="none">
      <path d="M8 2h23l11 11v43H8V2Z" stroke="currentColor" strokeWidth="2" />
      <path
        d="M17 25h16M17 33h16M17 41h10"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}

import { useState } from "react";
import type { Usage } from "../../shared/types";
import { duration } from "./TimingPanel";

const stageLabels: Record<string, string> = {
  extraction: "Trích xuất",
  extraction_quality: "Rà soát nguồn trích xuất",
  extraction_quality_repair: "Sửa kết quả rà soát nguồn",
  extraction_semantics: "Diễn giải vai trò và điều khoản từ nguồn",
  extraction_semantics_repair: "Sửa diễn giải nguồn",
  audit_plan_internal: "Lập phép tính trong chứng từ",
  audit_findings_internal: "Kiểm tra trong chứng từ",
  audit_meaning_internal: "Xác minh ý nghĩa và kết luận trong chứng từ",
  audit_relationships: "Liên kết chứng từ",
  audit_plan_cross: "Lập phép tính đối chiếu",
  audit_findings_cross: "Đối chiếu giữa chứng từ",
  audit_meaning_cross: "Xác minh ý nghĩa và kết luận đối chiếu",
  audit_identity_plan: "Lập đối chiếu thông tin định danh",
  audit_identity_findings: "Đối chiếu thông tin định danh",
  audit_identity_meaning: "Xác minh kết luận về thông tin định danh",
};
const statusLabels: Record<string, string> = {
  completed: "Thành công",
  failed: "Thất bại",
  running: "Đang gọi",
  pending: "Đang chờ",
};

function stageLabel(stage: string) {
  const suffix = "_refinement";
  if (stage.endsWith(suffix)) {
    const original = stage.slice(0, -suffix.length);
    return `${stageLabels[original] || original} · lượt sửa sau rà soát`;
  }
  return stageLabels[stage] || stage;
}

export function UsagePanel({ usage }: { usage: Usage }) {
  // Display conversion only; provider accounting remains in USD.
  const [rate, setRate] = useState("25000");
  const validRate = Number.isFinite(Number(rate)) && Number(rate) > 0;
  function usd(value: number | null) {
    return value === null ? "Chưa biết" : "$" + value.toFixed(5);
  }
  function vnd(value: number | null) {
    return value === null || !validRate
      ? "Chưa biết"
      : (value * Number(rate)).toLocaleString("vi-VN", {
          maximumFractionDigits: 2,
        }) + " ₫";
  }
  return (
    <section id="usage" className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">BƯỚC 05 · CLOUDFLARE WORKERS AI</span>
          <h2>Sử dụng API & chi phí</h2>
        </div>
        <span className="tag">Chi phí ước tính</span>
      </div>
      <div className="metrics">
        <div>
          <span>Chi phí USD đã biết</span>
          <strong>{usd(usage.estimated_usd)}</strong>
        </div>
        <div>
          <span>Quy đổi VND đã biết</span>
          <strong>{vnd(usage.estimated_usd)}</strong>
        </div>
        <div>
          <span>Số lượt gọi</span>
          <strong>{usage.call_count}</strong>
        </div>
        <div>
          <span>Token vào / ra đã biết</span>
          <strong>
            {usage.prompt_tokens.toLocaleString("vi-VN")} /{" "}
            {usage.completion_tokens.toLocaleString("vi-VN")}
          </strong>
        </div>
      </div>
      <label className="exchange-rate">
        Tỷ giá quy đổi (VND / USD)
        <input
          type="number"
          min="1"
          step="any"
          value={rate}
          onChange={(event) => setRate(event.target.value)}
        />
      </label>
      <p className="muted">
        Mặc định 25.000 VND/USD là tỷ giá minh họa, không phải tỷ giá trực tiếp.
        Có thể thay đổi để quy đổi tất cả chi phí bên dưới.
      </p>
      {!validRate && (
        <p role="alert" className="alert">
          Nhập tỷ giá lớn hơn 0 để xem chi phí VND.
        </p>
      )}
      <p className="muted">
        Đây là giá trị ước tính theo bảng giá, không phải số tiền đã thu. Phí
        thực tế và hạn mức còn lại của tài khoản chưa được xác minh.
      </p>
      {usage.unknown_usage_calls > 0 && (
        <p role="status" className="alert">
          {usage.unknown_usage_calls} lượt gọi chưa có dữ liệu usage; tổng ở
          trên chưa đầy đủ.
        </p>
      )}
      <h3 className="subheading">Chi phí theo giai đoạn</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Giai đoạn</th>
              <th>Lượt gọi</th>
              <th>USD ước tính</th>
              <th>VND quy đổi</th>
            </tr>
          </thead>
          <tbody>
            {usage.stages?.map((stage) => (
              <tr key={stage.stage}>
                <td>{stageLabel(stage.stage)}</td>
                <td>{stage.call_count}</td>
                <td>
                  {usd(stage.estimated_usd)}
                  {stage.unknown_usage_calls > 0 && (
                    <small>Chưa đầy đủ usage</small>
                  )}
                </td>
                <td>{vnd(stage.estimated_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Nhật ký từng lượt gọi API · {usage.call_count} lượt</summary>
        <p className="muted">Bảng giá: {usage.pricing_version}</p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Giai đoạn / model</th>
                <th>Trạng thái</th>
                <th>Token vào / ra</th>
                <th>Độ trễ</th>
                <th>USD ước tính</th>
                <th>VND quy đổi</th>
              </tr>
            </thead>
            <tbody>
              {usage.calls.map((call) => (
                <tr key={call.id}>
                  <td>
                    {stageLabel(call.stage)}
                    <small>
                      {call.model} · lần {call.attempt}
                    </small>
                  </td>
                  <td>{statusLabels[call.status] || call.status}</td>
                  <td>
                    {call.prompt_tokens ?? "Chưa biết"} /{" "}
                    {call.completion_tokens ?? "Chưa biết"}
                  </td>
                  <td>{duration(call.latency_ms)}</td>
                  <td>{usd(call.estimated_usd)}</td>
                  <td>{vnd(call.estimated_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

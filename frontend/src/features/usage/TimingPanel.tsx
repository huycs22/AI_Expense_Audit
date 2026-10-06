import { useEffect, useState } from "react";
import type { Audit } from "../../shared/types";

export function duration(ms: number | null) {
  if (ms === null || !Number.isFinite(ms)) return "Chưa biết";
  const seconds = Math.max(0, ms / 1000);
  return seconds >= 60
    ? `${Math.floor(seconds / 60)} phút ${(seconds % 60).toFixed(1)} giây`
    : `${seconds.toFixed(1)} giây`;
}

export function TimingPanel({ audit }: { audit: Audit }) {
  const [now, setNow] = useState(Date.now());
  const running = ["queued", "processing"].includes(audit.status);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const elapsed =
    (running ? now : Date.parse(audit.updated_at)) -
    Date.parse(audit.created_at);
  const measured = audit.usage.calls.filter((call) => call.latency_ms !== null);
  const total = measured.reduce((sum, call) => sum + call.latency_ms!, 0);
  return (
    <section id="timing" className="panel">
      <span className="eyebrow">BƯỚC 06 · THỜI GIAN</span>
      <h2>Thời gian & độ trễ hệ thống</h2>
      <div className="metrics">
        <div>
          <span>{running ? "Đã chạy" : "Từ lúc tạo đến cập nhật cuối"}</span>
          <strong>{duration(elapsed)}</strong>
        </div>
        <div>
          <span>Tổng độ trễ API đã ghi nhận</span>
          <strong>{measured.length ? duration(total) : "Chưa biết"}</strong>
        </div>
        <div>
          <span>Trung bình mỗi lượt gọi</span>
          <strong>
            {duration(measured.length ? total / measured.length : null)}
          </strong>
        </div>
        <div>
          <span>Lượt gọi chậm nhất</span>
          <strong>
            {duration(
              measured.length
                ? Math.max(...measured.map((call) => call.latency_ms!))
                : null,
            )}
          </strong>
        </div>
      </div>
      <p className="muted">
        Các lượt gọi có thể chạy song song, nên tổng độ trễ API không bằng thời
        gian xử lý hồ sơ. Khoảng từ lúc tạo đến cập nhật cuối bao gồm thời gian
        chờ và các lần thử lại.
      </p>
      {measured.length < audit.usage.call_count && (
        <p className="alert">Một số lượt gọi chưa có dữ liệu thời gian.</p>
      )}
      <p className="muted">
        Tạo hồ sơ: {new Date(audit.created_at).toLocaleString("vi-VN")} · Cập
        nhật cuối: {new Date(audit.updated_at).toLocaleString("vi-VN")}
      </p>
    </section>
  );
}

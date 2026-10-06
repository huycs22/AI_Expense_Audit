import { useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  FileText,
  UploadCloud,
  X,
} from "lucide-react";
import { api } from "../../shared/api";
import { roles } from "../../shared/labels";
import type { Role } from "../../shared/types";

const orderedRoles: Role[] = ["purchase_order", "invoice", "payment_request"];
export function UploadForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [files, setFiles] = useState<Record<Role, File[]>>({
    purchase_order: [],
    invoice: [],
    payment_request: [],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function choose(role: Role, selected: File[]) {
    if (
      selected.some((f) => f.type === "application/pdf") &&
      selected.length !== 1
    ) {
      setError("Mỗi chứng từ chọn một PDF hoặc nhiều ảnh.");
      return;
    }
    setFiles((previous) => ({ ...previous, [role]: selected }));
    setError("");
  }
  function move(role: Role, index: number, direction: number) {
    const next = [...files[role]];
    const target = index + direction;
    [next[index], next[target]] = [next[target], next[index]];
    setFiles((previous) => ({ ...previous, [role]: next }));
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("mode", mode);
      orderedRoles.forEach((role, index) =>
        files[role].forEach((file) =>
          body.append(mode === "auto" ? `document_${index + 1}` : role, file),
        ),
      );
      onCreated((await api.upload(body)).id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Không tải được hồ sơ");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form id="upload" onSubmit={submit} className="upload-form">
      <div className="section-heading">
        <div>
          <span className="eyebrow">BƯỚC 01 · TẢI LÊN</span>
          <h2>Ba chứng từ. Một lần kiểm tra.</h2>
          <p>Tải lên bộ hồ sơ của cùng một giao dịch để bắt đầu.</p>
        </div>
        <span className="tag">PDF · PNG · JPEG</span>
      </div>
      <fieldset className="recognition-mode">
        <legend>Cách nhận diện chứng từ</legend>
        <label>
          <input
            type="radio"
            name="recognition"
            checked={mode === "auto"}
            onChange={() => setMode("auto")}
          />{" "}
          Tự nhận diện bằng AI
        </label>
        <label>
          <input
            type="radio"
            name="recognition"
            checked={mode === "manual"}
            onChange={() => setMode("manual")}
          />{" "}
          Gán loại chứng từ
        </label>
      </fieldset>
      <p className="muted">
        AI nhận diện Đơn đặt hàng, Hóa đơn và Đề nghị thanh toán từ nội dung.
        Bạn cũng có thể gán loại chứng từ trước khi phân tích.
      </p>
      {mode === "auto" && (
        <label className="bulk-picker">
          <span className="bulk-picker-icon">
            <UploadCloud size={23} />
          </span>
          <span>
            <strong>Chọn cùng lúc ba PDF</strong>
            <small>Hoặc chọn từng chứng từ bên dưới</small>
          </span>
          <span className="bulk-picker-action">Chọn tệp ↗</span>
          <input
            aria-label="Chọn ba PDF"
            type="file"
            accept="application/pdf"
            multiple
            onChange={(event) => {
              const selected = Array.from(event.target.files || []);
              if (
                selected.length !== 3 ||
                selected.some((file) => file.type !== "application/pdf")
              ) {
                setError(
                  "Chọn đúng ba PDF; với ảnh, dùng ba nhóm trang bên dưới.",
                );
                return;
              }
              setFiles(
                Object.fromEntries(
                  orderedRoles.map((role, index) => [role, [selected[index]]]),
                ) as Record<Role, File[]>,
              );
              setError("");
            }}
          />
        </label>
      )}
      <div className="upload-grid">
        {orderedRoles.map((role, index) => (
          <section
            className={`upload-slot ${files[role].length ? "has-files" : ""}`}
            key={role}
          >
            <div className="slot-heading">
              <span className="step-number">0{index + 1}</span>
              {files[role].length ? (
                <CheckCircle2 size={23} />
              ) : (
                <FileText size={23} />
              )}
            </div>
            <h3>{mode === "auto" ? `Chứng từ ${index + 1}` : roles[role]}</h3>
            <p>
              {mode === "auto"
                ? "AI sẽ nhận diện loại từ nội dung"
                : ["Purchase Order", "Invoice", "Payment Request"][index]}
            </p>
            <label className="file-picker">
              <span className="upload-icon">
                <UploadCloud size={29} />
              </span>
              <strong>
                {files[role].length
                  ? "Chọn lại chứng từ"
                  : "Chọn file chứng từ"}
              </strong>
              <span>Một PDF hoặc ảnh PNG / JPEG theo thứ tự trang</span>
              <input
                aria-label={
                  mode === "auto" ? `Chứng từ ${index + 1}` : roles[role]
                }
                type="file"
                accept="application/pdf,image/png,image/jpeg"
                multiple
                onChange={(e) => choose(role, Array.from(e.target.files || []))}
              />
            </label>
            <ol className="selected-files">
              {files[role].map((file, i) => (
                <li key={`${file.name}-${i}`}>
                  <span title={file.name}>
                    {i + 1}. {file.name}
                  </span>
                  <button
                    type="button"
                    aria-label={`Đưa trang ${i + 1} lên`}
                    disabled={i === 0}
                    onClick={() => move(role, i, -1)}
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Đưa trang ${i + 1} xuống`}
                    disabled={i === files[role].length - 1}
                    onClick={() => move(role, i, 1)}
                  >
                    <ArrowDown size={14} />
                  </button>
                  <button
                    type="button"
                    aria-label={`Xóa ${file.name}`}
                    onClick={() =>
                      choose(
                        role,
                        files[role].filter((_, n) => n !== i),
                      )
                    }
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      {error && (
        <div role="alert" className="alert">
          {error}
        </div>
      )}
      <div className="form-footer">
        <div>
          <strong className="upload-count">
            {orderedRoles.filter((role) => files[role].length > 0).length} / 3
            chứng từ đã chọn
          </strong>
          <p>Tối đa 20 MB/file · 10 trang/chứng từ · 60 MB/hồ sơ</p>
        </div>
        <button
          className="primary"
          disabled={busy || orderedRoles.some((role) => !files[role].length)}
        >
          {busy ? "Đang chuẩn bị hồ sơ…" : "Phân tích hồ sơ"} <span>↗</span>
        </button>
      </div>
    </form>
  );
}

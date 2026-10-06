import { useEffect, useState } from "react";
import {
  ArrowRight,
  FolderClock,
  LayoutDashboard,
  ShieldCheck,
} from "lucide-react";
import { WorkflowSteps } from "./shared/WorkflowSteps";
import { api } from "./shared/api";
import type { HistoryItem } from "./shared/types";
import { UploadForm } from "./features/upload/UploadForm";
import { History } from "./features/history/History";
import { AuditView } from "./features/audits/AuditView";

export default function App() {
  const [view, setView] = useState<"overview" | "history">("overview");
  const [auditId, setAuditId] = useState(
    new URLSearchParams(location.search).get("audit"),
  );
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!auditId)
      api
        .history()
        .then(setHistory)
        .catch((e) => setError(e.message));
  }, [auditId, view]);
  function open(id: string) {
    setAuditId(id);
    window.history.pushState({}, "", `?audit=${id}`);
  }
  function back() {
    setAuditId(null);
    window.history.pushState({}, "", "/");
  }
  useEffect(() => {
    const handler = () =>
      setAuditId(new URLSearchParams(location.search).get("audit"));
    addEventListener("popstate", handler);
    return () => removeEventListener("popstate", handler);
  }, []);
  return (
    <div className="app-shell">
      <header className="app-header">
        <a href="/" className="brand">
          <span className="brand-icon">
            <ShieldCheck size={23} />
          </span>
          <span>
            Expense<span className="brand-second">Audit</span>
          </span>
        </a>
        <nav>
          <button
            className={view === "overview" && !auditId ? "active" : ""}
            onClick={() => {
              back();
              setView("overview");
            }}
          >
            <LayoutDashboard size={18} />
            Tổng quan
          </button>
          <button
            className={view === "history" && !auditId ? "active" : ""}
            onClick={() => {
              back();
              setView("history");
            }}
          >
            <FolderClock size={18} />
            Lịch sử hồ sơ
          </button>
        </nav>
      </header>
      <div className="workspace">
        <header className="topbar">
          <span>
            Không gian làm việc <ArrowRight size={13} />{" "}
            {auditId
              ? "Chi tiết hồ sơ"
              : view === "history"
                ? "Lịch sử"
                : "Tổng quan"}
          </span>
          <div className="local-badge">
            <span className="status-dot" /> Local workspace
          </div>
        </header>
        <main>
          {auditId ? (
            <AuditView key={auditId} id={auditId} onBack={back} />
          ) : (
            <>
              <div className="page-heading">
                <span className="eyebrow">AI EXPENSE AUDIT SYSTEM</span>
                <h1>
                  {view === "history"
                    ? "Lịch sử kiểm tra"
                    : "Kiểm tra trước khi thanh toán."}
                </h1>
                <p>
                  Đọc chứng từ, đối chiếu thông tin và tìm những sai lệch cần
                  xem xét.
                </p>
              </div>
              {error && (
                <div className="alert" role="alert">
                  Không kết nối được backend: {error}
                </div>
              )}
              {view === "overview" ? (
                <>
                  <WorkflowSteps />
                  <UploadForm onCreated={open} />
                  <History items={history.slice(0, 5)} onOpen={open} />
                </>
              ) : (
                <History items={history} onOpen={open} />
              )}
            </>
          )}
        </main>
        <footer>
          AI Expense Audit · Purchase Order / Invoice / Payment Request
        </footer>
      </div>
    </div>
  );
}

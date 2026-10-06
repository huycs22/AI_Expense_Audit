export const steps = [
  ["upload", "Tải lên"],
  ["extraction", "Trích xuất"],
  ["internal_audit", "Kiểm tra nội bộ"],
  ["cross_audit", "Đối chiếu chứng từ"],
  ["usage", "Chi phí & nhật ký API"],
  ["timing", "Thời gian"],
] as const;
export type WorkflowStage = (typeof steps)[number][0];

export function WorkflowSteps({
  active,
  onChange,
}: {
  active?: WorkflowStage;
  onChange?: (stage: WorkflowStage) => void;
}) {
  return (
    <nav className="workflow-steps" aria-label="Quy trình kiểm tra">
      {steps.map(([id, label], index) =>
        onChange ? (
          <button
            key={id}
            aria-current={active === id ? "step" : undefined}
            className={active === id ? "active" : ""}
            onClick={() => onChange(id)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            {label}
          </button>
        ) : (
          <span className="workflow-label" key={id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {label}
          </span>
        ),
      )}
    </nav>
  );
}

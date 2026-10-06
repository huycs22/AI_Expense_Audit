import { render, screen } from "@testing-library/react";
import { TimingPanel } from "./TimingPanel";
import type { Audit } from "../../shared/types";

test("separates wall time from cumulative API latency and excludes unknown latency", () => {
  const audit = {
    status: "completed",
    created_at: "2026-10-05T10:00:00Z",
    updated_at: "2026-10-05T10:00:10Z",
    usage: {
      call_count: 3,
      calls: [{ latency_ms: 8000 }, { latency_ms: 8000 }, { latency_ms: null }],
    },
  } as Audit;
  render(<TimingPanel audit={audit} />);
  expect(screen.getByText("10.0 giây")).toBeInTheDocument();
  expect(screen.getByText("16.0 giây")).toBeInTheDocument();
  expect(screen.getAllByText("8.0 giây")).toHaveLength(2);
  expect(screen.getByText(/chưa có dữ liệu thời gian/)).toBeInTheDocument();
});

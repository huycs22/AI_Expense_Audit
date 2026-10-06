import { fireEvent, render, screen } from "@testing-library/react";
import { UsagePanel } from "./UsagePanel";

test("separates estimated cost from billing and discloses missing usage", () => {
  render(
    <UsagePanel
      usage={{
        calls: [],
        call_count: 1,
        prompt_tokens: 0,
        completion_tokens: 0,
        estimated_usd: 0,
        estimated_neurons: 0,
        unknown_usage_calls: 1,
        pricing_version: "test",
      }}
    />,
  );
  expect(screen.getByText(/không phải số tiền đã thu/)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("chưa đầy đủ");
});

test("converts total, stage and call costs and keeps unknown costs unknown", () => {
  const { container } = render(
    <UsagePanel
      usage={{
        calls: [
          {
            id: "call",
            stage: "extraction",
            model: "test",
            status: "completed",
            attempt: 1,
            latency_ms: 1000,
            prompt_tokens: 2,
            completion_tokens: 3,
            estimated_usd: null,
            estimated_neurons: null,
          },
        ],
        stages: [
          {
            stage: "extraction",
            call_count: 1,
            estimated_usd: 0.01,
            estimated_neurons: 10,
            unknown_usage_calls: 1,
          },
        ],
        call_count: 1,
        prompt_tokens: 2,
        completion_tokens: 3,
        estimated_usd: 0.01,
        estimated_neurons: 10,
        unknown_usage_calls: 1,
        pricing_version: "test",
      }}
    />,
  );
  expect(screen.getAllByText("250 ₫")).toHaveLength(2);
  fireEvent.change(screen.getByLabelText("Tỷ giá quy đổi (VND / USD)"), {
    target: { value: "26000" },
  });
  expect(screen.getAllByText("260 ₫")).toHaveLength(2);
  expect(screen.getAllByText("Chưa biết")).toHaveLength(2);
  expect(container.textContent).not.toMatch(/Neuron/i);
  fireEvent.change(screen.getByLabelText("Tỷ giá quy đổi (VND / USD)"), {
    target: { value: "0" },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("lớn hơn 0");
});

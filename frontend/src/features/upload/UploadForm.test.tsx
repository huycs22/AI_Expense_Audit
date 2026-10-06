import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { UploadForm } from "./UploadForm";
import { api } from "../../shared/api";

test("automatic mode submits unlabeled grouped PDFs in any order", async () => {
  const upload = vi.spyOn(api, "upload").mockResolvedValue({ id: "created" });
  const created = vi.fn();
  render(<UploadForm onCreated={created} />);
  const files = ["invoice", "request", "order"].map(
    (name) => new File([name], `${name}.pdf`, { type: "application/pdf" }),
  );
  fireEvent.change(screen.getByLabelText("Chọn ba PDF"), { target: { files } });
  fireEvent.click(screen.getByRole("button", { name: /Phân tích hồ sơ/ }));
  await waitFor(() => expect(created).toHaveBeenCalledWith("created"));
  const body = upload.mock.calls[0][0];
  expect(body.get("mode")).toBe("auto");
  expect((body.get("document_1") as File).name).toBe("invoice.pdf");
  expect(body.has("purchase_order")).toBe(false);
  upload.mockRestore();
});

test("requires all three groups and preserves image ordering", () => {
  render(<UploadForm onCreated={vi.fn()} />);
  expect(
    screen.getByRole("button", { name: /Phân tích hồ sơ/ }),
  ).toBeDisabled();
  const a = new File(["a"], "a.png", { type: "image/png" });
  const b = new File(["b"], "b.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Chứng từ 1"), {
    target: { files: [a, b] },
  });
  fireEvent.click(screen.getByRole("button", { name: "Đưa trang 2 lên" }));
  expect(screen.getByText("1. b.png")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Chứng từ 2"), {
    target: { files: [a] },
  });
  fireEvent.change(screen.getByLabelText("Chứng từ 3"), {
    target: { files: [a] },
  });
  expect(screen.getByRole("button", { name: /Phân tích hồ sơ/ })).toBeEnabled();
});

test("rejects a PDF mixed with images inside one document", () => {
  render(<UploadForm onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("radio", { name: "Gán loại chứng từ" }));
  fireEvent.change(screen.getByLabelText("Đơn đặt hàng"), {
    target: {
      files: [
        new File(["p"], "a.pdf", { type: "application/pdf" }),
        new File(["i"], "a.png", { type: "image/png" }),
      ],
    },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("một PDF hoặc nhiều ảnh");
});

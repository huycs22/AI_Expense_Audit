import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Observation } from "../../shared/types";
import { ObservationValue } from "./ObservationValue";

describe("source units", () => {
  it("shows the quantity unit when normalization leaves the number unchanged", () => {
    render(
      <ObservationValue
        observation={
          {
            raw_value: "4",
            normalized_value: "4",
            unit: "boxes",
          } as Observation
        }
      />,
    );
    expect(screen.getByText("Đơn vị: boxes")).toBeInTheDocument();
    expect(screen.queryByText(/Chuẩn hóa/)).not.toBeInTheDocument();
  });
  it("shows money units independently of number formatting", () => {
    render(
      <ObservationValue
        observation={
          {
            raw_value: "2,400",
            normalized_value: "2400",
            unit: "USD",
          } as Observation
        }
      />,
    );
    expect(screen.getByText("Đơn vị: USD")).toBeInTheDocument();
    expect(screen.getByText("Chuẩn hóa: 2400")).toBeInTheDocument();
  });
});

import type { Observation } from "../../shared/types";

export function ObservationValue({
  observation,
}: {
  observation: Observation;
}) {
  const { raw_value, normalized_value, unit } = observation;
  return (
    <>
      {raw_value ?? "Không đọc được"}
      {unit && <small>Đơn vị: {unit}</small>}
      {normalized_value !== raw_value && (
        <small>Chuẩn hóa: {normalized_value ?? "Chưa rõ"}</small>
      )}
    </>
  );
}

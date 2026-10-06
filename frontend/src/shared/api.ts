import type { Audit, DocumentDetail, HistoryItem } from "./types";

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Yêu cầu thất bại (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export const api = {
  history: () => request<HistoryItem[]>("/api/audits"),
  audit: (id: string) => request<Audit>(`/api/audits/${id}`),
  document: (audit: string, doc: string) =>
    request<DocumentDetail>(`/api/audits/${audit}/documents/${doc}`),
  upload: (body: FormData) =>
    request<{ id: string }>("/api/audits", { method: "POST", body }),
  retry: (id: string) => request(`/api/audits/${id}/retry`, { method: "POST" }),
};

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../../shared/api";
import { fields, roles } from "../../shared/labels";
import type { DocumentDetail, Finding, Observation } from "../../shared/types";
import { ObservationValue } from "../extraction/ObservationValue";

export function RelatedDocuments({
  auditId,
  finding,
  observations,
  focused,
}: {
  auditId: string;
  finding: Finding | null;
  observations: Observation[];
  focused: Observation | null;
}) {
  const cache = useRef(new Map<string, DocumentDetail>());
  const previousFinding = useRef(finding?.id);
  useLayoutEffect(() => {
    if (previousFinding.current !== finding?.id) {
      document
        .querySelector(".related-documents")
        ?.scrollTo({ top: 0, behavior: "instant" });
      previousFinding.current = finding?.id;
    }
  }, [finding?.id]);
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const cited = observations.filter((observation) =>
    finding?.observation_ids.includes(observation.id),
  );
  const documentIds = [
    ...new Set(cited.map((observation) => observation.document_id)),
  ];
  const key = documentIds.join(",");
  useEffect(() => {
    let active = true;
    setLoading(true);
    setDocuments([]);
    setError("");
    Promise.all(
      documentIds.map(async (id) => {
        const cached = cache.current.get(id);
        if (cached) return cached;
        const result = await api.document(auditId, id);
        cache.current.set(id, result);
        return result;
      }),
    )
      .then((results) => {
        if (active) setDocuments(results);
      })
      .catch((exc) => {
        if (active) setError(exc.message || "Không mở được chứng từ liên quan");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // The document-ID key is stable when switching between findings on the same documents.
  }, [auditId, key]);
  useEffect(() => {
    if (!focused || loading) return;
    const card = document.getElementById(`related-${focused.page_id}`);
    if (card)
      document.querySelector(".related-documents")?.scrollTo({
        top: (card as HTMLElement).offsetTop - 12,
        behavior: "smooth",
      });
  }, [focused, loading]);
  return (
    <aside
      className="panel document-viewer related-documents"
      aria-label="Chứng từ liên quan"
    >
      <span className="eyebrow">BẰNG CHỨNG CỦA VẤN ĐỀ ĐÃ CHỌN</span>
      <h3>
        Chứng từ liên quan <span className="tag">{documentIds.length}</span>
      </h3>
      <p className="muted">
        Tự động hiển thị tất cả chứng từ và trang được trích dẫn.
      </p>
      <div className="related-shortcuts">
        {documents.map((doc) => (
          <button
            className="secondary"
            key={doc.id}
            onClick={() => {
              const card = document.getElementById(
                `related-document-${doc.id}`,
              );
              if (card)
                document
                  .querySelector(".related-documents")
                  ?.scrollTo({ top: card.offsetTop - 12, behavior: "smooth" });
            }}
          >
            {roles[doc.role]} ↓
          </button>
        ))}
      </div>
      {loading && <p role="status">Đang mở chứng từ liên quan…</p>}
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {!finding && (
        <p className="empty-state">
          Chọn một vấn đề để xem chứng từ liên quan.
        </p>
      )}
      {documents.map((doc) => {
        const sources = cited.filter(
          (observation) => observation.document_id === doc.id,
        );
        const pages = doc.pages.filter((page) =>
          sources.some((source) => source.page_id === page.id),
        );
        return (
          <article
            id={`related-document-${doc.id}`}
            className="related-document"
            key={doc.id}
            data-document-id={doc.id}
          >
            <div className="section-heading">
              <h3>{roles[doc.role]}</h3>
              <span className="tag">{pages.length} trang liên quan</span>
            </div>
            <div className="original-links">
              {doc.files.map((file) => (
                <a
                  href={file.url}
                  key={file.id}
                  target="_blank"
                  rel="noreferrer"
                >
                  {file.name} ↗
                </a>
              ))}
            </div>
            {pages.map((page) => {
              const pageSources = sources.filter(
                (source) => source.page_id === page.id,
              );
              return (
                <section
                  key={page.id}
                  id={`related-${page.id}`}
                  className={`related-page ${focused?.page_id === page.id ? "focused" : ""}`}
                >
                  <h4>Trang {page.number}</h4>
                  <div className="source-facts">
                    {pageSources.map((source) => (
                      <div
                        key={source.id}
                        className={
                          focused?.id === source.id
                            ? "selected-observation"
                            : ""
                        }
                      >
                        <span>
                          {fields[source.field_key] || source.field_key}
                        </span>
                        <strong>
                          <ObservationValue observation={source} />
                        </strong>
                      </div>
                    ))}
                  </div>
                  <a href={page.preview_url} target="_blank" rel="noreferrer">
                    <img
                      className="page-preview"
                      src={page.preview_url}
                      alt={`${roles[doc.role]} trang ${page.number}`}
                    />
                  </a>
                  {[...new Set(pageSources.map((source) => source.quote))]
                    .filter(Boolean)
                    .map((quote) => (
                      <blockquote key={quote}>
                        <p>{quote}</p>
                      </blockquote>
                    ))}
                  <small>
                    {pageSources.every(
                      (source) => source.grounding === "text_verified",
                    )
                      ? "Đã đối chiếu văn bản nguồn"
                      : "Có dữ liệu đọc từ ảnh cần xác nhận"}
                  </small>
                </section>
              );
            })}
            {!pages.length && (
              <p className="alert">
                Không tìm thấy trang nguồn được trích dẫn.
              </p>
            )}
          </article>
        );
      })}
    </aside>
  );
}

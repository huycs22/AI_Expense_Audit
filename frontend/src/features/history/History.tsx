import type { HistoryItem } from "../../shared/types";
import { assessments, statuses } from "../../shared/labels";

export function History({
  items,
  onOpen,
}: {
  items: HistoryItem[];
  onOpen: (id: string) => void;
}) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">ĐÃ LƯU TRÊN POSTGRESQL</span>
          <h2>Lịch sử hồ sơ</h2>
        </div>
        <span className="tag">{items.length} hồ sơ gần nhất</span>
      </div>
      {!items.length ? (
        <p className="empty-state">Hồ sơ đã phân tích sẽ xuất hiện tại đây.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Hồ sơ</th>
                <th>Thời gian</th>
                <th>Xử lý</th>
                <th>Đánh giá</th>
                <th>Vấn đề</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <code>{item.id.slice(0, 8)}</code>
                  </td>
                  <td>{new Date(item.created_at).toLocaleString("vi-VN")}</td>
                  <td>{statuses[item.status]}</td>
                  <td>{assessments[item.assessment]}</td>
                  <td>{item.finding_count}</td>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => onOpen(item.id)}
                    >
                      Xem hồ sơ ↗
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

# AI ENGINEER FRESHER - TECHNICAL ASSIGNMENT

## AI Expense Audit System

**Thời gian thực hiện:** 01 ngày

## Bối cảnh

Một doanh nghiệp thường xuyên phải xử lý các bộ hồ sơ đề nghị thanh toán từ nhân viên, nhà cung cấp và các phòng ban.

Mỗi bộ hồ sơ có thể bao gồm nhiều chứng từ liên quan như:

- Purchase Order
- Invoice
- Payment Request

Hiện tại nhân viên phải kiểm tra thủ công nội dung của từng chứng từ trước khi thực hiện thanh toán. Quá trình này mất nhiều thời gian và có nguy cơ bỏ sót các thông tin sai lệch.

## Yêu cầu

Xây dựng một hệ thống sử dụng AI hỗ trợ doanh nghiệp đọc, phân tích và kiểm tra bộ chứng từ trước khi thanh toán.

Hệ thống cần cho phép người dùng:

- Upload một bộ chứng từ.
- Trích xuất các thông tin cần thiết từ từng chứng từ.
- Hiển thị dữ liệu đã trích xuất.
- Kiểm tra tính hợp lệ và nhất quán của bộ chứng từ.
- Phát hiện các vấn đề hoặc bất thường có khả năng ảnh hưởng đến việc thanh toán.
- Hiển thị rõ kết quả kiểm tra để người dùng có thể xác định vấn đề nằm ở đâu.
- Lưu lại lịch sử các bộ chứng từ đã xử lý.
- Xem lại dữ liệu và kết quả của một lần xử lý trước đó.

Các chứng từ đầu vào có thể là PDF hoặc hình ảnh và có thể có nhiều trang.

## Technical Requirements

| Hạng mục | Yêu cầu |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL hoặc MySQL |
| AI | OpenAI, Gemini hoặc AI API tương đương |
| Frontend | React |

## Yêu cầu bài làm

Ứng viên tự phân tích nghiệp vụ và quyết định:

- Những thông tin nào cần được trích xuất.
- Những nội dung nào cần được kiểm tra.
- Trường hợp nào được xem là bất thường.
- Cách biểu diễn kết quả.
- Cách tổ chức và triển khai hệ thống.

Không có cấu trúc output hoặc architecture bắt buộc.

## Deliverables

Nộp Git repository bao gồm:

- Source code.
- README.md.
- `.env.example`.

README cần có đủ thông tin để setup và chạy project.

Không commit API key, password hoặc secret vào repository.

## Evaluation

| Tiêu chí | Điểm |
|---|---:|
| Phân tích và hiểu bài toán | 15 |
| Document Extraction | 20 |
| Audit / Validation Logic | 20 |
| Solution / Architecture | 15 |
| AI Integration | 10 |
| Code Quality / Maintainability | 10 |
| Performance / Optimization | 5 |
| Database / Documentation / UI | 5 |
| **Tổng** | **100** |

Việc hoàn thành nhiều chức năng không đồng nghĩa với điểm cao hơn. Bài làm được đánh giá dựa trên tính hợp lý, độ chính xác, chất lượng triển khai và khả năng giải thích các quyết định kỹ thuật.

## Dữ liệu đầu vào

Ứng viên sử dụng bộ chứng từ mẫu được cung cấp kèm đề bài. Các chứng từ là dữ liệu synthetic phục vụ tuyển dụng và không đại diện cho giao dịch thực tế.

---

*Synthetic sample - for technical assessment only*

/** Dữ liệu mẫu: 7 agent và các task TD-xx, dùng khi chưa có backend. */
import type { Agent, LogEntry, Task } from '../types';
import { mockScreenshot } from './screenshot';

const iso = (minAgo: number) => new Date(Date.now() - minAgo * 60_000).toISOString();

export const MOCK_COMPANY = 'Virtual Tech Dept';

export const MOCK_AGENTS: Agent[] = [
  { id: 'leader', name: 'Leader Nghèo', role: 'Trưởng nhóm', group: 'lead', status: 'working', activity: 'thinking', location: 'desk', taskId: 'TD-40', note: 'Chia việc sprint landing page Mộc Coffee' },
  { id: 'senior', name: 'Senior Coder', role: 'Lập trình viên chính', group: 'code', status: 'working', activity: 'typing', location: 'desk', taskId: 'TD-41', note: 'Viết section Menu và bảng giá' },
  { id: 'junior', name: 'Junior Coder', role: 'Lập trình viên', group: 'code', status: 'blocked', activity: 'thinking', location: 'desk', taskId: 'TD-42', note: 'Chờ khóa API gửi email cho form liên hệ' },
  { id: 'intern', name: 'Intern Coder', role: 'Thực tập sinh', group: 'code', status: 'working', activity: 'reading', location: 'desk', taskId: 'TD-41', note: 'Đọc code mẫu để hỗ trợ Senior' },
  { id: 'reviewer', name: 'Reviewer', role: 'Review code & bảo mật', group: 'code', status: 'idle', activity: 'idle', location: 'desk', taskId: null, note: 'Chờ PR của TD-41' },
  { id: 'designer', name: 'Designer', role: 'Thiết kế UI/UX', group: 'creative', status: 'working', activity: 'drawing', location: 'desk', taskId: 'TD-40', note: 'Vẽ mockup trang chủ, tông nâu cà phê' },
  { id: 'tester', name: 'Tester', role: 'Kiểm thử chất lượng', group: 'creative', status: 'working', activity: 'testing', location: 'desk', taskId: 'TD-43', note: 'Thử giao diện trên điện thoại' },
];

const t = (id: string, title: string, assignee: string, status: Task['status'], minAgo: number, extra: Partial<Task> = {}): Task => ({
  id,
  title,
  description: '',
  assigner: 'leader',
  assignee,
  status,
  files: [],
  screenshot: null,
  createdAt: iso(minAgo + 30),
  updatedAt: iso(minAgo),
  ...extra,
});

export const MOCK_TASKS: Task[] = [
  t('TD-36', 'Dựng khung dự án và repo', 'senior', 'done', 95, { files: ['package.json', 'index.html'] }),
  t('TD-37', 'Viết brief từ tin nhắn khách', 'leader', 'done', 80, { assigner: 'boss', files: ['docs/brief.md'] }),
  t('TD-38', 'Tối ưu ảnh hero', 'junior', 'error', 40, { description: 'Script nén ảnh báo lỗi định dạng HEIC.', files: ['scripts/compress.ts'] }),
  t('TD-39', 'Review cấu trúc thư mục', 'reviewer', 'review', 35, { files: ['docs/structure.md'] }),
  t('TD-40', 'Lập kế hoạch và mockup landing page Mộc Coffee', 'leader', 'doing', 12, {
    assigner: 'boss',
    description: 'Landing page cho quán cà phê Mộc Coffee ở Đà Lạt: hero, menu, câu chuyện quán, bản đồ, form liên hệ. Ngân sách 5 triệu.',
    files: ['docs/spec.md', 'design/home-mockup.png'],
    screenshot: mockScreenshot('Mộc Coffee', '#7b4b2a'),
  }),
  t('TD-41', 'Code section Menu và bảng giá', 'senior', 'doing', 8, {
    description: 'Hiển thị 12 món theo 3 nhóm, giá VND, ảnh nhỏ, responsive 2 cột trên điện thoại.',
    files: ['src/sections/Menu.tsx', 'src/data/menu.json'],
  }),
  t('TD-42', 'Tích hợp form liên hệ', 'junior', 'blocked', 6, {
    description: 'Form gửi email cho chủ quán. Đang chặn: chưa có khóa API dịch vụ gửi email.',
    files: ['src/sections/Contact.tsx'],
  }),
  t('TD-43', 'Kiểm thử giao diện trên di động', 'tester', 'doing', 3, {
    description: 'Thử trên màn hình 360px, 414px và tablet; kiểm tra menu dính, nút gọi điện, tốc độ tải.',
    files: ['qa/mobile-report.md'],
    screenshot: mockScreenshot('Kiểm thử 360px', '#2fb5b0'),
  }),
  t('TD-44', 'Viết nội dung SEO cho trang chủ', 'intern', 'todo', 2),
  t('TD-45', 'Thêm bản đồ Google Maps', 'junior', 'todo', 1),
];

export const MOCK_LOG: LogEntry[] = [
  { id: 'l1', ts: iso(30), agentId: 'leader', taskId: 'TD-37', kind: 'done', text: 'Hoàn thành brief cho Mộc Coffee' },
  { id: 'l2', ts: iso(14), agentId: 'leader', taskId: 'TD-40', kind: 'assign', text: 'Nhận TD-40 từ sếp' },
  { id: 'l3', ts: iso(12), agentId: 'designer', taskId: 'TD-40', kind: 'start', text: 'Bắt đầu vẽ mockup trang chủ' },
  { id: 'l4', ts: iso(8), agentId: 'senior', taskId: 'TD-41', kind: 'start', text: 'Bắt đầu code section Menu' },
  { id: 'l5', ts: iso(6), agentId: 'junior', taskId: 'TD-42', kind: 'blocked', text: 'TD-42 bị chặn: thiếu khóa API gửi email' },
  { id: 'l6', ts: iso(4), agentId: 'junior', taskId: 'TD-38', kind: 'error', text: 'TD-38 lỗi: script nén ảnh không đọc được HEIC' },
  { id: 'l7', ts: iso(3), agentId: 'tester', taskId: 'TD-43', kind: 'start', text: 'TD-43 đang kiểm thử trên 360px' },
];

# 电网智能运维助手 · 前端工作台

基于 **React 18 + TypeScript + Vite + Ant Design** 的运维工作台，替代原 `index.html` 单页 Demo。

## 快速开始

```bash
cd web
npm install
npm run dev        # 开发（http://localhost:5173）
npm run build      # 生产构建（产物在 dist/）
npm run preview    # 预览生产构建
```

## 演示模式 vs 真实后端

默认运行在**演示模式**（内置 mock 数据），无需后端即可浏览全部页面与交互。

切换真实后端（需先启动后端 `localhost:8000`）：

编辑 `src/config.ts`：

```ts
export const USE_MOCK = false;
```

保存后 Vite 自动热更新。开发环境已配置 `/api` 代理到 `http://localhost:8000`，无需处理 CORS。

## 演示账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| admin | admin123 | 管理员 | 全部权限（含运行链路、运行指标） |
| operator | operator123 | 运维 | 对话、诊断、缺陷评估、出工单草稿 |
| monitor | monitor123 | 监控 | 只读浏览 |
| manager | manager123 | 管理 | 审核复盘案例、确认工单 |

## 页面清单

| 路由 | 页面 | 说明 |
|------|------|------|
| `/workbench` | 对话工作台 | SSE 流式对话、设备选择、工单二次确认、证据溯源 |
| `/devices` | 设备管理 | 列表 + 详情（台账/实时量测/状态四态/告警，5s 轮询） |
| `/alarms` | 告警管理 | 列表 + 等级判定 |
| `/defects` | 缺陷管理 | 列表 + 分级评估 |
| `/workorders` | 工单管理 | 列表 + 草稿确认/取消 |
| `/runs` | 运行链路 | 步骤时间线（admin） |
| `/knowledge` | 知识库 | 检索 + 文档列表 + 重新入库（admin） |
| `/review-cases` | 复盘案例 | 列表 + 审核/驳回/废止（manager/admin） |
| `/health` | 系统健康 | 组件状态 |
| `/metrics` | 运行指标 | 评估指标 + 历史评测（admin） |
| `/tools` | 工具注册 | 工具表 |
| `/settings` | 设置 | 账户/环境信息 |

## 目录结构

```
web/
├── src/
│   ├── api/           # API 封装（真实接口 + mock 切换 + SSE 流式解析）
│   ├── components/    # AppShell、RequireAuth、通用 badge
│   ├── mocks/         # mock 数据（字段严格对齐后端返回）
│   ├── pages/         # 12 个页面
│   ├── store/         # Zustand 全局状态
│   ├── styles/        # 全局样式（复用原 Demo 配色 token）
│   ├── types/         # 类型定义（对齐后端）
│   ├── utils/         # 权限矩阵
│   ├── App.tsx        # 路由
│   └── main.tsx       # 入口（AntD ConfigProvider + QueryClient）
├── vite.config.ts     # 别名 @ + /api 代理
└── index.html
```

## 设计要点（对齐 docs/前端工作台设计.md）

- **首屏是工作台不是聊天框**：设备选择器 + 任务型对话。
- **所有 Agent 结论可追溯**：`final_answer` 的 `sources`/`verification` 可视化。
- **写操作二次确认**：工单草稿展示等级/设备/消缺时限，确认才落库。
- **权限显隐**：无权限按钮禁用并显示所需角色（如「需要 admin 权限」），安全靠后端。
- **链路默认摘要、细节展开**：运行链路用 Timeline + Collapse。

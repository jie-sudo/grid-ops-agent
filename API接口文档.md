# 电网智能运维助手 Agent 平台 · API 接口文档

> 供前端工程师对接使用。所有接口基于 FastAPI，Swagger 文档见 `http://localhost:8000/docs`。

## 一、通用约定

### Base URL

```
http://localhost:8000/api/v1
```

### 认证

- 登录后获取 JWT token，除 `/health` 和 `/auth/login` 外，所有接口需带请求头：

```
Authorization: Bearer <token>
```

- 未认证返回 `401`；权限不足返回 `403`。
- 角色：`admin` / `operator` / `monitor` / `manager`。

### 统一返回结构

```json
{ "code": 0, "message": "ok", "data": { ... } }
```

- `code`: 0 成功；非 0 失败（400 参数错误 / 401 未认证 / 403 无权限 / 404 不存在 / 429 限流 / 500 内部错误 / 504 上游超时）。

### 默认账号（演示）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |
| operator | operator123 | 运维 |
| monitor | monitor123 | 监控 |
| manager | manager123 | 管理 |

---

## 二、接口清单

### 1. 登录

**POST /auth/login**

请求：
```json
{ "username": "admin", "password": "admin123" }
```

返回：
```json
{ "code": 0, "message": "ok", "data": { "token": "eyJ...", "user_id": "U0001", "role": "admin" } }
```

### 2. 对话（同步）

**POST /chat**

请求：
```json
{ "message": "变压器的缺陷分级有哪几级", "session_id": "sxxx（可选）" }
```

返回（三种 type）：
```json
{ "code": 0, "data": { "session_id": "sxxx", "type": "final_answer", "answer": "...", "sources": ["..."] } }
{ "code": 0, "data": { "type": "clarify", "question": "请提供设备编号..." } }
{ "code": 0, "data": { "type": "confirm_required", "preview": { "content": "...", "level": "危急", "deadline": "..." }, "message": "请确认是否落库" } }
```

### 3. 对话（流式 SSE）

**POST /chat/stream**

请求同 `/chat`。返回 `text/event-stream`，逐条推送事件：

```
data: {"type":"session","session_id":"sxxx"}
data: {"type":"intent","intent":"故障诊断","confidence":0.9}
data: {"type":"tool_call","tool":"query_device","params":{...}}
data: {"type":"tool_result","tool":"query_device","result":{...}}
data: {"type":"degraded","tool":"diagnose","reason":"..."}
data: {"type":"clarify","question":"..."}
data: {"type":"confirm_required","preview":{...},"message":"..."}
data: {"type":"final_answer","answer":"...","sources":[...]}
```

前端逐条 `JSON.parse(data)` 后按 `type` 分发渲染。

### 4. 会话列表

**GET /sessions**

返回当前用户的历史会话：
```json
{ "code": 0, "data": { "sessions": [ { "session_id": "sxxx", "intent": "问答", "created_at": "..." } ], "count": 1 } }
```

### 5. 设备列表（模糊搜索）

**GET /devices?keyword=城西站&limit=50**

返回：
```json
{ "code": 0, "data": { "devices": [ { "device_id": "DEV000001", "device_name": "城西站开关柜0001", "device_type": "开关柜", "station": "城西站", "status": "运行" } ], "count": 1 } }
```

### 6. 设备台账

**GET /devices/{device_id}**

返回：
```json
{ "code": 0, "data": { "found": true, "device": { "device_id": "DEV000001", "device_name": "...", "device_type": "开关柜", "voltage_level": "35kV", "station": "城西站", "status": "运行" } } }
```

### 7. 设备量测

**GET /devices/{device_id}/measurements?measure_type=温度&hours=24**

返回：
```json
{ "code": 0, "data": { "values": [ { "point_id": "PT...", "ts": "...", "value": 60.5, "quality": "正常" } ], "count": 1 } }
```

### 8. 设备状态评价

**GET /devices/{device_id}/state**

返回：
```json
{ "code": 0, "data": { "found": true, "state": "正常", "basis": [ "局放=30.7pC，上限=100pC，越限比例=-69%" ] } }
```

### 9. 告警列表

**GET /alarms?device_id=DEV000001&hours=24**

返回：
```json
{ "code": 0, "data": { "alarms": [ { "alarm_id": "AL...", "device_id": "...", "alarm_type": "过温", "level": "重要", "trigger_time": "...", "status": "活动" } ], "count": 1 } }
```

### 10. 告警等级判定

**POST /alarms/analyze**

请求：
```json
{ "alarm_type": "过温", "over_ratio": 0.6 }
```

返回：
```json
{ "code": 0, "data": { "level": "紧急", "basis": "类型[过温]，越限比例=60%" } }
```

### 11. 缺陷列表

**GET /defects**

返回：
```json
{ "code": 0, "data": { "defects": [ { "defect_id": "DF...", "device_id": "...", "description": "...", "level": "严重", "status": "待处理", "source": "巡检" } ], "count": 1 } }
```

### 12. 缺陷分级

**POST /defects/evaluate**

请求：
```json
{ "description": "套管闪络了" }
```

返回（无法确定时 `degraded=true`、`level=null`）：
```json
{ "code": 0, "data": { "level": "危急", "reasons": [ "命中关键词[闪络]" ], "degraded": false } }
```

### 13. 消缺时限

**GET /defects/deadline/{level}**（level：一般/严重/危急）

返回：
```json
{ "code": 0, "data": { "hours": 24, "label": "24 小时内消除" } }
```

### 14. 故障诊断

**POST /diagnoses**

请求：
```json
{ "device_type": "开关柜", "measurements": { "局放": 150, "温度": 90 } }
```

返回：
```json
{ "code": 0, "data": { "fault_type": "局放超标", "confidence": 0.75, "basis": [ "局放=150pC，上限=100pC" ], "degraded": false, "reason": null } }
```

### 15. 工单列表

**GET /workorders**

返回：
```json
{ "code": 0, "data": { "workorders": [ { "order_id": "WO...", "ref_type": "缺陷", "ref_id": "DEV000001", "content": "...", "level": "危急", "status": "已下发", "assignee": null, "deadline": "..." } ], "count": 1 } }
```

### 16. 工单草稿

**POST /workorders/draft**

请求：
```json
{ "defect_level": "危急", "content": "变压器油温严重超标", "device_id": "DEV000001", "assignee": "张三" }
```

返回：
```json
{ "code": 0, "data": { "draft": { "ref_type": "缺陷", "content": "...", "level": "危急", "deadline": "...", "status": "草稿" }, "message": "工单草稿已生成，待二次确认后落库" } }
```

> 说明：真正的落库走对话流程的二次确认（`/chat` 里回复"确认"），不提供直接落库接口。

### 17. 知识库文档列表

**GET /knowledge/docs**

返回：
```json
{ "code": 0, "data": { "docs": [ { "title": "配电网设备缺陷分类与分级标准（摘编）", "source": "Q/GDW 745-2012 / Q/GDW 1519-2014", "status": "active", "superseded_by": "" } ], "count": 34 } }
```

### 18. 知识检索

**GET /knowledge/search?question=危急缺陷消缺时限&top_k=5**

返回：
```json
{ "code": 0, "data": { "chunks": [ { "content": "...", "source": "Q/GDW 745-2012", "title": "...", "device_domain": "通用", "status": "active" } ], "count": 1 } }
```

### 19. 工具注册表

**GET /tools**

返回：
```json
{ "code": 0, "data": { "tools": [ { "name": "query_device", "description": "按设备编号查询台账", "params": { "device_id": "str" }, "read_only": true } ], "count": 11 } }
```

### 20. 运行链路（追溯，仅 admin）

**GET /traces/{session_id}**

返回：
```json
{ "code": 0, "data": { "session_id": "sxxx", "traces": [ { "step": 1, "tool": "query_device", "params": {...}, "result": {...}, "sources": [...], "elapsed_ms": 20, "degraded": false } ] } }
```

### 21. 健康检查（无需认证）

**GET /health**

返回：
```json
{ "code": 0, "data": { "status": "up", "dependencies": { "postgres": "ok", "chromadb": "ok", "redis": "ok" } } }
```

---

## 三、前端对接要点

1. **先登录拿 token**，之后所有请求带 `Authorization: Bearer <token>`。
2. **对话用 `/chat/stream`**（SSE），逐事件渲染；`confirm_required` 时弹确认框，用户回复"确认/取消"走 `/chat` 或 `/chat/stream`。
3. **设备选择器用 `/devices?keyword=`** 搜索，选中后前端把设备编号拼进消息（如"设备 DEV000001：温度多少"）。
4. **运行链路页面**用 `/traces/{session_id}`（需 admin），展示步骤时间线。
5. **字段说明**：缺陷/工单的 `level` 三值 `一般/严重/危急`；设备状态 `运行/停运/检修/备用`；量测 `quality` 四值 `正常/越限/缺失/无效`。

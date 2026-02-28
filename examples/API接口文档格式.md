# API 接口文档

> 记录当前应用提供的所有 API 接口，包含 URL、方法、入参、返回值和调用示例。
> 每步开发新增接口时同步更新本文档。

**Base URL**：`http://localhost:3000`（本地开发）

**CORS 配置**：<说明 CORS 配置>

**错误响应规范**：<说明统一错误格式>

---

## 一、<模块名称>

### <METHOD> <路径>

<接口功能描述>

**请求头**：
```
Content-Type: application/json
Cookie: <认证Cookie，如需要>
```

**请求体**：（POST/PUT 接口）
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| field1 | string | ✅ | 字段说明 |
| field2 | number | ❌ | 字段说明，默认值 X |

**Query 参数**：（GET 接口如有）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| param1 | string | ❌ | 参数说明 |

**路径参数**：（如有）

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 资源标识 |

**成功返回**（HTTP <状态码>）：
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

**失败场景**：

| HTTP 状态码 | code | 触发条件 |
|------------|------|----------|
| 400 | `BAD_REQUEST` | 参数错误描述 |
| 401 | `UNAUTHORIZED` | 未登录或会话过期 |
| 404 | `NOT_FOUND` | 资源不存在 |

**curl 示例**：
```bash
curl -X POST http://localhost:3000/api/xxx \
  -H "Content-Type: application/json" \
  -b tmp/cookies.txt \
  -d '{"field1":"value1"}'
```

---

## 二、<模块名称>

...
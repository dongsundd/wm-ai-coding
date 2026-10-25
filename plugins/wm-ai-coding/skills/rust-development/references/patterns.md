# Rust 设计模式速查

本文件为 OpenSpec `languages-rust/spec.md` 中 9 条 HARD-GATE 规则提供**可复用代码模板**。每个模式包含：适用场景、错误示例、正确示例。

---

## 1. 错误处理模式（对应 Requirement 1, 9）

### 适用场景

任何 lib 代码中的 Result 处理、错误传播、上下文附加。

### 错误示例 ❌

```rust
// ❌ .unwrap() 在 lib 代码中 = panic 风险
pub fn get_profile(id: i32) -> Profile {
    let row = sqlx::query_as::<_, Profile>("SELECT * FROM profile WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await
        .unwrap();  // panic if row not found or DB error
    row
}

// ❌ Result<T, String> 丢失错误类型
pub fn get_profile(id: i32) -> Result<Profile, String> {
    // ...
}
```

### 正确示例 ✅

```rust
// ✅ ? 传播 + with_context 附加上下文
pub async fn get_profile(db: &Database, id: i32) -> Result<Profile, AppError> {
    let row = sqlx::query_as::<_, Profile>("SELECT * FROM profile WHERE id = $1")
        .bind(id)
        .fetch_optional(db.pool())
        .await
        .with_context("查询档案失败")?
        .ok_or_else(|| AppError::NotFound(format!("档案 {} 不存在", id)))?;
    Ok(row)
}
```

### 关键点

- `?` 自动转换错误类型（需 `From` impl）
- `.with_context()` 添加调试信息，错误时记录日志
- `AppError::NotFound` / `AppError::Internal` / `AppError::Request` 等是结构化错误

---

## 2. 事务模式（对应 Requirement 2）

### 适用场景

多 INSERT/UPDATE 操作、跨表写入、需要原子性的写操作。

### 错误示例 ❌

```rust
// ❌ 直接用 pool 写多次 = 部分写入风险
async fn create_user_with_profile(db: &Database, user: User, profile: Profile) -> Result<i32, AppError> {
    let user_id = sqlx::query_scalar::<_, i32>("INSERT INTO users ... RETURNING id")
        .fetch_one(db.pool())
        .await?;
    let profile_id = sqlx::query_scalar::<_, i32>("INSERT INTO profiles ... RETURNING id")
        .bind(user_id)
        .fetch_one(db.pool())
        .await?;
    // 如果第二条失败，user 已写入但 profile 未写入 = 数据不一致
    Ok(profile_id)
}

// ❌ let _ = tx.commit() 静默错误
let _ = tx.commit().await;  // 不知道 commit 是否成功
```

### 正确示例 ✅

```rust
// ✅ 显式 begin + commit，自动 rollback
async fn create_user_with_profile(db: &Database, user: User, profile: Profile) -> Result<i32, AppError> {
    let mut tx = db.pool().begin().await
        .with_context("开始事务失败")?;

    let user_id = sqlx::query_scalar::<_, i32>(
        "INSERT INTO users (name) VALUES ($1) RETURNING id"
    )
    .bind(&user.name)
    .fetch_one(&mut *tx)
    .await
    .with_context("插入 user 失败")?;

    let profile_id = sqlx::query_scalar::<_, i32>(
        "INSERT INTO profiles (user_id, bio) VALUES ($1, $2) RETURNING id"
    )
    .bind(user_id)
    .bind(&profile.bio)
    .fetch_one(&mut *tx)
    .await
    .with_context("插入 profile 失败")?;

    tx.commit().await
        .with_context("提交事务失败")?;
    // tx 在 commit 失败时自动 drop，触发 rollback
    Ok(profile_id)
}
```

### 关键点

- `pool.begin()` 返回 `Transaction`，持有期间操作在同一连接
- `tx` 在 `commit()` 失败或被 drop 时自动 rollback
- `?` 在事务内任何位置失败都会让 `tx` drop，触发自动回滚

---

## 3. 查询参数化模式（对应 Requirement 3, 4, 5）

### 适用场景

所有用户输入、动态值、SQL 拼接场景。

### 错误示例 ❌

```rust
// ❌ 字符串插值 = SQL 注入风险
let name = user_input;
let sql = format!("SELECT * FROM profile WHERE name = '{}'", name);

// ❌ LIMIT/OFFSET 数字直接拼接
let sql = format!("SELECT * FROM profile LIMIT {} OFFSET {}", limit, offset);

// ❌ INTERVAL '$N days' 中 $N 在单引号内 = 不被识别
let sql = format!("SELECT * FROM profile WHERE created_at >= NOW() - INTERVAL '{} days'", days);
```

### 正确示例 ✅

```rust
// ✅ $N 占位符 + .bind()
let name = user_input;
let row = sqlx::query_as::<_, Profile>(
    "SELECT * FROM profile WHERE name = $1"
)
.bind(name)
.fetch_one(pool)
.await?;

// ✅ LIMIT/OFFSET 参数化
let rows = sqlx::query_as::<_, Profile>(
    "SELECT * FROM profile ORDER BY id LIMIT $1 OFFSET $2"
)
.bind(limit)  // bind i64
.bind(offset)
.fetch_all(pool)
.await?;

// ✅ make_interval 函数
let rows = sqlx::query_as::<_, Profile>(
    "SELECT * FROM profile WHERE created_at >= NOW() - make_interval(days => $1)"
)
.bind(days)
.fetch_all(pool)
.await?;
```

### 关键点

- `$1, $2, ...` 占位符由 sqlx 替换为参数化查询
- `LIMIT $N OFFSET $M` 中的 N、M 也是参数
- `make_interval(days => $1)` 是 PostgreSQL 函数，`$1` 在函数参数位置被识别

---

## 4. NULL 安全模式（对应 Requirement 6）

### 适用场景

访问数据库列时，尤其是 nullable 列（无 NOT NULL 约束的列）。

### 错误示例 ❌

```rust
// ❌ 假设 bio 列有值，但实际可能是 NULL = panic
let bio: String = row.get("bio");
// error: ColumnDecode: Cannot decode none to String
```

### 正确示例 ✅

```rust
// ✅ 用 try_get + unwrap_or_default
let bio: String = row.try_get::<String, _>("bio").unwrap_or_default();

// ✅ 用 Option<T>（业务需要感知 None 时）
let bio: Option<String> = row.try_get::<Option<String>, _>("bio").ok().flatten();
// 或更简洁：
let bio: Option<String> = row.get("bio");
```

### 判断方法

查 SQL migration 文件：
- `bio TEXT NOT NULL` → 用 `row.get("bio")` 直接拿 String
- `bio TEXT`（无 NOT NULL）→ 用 `try_get + unwrap_or_default` 或 `Option<T>`

---

## 5. 文档注释模式（对应 Requirement 7）

### 适用场景

所有 `pub` 项（fn / async fn / struct / enum / trait / mod.rs）

### 错误示例 ❌

```rust
// ❌ 无注释
pub fn calculate_score(profile: &Profile) -> i32 {
    // ...
}
```

### 正确示例 ✅

```rust
// ✅ 模块顶部（mod.rs）描述职责
//! Profile 模块 - 档案管理
//!
//! 职责：档案 CRUD、需求分析、标签职位管理

/// 根据档案的五维信号计算综合评分
///
/// 综合考虑吸引力、可用性、安全性、窗口四个维度，
/// 权重参考 strategy 模块的 config.json。
///
/// # Arguments
/// * `profile` - 档案引用
///
/// # Returns
/// 0-100 的综合评分
pub fn calculate_score(profile: &Profile) -> i32 {
    // ...
}
```

### 关键点

- 模块顶部用 `//!`（内部注释）
- 函数/结构体用 `///`（外部文档）
- 中文 + 简洁 + 说"做什么"和"为什么"，不说"怎么做"

---

## 6. API 处理器模式（对应 Requirement 1, 9）

### 适用场景

axum 路由处理器、HTTP handler 函数。

### 错误示例 ❌

```rust
// ❌ 返回 String 错误
async fn get_profile(
    State(state): State<AppState>,
    Path(id): Path<i32>,
) -> Result<Json<Profile>, String> {
    // ...
}

// ❌ unwrap 在 handler 中
async fn get_profile(...) -> Result<Json<Profile>, AppError> {
    let row = sqlx::query_as::<_, Profile>("...")
        .fetch_one(state.db.pool())
        .await
        .unwrap();
    Ok(Json(row))
}
```

### 正确示例 ✅

```rust
// ✅ 标准 axum handler 签名
async fn get_profile(
    State(state): State<AppState>,
    Path(id): Path<i32>,
) -> Result<Json<ApiResponse<Profile>>, AppError> {
    let row = sqlx::query_as::<_, Profile>(
        "SELECT * FROM profile WHERE id = $1"
    )
    .bind(id)
    .fetch_optional(state.db.pool())
    .await
    .with_context("查询档案失败")?
    .ok_or_else(|| AppError::NotFound(format!("档案 {} 不存在", id)))?;

    Ok(Json(ApiResponse::success(row)))
}

// ✅ POST handler with Json body
async fn create_profile(
    State(state): State<AppState>,
    Json(input): Json<CreateProfileInput>,
) -> Result<Json<ApiResponse<i32>>, AppError> {
    let id = sqlx::query_scalar::<_, i32>(
        "INSERT INTO profile (name) VALUES ($1) RETURNING id"
    )
    .bind(&input.name)
    .fetch_one(state.db.pool())
    .await
    .with_context("创建档案失败")?;

    Ok(Json(ApiResponse::success(id)))
}
```

### 标准签名模板

```rust
async fn <name>(
    State(state): State<AppState>,
    Path(<param>): Path<T>,
    Json(<body>): Json<T>,
) -> Result<Json<ApiResponse<R>>, AppError>
```

- `State<AppState>` - 全局状态
- `Path<T>` / `Query<T>` - URL 参数
- `Json<T>` - 请求体
- 返回 `Result<Json<ApiResponse<R>>, AppError>`

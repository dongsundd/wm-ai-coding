# Rust 编码规范提醒

## 格式化 (Formatting)

- ✅ 使用 `rustfmt` 风格
- ✅ 4 空格缩进（不是 tab）
- ✅ 行长度不超过 100 字符
- ✅ 运算符周围有空格：`let x = 1 + 2;`
- ✅ 逗号后有空格：`[1, 2, 3]`
- ✅ `{:?}` 用于调试，`{}` 用于用户输出

## 命名规范 (Naming)

| 类型 | 规范 | 示例 |
|------|------|------|
| 变量 | snake_case | `let max_value = 10;` |
| 函数 | snake_case | `fn get_length() {}` |
| 模块 | snake_case | `mod my_module;` |
| 类型 | PascalCase | `struct UserProfile;` |
| Trait | PascalCase | `trait Readable {}` |
| Enum 变体 | PascalCase | `enum Status { Active, Inactive }` |
| 常量 | SCREAMING_SNAKE_CASE | `const MAX_SIZE: usize = 100;` |
| 宏 | snake_case | `macro_rules! my_macro` |

## 所有权与借用

### 优先所有权
```rust
// ✅ 推荐：返回所有权
fn first_char(s: String) -> char {
    s.chars().next().unwrap()
}

// ❌ 避免：仅为了获取值而克隆
fn first_char(s: &String) -> char {
    s.clone().chars().next().unwrap()
}
```

### 借用而非克隆
```rust
// ✅ 推荐
fn print_str(s: &str) {
    println!("{}", s);
}

// ❌ 避免
fn print_str(s: String) {
    println!("{}", s);
}
```

### 避免不必要的 clone
```rust
// ❌ 避免
let x = some_function();
let y = x.clone();

// ✅ 优先
let x = some_function();
let y = x;  // 如果之后不再使用 x
```

### 借用检查
```rust
fn mutate(v: &mut Vec<i32>) {
    v.push(42);
}

fn read(v: &Vec<i32>) {
    println!("{}", v.len());
}
```

## 错误处理

### 使用 Result
```rust
// ✅ 推荐
fn read_file(path: &str) -> Result<String, io::Error> {
    fs::read_to_string(path)
}

// ❌ 避免
fn read_file(path: &str) -> String {
    fs::read_to_string(path).unwrap()  // 可能 panic
}
```

### 使用 ? 操作符
```rust
fn process() -> Result<String, io::Error> {
    let content = read_file("input.txt")?;
    let parsed = parse(&content)?;
    Ok(parsed)
}
```

### 提供有意义的错误
```rust
// ✅ 推荐
Err(Error::new(
    ErrorKind::InvalidInput,
    format!("invalid config: {}", path)
))

// ❌ 避免
Err("invalid config")
```

## 安全性

### 限制 unsafe 代码
```rust
// ✅ 最小化 unsafe 块
unsafe {
    let ptr = slice.as_ptr();
    // 只做必要的操作
    ptr::read(ptr)
}

// ❌ 避免大范围 unsafe
unsafe {
    // 大段代码
}
```

### 使用安全抽象
```rust
// ✅ 使用安全容器
let boxed = Box::new(42);
let rc = Rc::new(data);
let arc = Arc::new(data);

// ❌ 避免裸指针
let ptr: *mut i32 = &mut value;
```

## 惯用法

### Option 处理
```rust
// unwrap_or_else 是懒加载
let x = opt.unwrap_or_else(|| expensive_computation());

// map 转换
let result = opt.map(|v| v * 2);

// and_then 链式
let result = parse(input)
    .and_then(|n| validate(n))
    .and_then(|n| process(n));
```

### 迭代器链式
```rust
// ✅ 链式操作
let result: Vec<i32> = items.iter()
    .filter(|x| *x > 0)
    .map(|x| x * 2)
    .collect();

// ✅ 使用 collect 收集到不同类型
let set: HashSet<_> = iter.collect();
let string: String = chars.collect();
```

### 模式匹配
```rust
match value {
    Some(x) if x > 0 => { /* */ }
    Some(_) => { /* */ }
    None => { /* */ }
}
```

## 注释规范

```rust
/// 文档注释 - 公开 API
/// 
/// # Arguments
/// * `name` - The name to greet
pub fn greet(name: &str) -> String {}

// // 行注释
// // 解释代码意图

// TODO 注释
// TODO: 实现错误处理

// 不安全代码注释
// SAFETY: 解释为什么不安全是安全的
unsafe fn do_unsafe_thing() {}
```

## 模块组织

```rust
// 模块层级
mod inner {
    pub fn public_fn() {}
    fn private_fn() {}
}

pub use inner::public_fn;  // 重新导出
```

## 测试

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_example() {
        assert_eq!(add(2, 2), 4);
    }
}
```

## 依赖管理

```rust
// Cargo.toml 规范
[dependencies]
name = "version"    // 精确版本
name = "1.0"       // 兼容版本
name = "1.0.0"     // 补丁兼容

[dev-dependencies]
# 开发依赖

[build-dependencies]
# 构建脚本依赖
```
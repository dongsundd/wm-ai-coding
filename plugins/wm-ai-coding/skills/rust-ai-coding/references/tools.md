# Rust 工具链参考

## Cargo - 包管理器

### 基本命令

```bash
# 创建新项目
cargo new my_project        # 二进制
cargo new --lib my_lib      # 库

# 构建
cargo build                # 调试构建
cargo build --release      # 优化构建
cargo build --lib          # 仅库
cargo build --bin name     # 仅二进制

# 运行
cargo run                  # 运行项目
cargo run --release        # 优化运行
cargo run -- example name  # 运行示例

# 测试
cargo test                 # 运行所有测试
cargo test --lib           # 仅库测试
cargo test --test name     # 集成测试
cargo test -- --nocapture  # 显示输出

# 检查 (快速类型检查)
cargo check               # 检查编译
cargo check --all-targets # 检查所有目标

# 文档
cargo doc                 # 构建文档
cargo doc --open          # 构建并打开
cargo doc --no-deps       # 仅项目代码

# 清理
cargo clean               # 清理构建产物
cargo clean --release     # 仅清理 release

# 更新依赖
cargo update              # 更新依赖
cargo update package_name # 更新指定包

# 发布
cargo publish             # 发布到 crates.io
cargo login               # 登录 crates.io

# 查看信息
cargo tree                # 依赖树
cargo tree -i package     # 反向依赖
cargo metadata            # 元数据 JSON
cargo version             # 版本信息
```

### Cargo.toml 结构

```toml
[package]
name = "my_crate"
version = "0.1.0"
edition = "2021"          # Rust 版本: 2015, 2018, 2021, 2024
authors = ["Name <email>"]
description = "..."
license = "MIT"
homepage = "https://..."

[dependencies]
# 精确版本
foo = "1.0.0"

# 范围版本
bar = "1.0"              # 1.0.x
baz = ">=1.0.0"          # 最小版本
qux = "<2.0.0"           # 最大版本

# 特性
async = { version = "1.0", optional = true }
tokio = { version = "1.0", features = ["full"] }

# Git 依赖
git = "https://github.com/rust-lang/rustfmt"
branch = "master"

# 路径依赖
local_crate = { path = "../local" }

[dev-dependencies]
# 开发依赖 (仅测试)
criterion = "0.3"

[build-dependencies]
# 构建脚本依赖
cc = "1.0"

[features]
default = ["default_feat"]
default_feat = []
extra_feat = []

[workspace]
members = ["crate1", "crate2"]
exclude = ["exclude_crate"]

[profile.dev]
opt-level = 0
debug = true

[profile.release]
opt-level = 3
lto = "thin"

[lib]
name = "my_crate"
path = "src/lib.rs"

[[bin]]
name = "my_bin"
path = "src/main.rs"
```

### 常见配置

```toml
# .cargo/config.toml
[build]
target = "x86_64-unknown-linux-gnu"

[target.x86_64-pc-windows-gnu]
linker = "gcc"

[net]
retry = 5

[term]
verbose = false
color = "auto"

[alias]
b = "build"
t = "test"
r = "run"
c = "check"
```

## Rustc - 编译器

```bash
# 编译
rustc main.rs            # 编译文件
rustc --crate-type lib   # 库

# 选项
rustc -o output          # 输出文件
rustc -g                 # 调试信息
rustc -O                 # 优化
rustc --emit=asm         # 输出汇编
rustc --emit=llvm-ir     # 输出 LLVM IR
rustc --emit=metadata    # 输出元数据

# 目标
rustc --print target-list    # 列出支持目标
rustc --target x86_64-pc-windows-gnu

# 版本
rustc --version
rustc +stable build
rustc +nightly build

# 文档
rustup doc --book        # 打开 Rust Book
rustup doc --std         # 打开标准库文档
rustup doc --core        # 打开 core 文档
rustup doc --cargo       # 打开 Cargo Book
rustup doc --rustc       # 打开编译器文档
```

## Rustup - 工具链管理

```bash
# 安装
rustup install stable
rustup install nightly
rustup install 1.70.0

# 切换
rustup default stable
rustup default nightly

# 目标
rustup target add x86_64-unknown-linux-gnu
rustup target list --installed

# 组件
rustup component add clippy
rustup component add rustfmt
rustup component add rust-src

# 更新
rustup update
rustup self update

# 工具链信息
rustup show
rustup toolchain list
rustup target list
```

## Clippy - Linter

```bash
# 运行 clippy
cargo clippy
cargo clippy -- -W clippy::all          # 警告视为错误
cargo clippy -- -D clippy::style       # 禁止样式警告
cargo clippy -- -A clippy::explicit_iter_loop  # 允许特定警告

# 检查特定目标
cargo clippy --lib
cargo clippy --bins
cargo clippy --tests

# CI 检查
cargo clippy --all-targets --all-features -- -D warnings
```

## Rustfmt - 代码格式化

```bash
# 格式化
rustfmt main.rs
rustfmt src/               # 格式化目录
rustfmt --check           # 检查但不修改
rustfmt --edition 2021    # 指定版本

# 配置 (rustfmt.toml)
max_width = 100
tab_spaces = 4
hard_tabs = false
newline_style = "Unix"
use_small_heuristics = "Default"
reorder_imports = true
reorder_modules = true
remove_nested_parens = true
```

## 测试框架

```rust
// 单元测试
#[cfg(test)]
mod tests {
    #[test]
    fn it_works() {
        assert_eq!(2 + 2, 4);
    }
    
    #[test]
    #[should_panic]
    fn it_panics() {
        panic!("expected panic");
    }
    
    #[test]
    fn result_test() -> Result<(), String> {
        if true { Ok(()) } else { Err("failed".into()) }
    }
}

// 集成测试 (tests/ 目录)
#[test]
fn test_integration() {
    // 测试公开 API
}

// 文档测试
/// ```
/// let x = add(1, 2);
/// assert_eq!(x, 3);
/// ```
pub fn add(a: i32, b: i32) -> i32 { a + b }

// 基准测试 (benches/ 目录)
use criterion::{black_box, criterion_group, criterion_main};

fn bench_add(c: &mut Criterion) {
    c.bench_function("add", |b| {
        b.iter(|| add(black_box(1), black_box(2)));
    });
}

criterion_group!(benches, bench_add);
criterion_main!(benches);
```

## Crates.io 生态

### 常用库

| 类别 | 库 | 用途 |
|------|-----|------|
| 异步 | tokio | 异步运行时 |
| 异步 | async-std | 异步标准库 |
| Web | actix-web | Web 框架 |
| Web | axum | Web 框架 |
| Web | rocket | Web 框架 |
| API | reqwest | HTTP 客户端 |
| JSON | serde_json | JSON 序列化 |
| 日志 | tracing | 结构化日志 |
| 错误 | anyhow | 错误处理 |
| 数据库 | sqlx | 数据库 ORM |
| CLI | clap | 命令行解析 |
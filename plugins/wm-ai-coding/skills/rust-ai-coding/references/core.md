# Rust Core 库参考 (core)

## 概述

Core 库是 Rust 的基础库，无依赖、可移植，是标准库 (std) 的底层依赖。

**特点**：
- 不涉及堆内存分配 (无 `alloc`)
- 不涉及并发 (无 `thread`)
- 不涉及 I/O (无 `io`)
- 平台无关

## 原始类型 (Primitives)

```rust
// 整数
i8, i16, i32, i64, i128, isize
u8, u16, u32, u64, u128, usize

// 浮点数
f32, f64

// 其他
bool, char, str, ()  // unit
fn                    // 函数指针
*const T, *mut T      // 裸指针
&T, &mut T           // 引用
[T; N]               // 数组
(T, U, ...)          // 元组
!                    // never type (实验)
```

## 核心模块

### 1. mem - 内存操作
```rust
use core::mem;

// 获取类型大小
mem::size_of::<i32>()  // 4

// 获取类型对齐
mem::align_of::<i32>() // 4

// 创建未初始化的值
let x: i32 = mem::uninitialized(); // 已废弃

// 创建展位符
let x: i32 = mem::zeroed();

// 替换值
let mut a = vec![1, 2, 3];
let b = mem::take(&mut a);

// 替换为默认值
let mut s = String::from("hello");
mem::take(&mut s);

// 获取值并替换为默认值
let mut x = Some(5);
let y = x.take();  // Option::take
```

### 2. ptr - 指针操作
```rust
use core::ptr;

// 复制内存
ptr::copy(src, dst, count);
ptr::copy_nonoverlapping(src, dst, count);

// 读取/写入
ptr::read(ptr);
ptr::write(ptr, value);

// 空指针
ptr::null::<i32>()
ptr::null_mut::<i32>()
```

### 3. option - Option 类型
```rust
use core::option::Option;

let x: Option<i32> = Some(5);
let y: Option<i32> = None;

// 方法
x.is_some();
x.is_none();
x.unwrap();           // panic if None
x.unwrap_or(0);        // 默认值
x.unwrap_or_else(|| 0);
x.map(|v| v * 2);      // 转换
x.and_then(|v| Some(v * 2));
```

### 4. result - Result 类型
```rust
use core::result::Result;

let x: Result<i32, &str> = Ok(5);
let y: Result<i32, &str> = Err("error");

// 方法
x.is_ok();
x.is_err();
x.unwrap();           // panic if Err
x.unwrap_err();       // panic if Ok
x.map(|v| v * 2);
x.map_err(|e| e.to_string());
x.and_then(|v| Ok(v * 2));
```

### 5. iter - 迭代器
```rust
// Iterator trait 方法
iter.next()
iter.collect()
iter.map(|x| x * 2)
iter.filter(|x| *x > 0)
iter.fold(0, |acc, x| acc + x)
iter.enumerate()
iter.zip(other)
iter.chain(other)
```

### 6. marker - 标记 trait
```rust
// 核心 trait
trait Send {}           // 可在线程间传递
trait Sync {}           // 可安全共享引用
trait Sized {}          // 已知大小
trait Copy {}           // 复制语义
trait Clone {}          // 可克隆
trait Default {}       // 有默认值
trait Drop {}          // 析构函数

// 不稳定
trait Unpin {}
trait UnwindSafe {}
trait RefUnwindSafe {}
```

### 7. convert - 类型转换
```rust
// From / Into
impl From<&str> for String
impl From<String> for Box<str>

// AsRef / AsMut
impl AsRef<[u8]> for Vec<u8>
impl AsMut<[u8]> for Vec<u8>

// AsPtr / AsMutPtr
```

### 8. fmt - 格式化
```rust
// Debug trait
impl fmt::Debug for MyType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "MyType {{ ... }}")
    }
}

// Display trait (需要手动实现)
impl fmt::Display for MyType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "my_value")
    }
}
```

### 9. panic - Panic 处理
```rust
panic!("message");
panic!("expected {}, got {}", expected, actual);

// 使用 panic hooks
std::panic::set_hook(Box::new(|info| {
    println!("panic: {}", info);
}));
```

## Intrinsics (编译器内置)

```rust
// 需通过 core::intrinsics 访问 (不稳定)
// transmute - 类型转换
// bitcast - 位转换
// assert_invariant - 断言不变量
// offset - 指针偏移
```

## 编译期计算

```rust
// Const functions (Rust 1.48+)
const fn add(a: i32, b: i32) -> i32 {
    a + b
}

const VALUE: i32 = add(1, 2);

// Const generics (Rust 1.51+)
fn foo<T, const N: usize>(arr: [T; N]) -> &T {
    &arr[0]
}
```

## 与 std 的区别

| 功能 | core | std |
|------|------|-----|
| Vec | ❌ | ✅ |
| String | ❌ | ✅ |
| Box | ✅ (alloc) | ✅ |
| HashMap | ❌ | ✅ |
| 线程 | ❌ | ✅ |
| I/O | ❌ | ✅ |
| 网络 | ❌ | ✅ |
| 原始类型 | ✅ | ✅ |
| Option/Result | ✅ | ✅ |
| Iterator | ✅ | ✅ |
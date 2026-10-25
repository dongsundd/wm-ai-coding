# Rust 程序设计语言 (The Rust Book)

## 章节概览

### 第一部分：基础

1. **入门** - 安装、Hello World、项目结构
2. **编程概念** - 变量、数据类型、函数、控制流
3. **所有权系统** - 所有权、借用、生命周期
4. **结构体与方法** - struct、impl、方法
5. **枚举与模式匹配** - enum、match、if let
6. **模块系统** - mod、pub、use、crate
7. **常用集合** - Vec、String、HashMap
8. **错误处理** - Result、panic、?

### 第二部分：中级

9. **泛型与 Trait** - 泛型、Trait、Trait Bound
10. **生命周期** - 生命周期标注、static
11. **测试** - 单元测试、集成测试、文档测试
12. **闭包** - 闭包语法、Fn/FnMut/FnOnce
12. **迭代器** - Iterator、迭代器适配器
14. **智能指针** - Box、Rc、Arc、Cell、RefCell
15. **并发** - 线程、Send、Sync、Mutex

### 第三部分：高级

16. **不安全 Rust** - unsafe、裸指针、FFI
17. **Trait 对象** - 动态分发、对象安全
18. **高级类型** - 类型别名、Newtype、never type
19. **宏** - 声明宏、过程宏

## 核心概念

### 所有权规则
1. 每个值有一个所有者
2. 同一时间只有一个所有者
3. 所有者离开作用域时值被丢弃

### 借用规则
1. 任意数量的不可变引用 OR 一个可变引用
2. 引用必须始终有效

### 生命周期
```rust
&'a str           // 字符串切片
fn foo<'a>(x: &'a str) -> &'a str  // 输入输出生命周期相同
struct Foo<'a> { x: &'a str }
impl<'a> Foo<'a> { ... }
```

### Trait
```rust
pub trait Summary {
    fn summarize(&self) -> String;
    fn default_impl(&self) -> String {
        String::from("(Read more...)")
    }
}

pub struct NewsArticle { ... }
impl Summary for NewsArticle {
    fn summarize(&self) -> String { ... }
}
```

### 泛型
```rust
fn largest<T: PartialOrd>(list: &[T]) -> &T { ... }

struct Pair<T, U> {
    x: T,
    y: U,
}
```

### 闭包
```rust
let add = |a, b| a + b;
let add = |a, b| -> i32 { a + b };

// Fn, FnMut, FnOnce
fn apply<F: Fn(i32) -> i32>(f: F, x: i32) -> i32 { f(x) }
```

### 迭代器
```rust
let v = vec![1, 2, 3];
let iter = v.iter();
for val in iter { ... }

// 适配器
iter.map(|x| x * 2)
    .filter(|x| *x > 0)
    .collect()

// 消费者
iter.sum()
    .fold(0, |acc, x| acc + x)
    .find(|x| *x > 0)
```

### 并发
```rust
use std::thread;
use std::sync::Mutex;

let handle = thread::spawn(|| {
    // 多线程代码
});
handle.join().unwrap();

// 共享状态
let m = Mutex::new(0);
{
    let mut num = m.lock().unwrap();
    *num += 1;
}
```

### 不安全 Rust
```rust
unsafe fn dangerous() { ... }

let mut num = 5;
let r1 = &num as *const i32;
let r2 = &mut num as *mut i32;

unsafe {
    println!("{}", *r1);
}

// FFI
extern "C" {
    fn abs(input: i32) -> i32;
}
```

## 学习路径建议

1. **入门**: 第1-8章，理解基础语法和所有权
2. **进阶**: 第9-15章，掌握泛型、trait、并发
3. **高级**: 第16-19章，理解 unsafe、宏、底层机制

## 在线资源

- 官方文档: https://doc.rust-lang.org/book/
- 标准库: https://doc.rust-lang.org/std/
- Rust by Example: https://doc.rust-lang.org/rust-by-example/
- Rustlings: https://github.com/rust-lang/rustlings
- Exercism: https://exercism.org/tracks/rust
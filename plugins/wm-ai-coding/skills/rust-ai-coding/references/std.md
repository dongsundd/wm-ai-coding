# Rust 标准库参考 (std)

## 核心模块

### 1. 基础类型 (Primitives)
- `bool` - 布尔类型
- `char` - Unicode 字符 (32位)
- `i8`, `i16`, `i32`, `i64`, `i128`, `isize` - 有符号整数
- `u8`, `u16`, `u32`, `u64`, `u128`, `usize` - 无符号整数
- `f32`, `f64` - 浮点数
- `str` - 字符串切片 (&str)
- `usize`, `isize` - 指针大小的整数

### 2. 常用集合 (Collections)
- **Vec<T>** - 可增长的动态数组
  - 创建: `Vec::new()`, `vec![1, 2, 3]`, `Vec::with_capacity(n)`
  - 操作: `push()`, `pop()`, `len()`, `capacity()`, `iter()`
  
- **String** - 可变字符串 (UTF-8)
  - 创建: `String::new()`, `String::from("...")`, `format!("{}", x)`
  - 操作: `push()`, `push_str()`, `len()`, `chars()`, `split()`
  
- **HashMap<K, V>** - 哈希映射
  - 创建: `HashMap::new()`, `HashMap::from([...])`
  - 操作: `insert()`, `get()`, `contains_key()`, `remove()`

### 3. 选项与结果 (Option & Result)
```rust
// Option<T> - 可能存在或不存在的值
let x: Option<i32> = Some(5);
let y: Option<i32> = None;

// Result<T, E> - 错误处理
fn read_file() -> Result<String, std::io::Error> {
    std::fs::read_to_string("file.txt")
}
```

### 4. 智能指针
- **Box<T>** - 堆分配
- **Rc<T>** - 引用计数 (单线程)
- **Arc<T>** - 原子引用计数 (多线程)
- **Cell<T>** / **RefCell<T>** - 内部可变性

### 5. 迭代器 (Iterator)
```rust
let v = vec![1, 2, 3];
for i in v.iter() {
    println!("{}", i);
}
// 或
v.iter().map(|x| x * 2).filter(|x| *x > 3).collect::<Vec<_>>();
```

### 6. 错误处理宏
- `panic!()` - 触发 panic
- `assert!()`, `assert_eq!()`, `assert_ne!()` - 断言
- `unreachable!()` - 标记不可达代码
- `unimplemented!()` - 标记未实现

### 7. 标准宏
- `println!()`, `print!()` - 打印
- `format!()` - 字符串格式化
- `vec![]` - 创建 Vec
- `dbg!()` - 调试打印
- `env!("VAR")` - 环境变量

## 常用 trait

- `Clone` - 克隆
- `Copy` - 复制语义
- `Default` - 默认值
- `Display`, `Debug` - 格式化
- `From`, `Into` - 类型转换
- `Iterator` - 迭代器
- `IntoIterator` - 可迭代
- `serde::Serialize`, `Deserialize` - 序列化

## 模块层级

```
std
├── alloc    - 内存分配
├── array    - 数组操作
├── borrow   - 借用检查
├── cell     - 内部可变性
├── cmp      - 比较
├── collections - 集合
├── fmt      - 格式化
├── hash     - 哈希
├── io       - 输入输出
├── iter     - 迭代器
├── mem      - 内存操作
├── option   - Option 类型
├── prelude  - 预导入
├── ptr      - 指针操作
├── rc       - 引用计数
├── result   - Result 类型
├── slice    - 切片操作
├── str      - 字符串操作
├── string   - String 类型
├── sync     - 同步原语
├── thread   - 线程
└── vec      - Vec 类型
```
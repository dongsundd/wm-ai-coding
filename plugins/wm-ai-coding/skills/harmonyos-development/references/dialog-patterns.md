# CustomDialogController 正确用法（踩坑总结）

> 来源：实际使用场景。

## 问题现象

`TagSelectDialog` 在关闭后状态残留，导致下一次打开时显示上一次的选择。

## 根因分析

**错误模式**：在 `CustomDialog` 组件内部创建 `CustomDialogController`

```typescript
@CustomDialog
struct TagSelectDialog {
  // ❌ 错误：在组件内部创建 controller
  controller: CustomDialogController = new CustomDialogController({
    builder: TagSelectDialog({ ... }),
  });

  aboutToDisappear(): void {
    // 销毁 controller - 但此时组件已经渲染完毕，问题已发生
    this.controller = null;
  }
}
```

**为什么错**：`CustomDialogController` 控制 Dialog 的生命周期，而 Dialog 组件自己的生命周期由 HarmonyOS 管理。两者混在一起会导致状态不一致。

## 正确模式：ComponentContent（API 12+）

```typescript
// ✅ TagSelectDialog - 纯 UI 组件，不持有 controller
@CustomDialog
struct TagSelectDialog {
  @Link selectedTags: Tag[];
  // 不创建 controller，只接收 controller 作为参数

  build() {
    Column() {
      // ... UI 内容
      List() {
        ForEach(this.tags, (tag: Tag) => {
          ListItem() {
            SelectRow({ tag: tag, selected: this.isSelected(tag) })
              .onClick(() => { this.toggle(tag); })
          }
        })
      }
    }
  }
}

// ✅ 使用方：持有 controller，在 aboutToAppear 中创建
@Entry
@Component
struct ChatDetailPage {
  @State selectedTags: Tag[] = [];
  dialogController: CustomDialogController | null = null;

  aboutToAppear(): void {
    // 在生命周期中创建 controller
    this.dialogController = new CustomDialogController({
      builder: TagSelectDialog({ selectedTags: $selectedTags }),
      customStyle: true,
    });
  }

  openDialog(): void {
    this.dialogController?.open();
  }

  aboutToDisappear(): void {
    // 清理 controller
    this.dialogController = null;
  }
}
```

## 正确模式：传统方式（API 9-11）

```typescript
// ✅ 使用方：在 @Component 中持有 controller
@Entry
@Component
struct MyPage {
  @State selectedTags: Tag[] = [];
  private dialogController: CustomDialogController;

  aboutToAppear(): void {
    this.dialogController = new CustomDialogController({
      builder: TagSelectDialog({ selectedTags: $selectedTags }),
      alignment: DialogAlignment.Bottom,
    });
  }

  aboutToDisappear(): void {
    // 重要：aboutToDisappear 中关闭 dialog
    if (this.dialogController) {
      this.dialogController.close();
      this.dialogController = null;
    }
  }
}
```

## 关键约束汇总

| 约束 | 说明 |
|------|------|
| controller 在 aboutToAppear 中创建 | 确保 Dialog 能正确渲染 |
| aboutToDisappear 中 close + null | 防止状态污染 |
| Dialog 组件不自己创建 controller | 只接收外部传入的 controller |
| 使用 @Link 而非 @State | 确保父子状态同步 |

## 常见错误

```typescript
// ❌ 错误 1：controller 在 build() 中创建
build() {
  let controller = new CustomDialogController({ ... });
  // 每次 build 都创建新实例，状态丢失
}

// ❌ 错误 2：Dialog 内部持有 @State controller
@CustomDialog
struct MyDialog {
  @State controller: CustomDialogController  // 不要这样做
}

// ❌ 错误 3：关闭 dialog 后不清理
aboutToDisappear(): void {
  // 没有 close()，会导致内存泄漏和状态残留
}
```

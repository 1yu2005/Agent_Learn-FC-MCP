# 一、SDK

**SDK** 是 **Software Development Kit** 的缩写，中文叫 **软件开发工具包**。它是==一整套帮助开发者==在某个平台、系统、硬件或服务上==开发软件的工具和资源集合==。

简单说：**SDK 是为了让你更方便地开发某类应用而提供的一整套“开发套件”。**

## SDK 通常包含什么？ ⭐⭐⭐⭐⭐

- **库/代码包**：封装好的函数、类、模块，直接调用即可
- **API**：定义如何与平台或服务交互的接口
- **文档**：使用说明、参考手册、教程
- **示例代码**：演示如何调用功能
- **开发工具**：编译器、调试器、模拟器、命令行工具等
- **运行时环境**：有些 SDK 会包含运行所需的环境
- **配置文件/密钥**：某些服务需要认证信息

## SDK 和 API 有什么区别？

这是最容易混淆的地方：

| 概念    | 含义                                       |
| ------- | ------------------------------------------ |
| **API** | 接口规范，定义“能调用什么、怎么调用”       |
| **SDK** | 工具包，提供实现、工具、文档，通常包含 API |

可以这样理解：

- **API 是菜单**：告诉你有哪些菜、怎么点
- **SDK 是整套厨房工具 + 食材 + 菜谱**：让你能直接把菜做出来

也就是说，**SDK 通常包含 API**，但 API 不一定以 SDK 的形式提供。你可以直接调用 HTTP API，也可以使用别人封装好的 SDK。

## 常见例子

- **Android SDK**：开发 Android 应用
- **iOS SDK**：开发 iPhone/iPad 应用
- **JDK**：Java 开发工具包，Java 的 SDK
- **AWS SDK**：调用亚马逊云服务
- **微信支付 SDK**：快速接入微信支付
- **Python SDK**：比如 `boto3` 就是 AWS 的 Python SDK

## 为什么用 SDK？

- 减少重复工作，不用从零实现
- 封装复杂细节，比如签名、加密、重试
- 提供统一接口，保证兼容性
- 附带文档和示例，降低学习成本

## 一句话总结

**SDK 就是让开发者能更方便地为某个平台、服务或硬件开发软件的一整套工具和资源。**它通常包含 API、库、文档和开发工具，目标是提高开发效率、降低门槛。



# 二、JSON 数据

## 1. JSON 是什么

JSON 是一种**用==纯文本==表示数据的格式**，全称 JavaScript Object Notation。  
它语言无关，常用于：

- API 数据传输
- 配置文件
- 前后端数据交换

==JSON 本身是**字符串/文本**==，不是 Python 字典。  
只是它长得经常像 Python 的字典或列表。

---

## 2. JSON 的两种核心结构

### 对象

用 `{}` 表示，里面是键值对：

```json
{
  "name": "张三",
  "age": 25
}
```

### 数组

用 `[]` 表示，里面是有序的值：

```json
["阅读", "跑步", "编程"]
```

两者可以互相嵌套。

---

## 3. 一个典型 JSON 示例

```json
{
  "name": "张三",
  "age": 25,
  "isStudent": false,
  "hobbies": ["阅读", "跑步", "编程"],
  "address": {
    "city": "北京",
    "zip": "100000"
  },
  "courses": [
    { "title": "数学", "score": 95 },
    { "title": "英语", "score": 88 }
  ],
  "nickname": null
}
```

实际传输时，JSON 常常压缩成一行：

```json
{"name":"张三","age":25,"hobbies":["阅读","跑步"]}
```

换行和空格只是为了让格式更易读。

---

## 4. JSON 支持的值类型

| 类型   | 示例                 |
| ------ | -------------------- |
| 字符串 | `"hello"`            |
| 数字   | `123`、`3.14`        |
| 布尔值 | `true`、`false`      |
| 空值   | `null`               |
| 对象   | `{ "key": "value" }` |
| 数组   | `[1, 2, 3]`          |

==顶层可以是对象、数组，也可以是字符串、数字、布尔值或 `null`。==  
但最常见的是**对象**或**数组**。

---

## 5. JSON 语法规则  ⭐⭐⭐⭐⭐

- 键必须用**双引号**：`"name"`
- 字符串必须用**双引号**
- 多个键值对用逗号分隔
- 标准 JSON **不支持注释**
- 标准 JSON **不允许尾随逗号**
- 一个 JSON 文件只能有一个顶层值
- 可以嵌套对象和数组

错误示例：

```json
{
  name: "张三",   // 错：键没有双引号
  age: 25,        // 错：尾随逗号
}
```

---

## 6. JSON 与 Python 的对应关系

| JSON             | Python           |
| ---------------- | ---------------- |
| 对象 `{}`        | `dict`           |
| 数组 `[]`        | `list`           |
| 字符串 `"abc"`   | `str`            |
| 数字 `123`       | `int` / `float`  |
| `true` / `false` | `True` / `False` |
| `null`           | `None`           |

注意大小写：

- JSON 是 `true`、`false`、`null`
- Python 是 `True`、`False`、`None`

---

## 7. JSON 字符串 vs 解析后的数据

这段是 Python 里的 **JSON 字符串**：

```python
'{"name": "张三", "age": 25}'
```

注意外层有引号，说明它是一个字符串。  
它看起来像字典，但还不是字典。

用 Python 解析后：

```python
import json

s = '{"name": "张三", "age": 25}'
data = json.loads(s)

print(data)        # {'name': '张三', 'age': 25}
print(type(data))  # <class 'dict'>
```

这时候它才是真正的 Python 字典。

反过来，把 Python 对象转成 JSON 字符串：

```python
import json

py_obj = {"name": "李四", "age": 30}
json_str = json.dumps(py_obj, ensure_ascii=False)

print(json_str)  # {"name": "李四", "age": 30}
```

简单记：

- ==`json.loads()`：JSON 字符串 → Python 对象==
- ==`json.dumps()`：Python 对象 → JSON 字符串==

---

## 8. 常见误区

- 以为 JSON 就是 Python 字典  
  → JSON 是文本格式，解析后才可能变成字典。
- 以为 JSON 一定是字典  
  →==JSON 顶层也可以是数组、字符串、数字、布尔值、`null`==
- 以为 JSON 可以用单引号  
  → 标准 JSON 必须用双引号。
- 以为 JSON 可以写注释  
  → 标准 JSON 不支持注释。
- 以为 JSON 可以尾随逗号  
  → 标准 JSON 不允许尾随逗号。
- 混淆 `true/false/null` 和 `True/False/None`  
  → JSON 用小写，Python 用大写和 `None`。

---

## 9. 一句话总结

JSON 是一种用字符串表示数据的格式，经常长得像字典，但解析后可能是字典、列表、字符串、数字、布尔值或 `null`。  
在 Python 中，可以用 `json.loads()` 把 JSON 字符串转成 Python 对象，用 `json.dumps()` 把 Python 对象转成 JSON 字符串。
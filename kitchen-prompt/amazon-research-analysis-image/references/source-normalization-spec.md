# 数据源标准化规范

本参考定义 `multi-source-analysis-workbench` 内置解析器的默认输出契约。

## 1. 目标

解析层应将异构来源文件统一为稳定记录结构，使下游分析脚本无需关心输入来自 Excel、PDF、CSV、JSON、文本或 HTML。

## 2. 记录结构

每条标准化记录应为一个 JSON 对象，包含以下字段：

- `source_file`：原始文件路径或文件名
- `record_id`：来源内部稳定唯一标识
- `title`：短标题或合成标题
- `text`：用于分析的主文本
- `metadata`：来源特定属性对象

示例：

```json
{
  "source_file": "reports/customer_feedback.xlsx",
  "record_id": "Sheet1-42",
  "title": "Row 42",
  "text": "The battery lasted only two days and the charger became hot.",
  "metadata": {
    "source_type": "excel",
    "sheet_name": "Sheet1",
    "row_number": 42,
    "column_map": {
      "comment": "The battery lasted only two days and the charger became hot.",
      "rating": 2
    }
  }
}
```

## 3. 字段规则

`source_file`
- 可行时保留原始路径。
- 若所有输出共享同一根目录，允许使用相对路径。

`record_id`
- 在本次标准化输出中必须唯一。
- 优先使用确定性 ID，如 `sheet-row`、`page-index`、`filename-chunk`。

`title`
- 有来源标题时直接复用。
- 无标题时生成简短合成标题，如 `Page 3` 或 `Row 18`。

`text`
- 这是后续分析、标注、分类、摘要、向量化的主字段。
- 若单行信息不足，可合并多个相关单元格或段落后写入。

`metadata`
- 所有来源特有信息放在这里。
- 除非下游脚本明确要求，不要把所有字段平铺到顶层。

## 4. 分来源建议

Excel：
- 每个有效数据行一条记录
- 包含 `sheet_name`、`row_number`、`column_map`

PDF：
- 每页或每个分块一条记录
- 包含 `page`
- 若页面文本为空，记录可能需要 OCR

CSV：
- 每行一条记录
- 视需要保留 `row_number` 和原始行内容

JSON：
- 列表或对象集合中的每项一条记录
- 原始嵌套字段可放入 `metadata.raw`

TXT / Markdown：
- 每文件一条或按语义分块
- 分块时包含 `chunk_index`

HTML：
- 有页面标题时保留
- 若来源可提供 URL 类信息，建议写入元数据

## 5. 输出格式

默认输出应为 `jsonl`。

选择 `jsonl` 的原因：
- 适合大数据量流式处理
- 易于逐行检查
- 易于衔接 Python 或 LLM 下游管道

## 6. 非目标

本契约不强制领域分类法。

`rating`、`asin`、`journey_stage`、`appeals_l1`、`sentiment` 等领域字段，除非本身就存在于输入中，否则应在下游分析脚本中补充，而非写死在通用解析层。

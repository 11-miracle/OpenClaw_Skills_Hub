# 分析方法契约

本参考定义 `analysis_source_image_generate` 在异构文件完成标准化之后的默认分析推理契约。

核心目标是避免流程停在 `jsonl`。标准化记录只是地基；真正的分析必须包含显式编码框架、聚合逻辑和证据纪律，并可映射为可执行生成输出。

## 1. 适用范围

当用户有以下任一诉求时，使用本方法：
- 结构化结论
- 主题提取
- 问题分类
- VOC / 投诉分析
- 旅程或分段分析
- 机会识别
- 建议生成
- 新品描述生成
- 产品生图提示词生成
- 报告交付（仅在用户显式要求时）

若用户仅需解析，可跳过本方法。

## 2. 核心原则

每个结论都应可沿以下链路追溯：

`source file -> normalized record -> coded evidence row -> summary table -> finding -> image shape calibration -> recommendation -> generation output`

若无法沿此链路追溯，视为“未被证据充分支持的推断”。

## 3. 分析流程

### 步骤 1：定义分析单位

确定后续编码使用的行级单位，例如：
- 一条评论
- 一条投诉记录
- PDF 单页
- 语义分块
- 文档章节

规则：
- 单位要足够大以保留语义上下文
- 单位要足够小以保证稳定编码
- 若一条源记录含多个独立问题，应在下游拆为多条证据行，而非强塞到一组标签中

### 步骤 2：构建 `source_inventory`

记录分析样本覆盖范围。

最小字段：
- `source_file`
- `source_type`
- `included`
- `record_count`
- `date_range`
- `notes`

目的：
- 说明纳入了什么
- 暴露排除项与解析限制
- 避免无提示混合来源

### 步骤 3：构建 `coding_frame`

定义用于证据编码的维度。

维度示例：
- 分类维度：问题类型、投诉类别、APPEALS、主题
- 情绪维度：情绪极性、情绪类别、语气
- 过程维度：用户旅程阶段、操作步骤、生命周期阶段
- 分段维度：产品线、客户分群、区域、渠道
- 机会维度：风险、痛点、爽点、未满足需求、可行动性

最小字段：
- `dimension_name`
- `label_name`
- `label_definition`
- `inclusion_rule`
- `exclusion_rule`
- `example_signal`

规则：
- 用户给了框架时优先复用，不要平行发明新框架
- 若需新建分类体系，必须在输出结论前先定义清楚
- 不允许使用隐式标签和未文档化“直觉判定”

### 步骤 4：构建 `coded_evidence_rows`

这是主分析表，负责把标准化记录映射为一条或多条编码证据。

最小字段：
- `source_file`
- `record_id`
- `excerpt`
- `dimension_name`
- `label_name`
- `secondary_label`
- `segment_or_stage`
- `severity_or_strength`
- `evidence_level`
- `reason`
- `confidence`

规则：
- `excerpt` 需足以支撑标签判定
- `evidence_level` 至少区分 `direct` 与 `inferred`
- 标签不确定时应使用 `confidence`
- 一条标准化记录可对应多条编码证据（多问题场景）

### 步骤 5：构建 `dimension_summary`

将编码证据聚合成核心洞察视图。

最小字段：
- `dimension_name`
- `label_name`
- `count`
- `share`
- `top_segments_or_stages`
- `top_signals`
- `representative_excerpt`
- `interpretation`

规则：
- 占比必须基于实际纳入样本计算
- 样本若存在偏置（如低星样本、单渠道样本、部分采样），必须显式说明
- 不要输出超出样本可靠性的伪精度

### 步骤 6：构建 `segment_or_journey_summary`

当任务包含阶段、分群、流程或来源对比视角时使用该表。

最小字段：
- `segment_or_stage`
- `count`
- `share`
- `top_labels`
- `top_emotions_or_risks`
- `unmet_need_or_pattern`
- `representative_excerpt`

若任务确实不存在分段/旅程视角，可跳过，但必须显式写明。

### 步骤 7：构建 `recommendation_backlog`

建议必须来自重复出现或高严重度证据，而不是泛化“最佳实践”。

最小字段：
- `priority`
- `recommendation`
- `supported_by`
- `expected_impact`
- `difficulty_or_cost`
- `evidence_refs`

规则：
- 每条建议都要绑定到一条或多条标签/汇总结果
- 区分快速修复与结构性改进
- 不可给出无法回溯到证据的建议

### 步骤 8：构建 `evidence_appendix`

这是最终交付的证据追溯层。

最小字段：
- `source_file`
- `record_id`
- `title`
- `original_text`
- `normalized_or_translated_text`
- `labels`
- `segment_or_stage`
- `notes`

目的：
- 保持可审计性
- 支持抽样复核
- 在不干扰主体叙述的前提下保留代表性证据

### 步骤 9：执行 `image_shape_calibration`

在生成产品生图提示词前，默认先进行外部图片形态参考核对。

最小中间对象：
- `image_reference_pool`
- `shape_consensus`
- `shape_uncertainties`
- `shape_confidence`

#### `image_reference_pool`

记录候选参考图的筛选结果，仅用于收集真实商品外观参考。

最小字段：
- `source_url_or_domain`
- `source_type`
- `query_term`
- `product_match_level`
- `same_product_or_same_category`
- `usable`
- `rejection_reason`

规则：
- 默认优先级：电商商品详情页/商品结果 > 品牌官网 > 主流图片结果中的真实商品图
- 至少查看 `3-5` 张可靠图片后再形成参考判断
- 若仅有 `2` 张可用图片，可继续，但 `shape_confidence` 不得高于 `low`
- 概念图、纯渲染图、错类商品图、只有局部的营销海报图，必须标记为不可作为强证据

#### `shape_consensus`

只保留与分析不冲突、并可帮助避免外形失真的形态事实。

建议字段：
- `overall_silhouette`
- `critical_components`
- `assembly_relationships`
- `relative_proportions`
- `material_finish`
- `usage_pose`

规则：
- 只写可帮助核对主体轮廓、关键部件、连接关系、大致比例、典型材质外观与真实使用姿态的参考信息
- 若图片参考与分析结果冲突，默认以分析结果为主，并将差异记录到 `shape_uncertainties`
- 图片参考用于“外形与结构一致性核对”，不是卖点想象来源，也不决定核心场景

#### `shape_uncertainties`

记录图片参考无法确认、或与分析结果不一致的结构信息。

建议字段：
- `candidate_detail`
- `conflict_reason`
- `fallback_expression`

规则：
- 任何仅在单图出现、或与文本证据不一致的结构，默认进入不确定项
- 不确定项只能以 `suggested / inferred / optional` 语气进入提示词，不能写成确定事实
- 图片参考不用于扩写未被分析支持的材质、功能或改进点

#### `shape_confidence`

至少使用以下等级：
- `high`
- `medium`
- `low`

判定依据：
- 可用图片数量
- 来源可靠性
- 跨图一致性
- 与文本证据的冲突程度

默认规则：
- `high`：至少 3 张可靠图，且跨图高度一致、与文本不冲突
- `medium`：有 3 张左右可用图，但存在少量差异或局部不确定
- `low`：仅有 2 张可用图，或结果噪音较大，或存在明显不确定项

### 步骤 10：映射到生成输出（默认）

将分析结果映射为“新品描述 + 生图提示词”时，至少产出：
- `product_description_cn`
- `product_description_en`
- `image_prompt_structured_cn`
- `negative_prompt_cn`
- `image_prompt_structured_en`
- `negative_prompt_en`
- `evidence_highlights`

映射规则：
- 描述中的核心卖点必须来源于 `dimension_summary` 与 `recommendation_backlog` 的高频或高优先级证据。
- 视觉结构字段先来自分析结论；图片参考仅用于校验是否明显偏离真实商品形态，并在不冲突时补充保守结构信息。
- 视觉要素（主体、场景、材质、风格、镜头、灯光）必须能在 `coded_evidence_rows` / `evidence_appendix` / `shape_consensus` 中找到直接依据，或被明确标注为推断。
- `image_prompt_structured_cn` 与 `image_prompt_structured_en` 必须分成两个独立部分输出，不可混排。
- `negative_prompt_cn` 与 `negative_prompt_en` 也必须分成两个独立部分输出。
- `image_prompt_structured_*` 必须显式写出物理结构字段：`关键部件`、`几何与比例`、`连接与装配`、`受力与支撑`、`可动件运动范围`，避免仅输出“风格化描述”。
- 未被证据覆盖的结构参数（例如精确尺寸、内部骨架）应标注为 `inferred` 或 `insufficient`，并降级为“建议范围”，不得伪装为确定事实。
- 对于证据不足项，必须降级表达（例如“可探索方向”），不得伪装为确定事实。
- `evidence_highlights` 至少包含来源文件与记录定位（`source_file + record_id`，必要时补 `page/row_number`）。
- `negative_prompt_*` 应包含结构性禁用词：穿模、悬空无支撑、错位装配、违反开合路径、违背材料力学常识。
- 若 `shape_confidence = low`，只收缩图片带来的补充结构细节，不削弱分析已明确支持的产品定义。
- 若分析结果与图片参考冲突，默认以分析结果为主；图片只能触发“收缩描述、降低结构确定性、删除高风险外形猜测”，不能推翻分析结论。
- 未经分析支持的结构，不得因为图片参考而写成确定性提示词。

## 4. 证据分级规则

默认使用以下证据等级：
- `direct`：源文本中明确陈述
- `inferred`：可合理推导但非字面陈述
- `insufficient`：当前样本不足以验证

建议：
- 结论与生成结果应以 `direct` 证据为主
- `inferred` 可用于综合推断，但必须标注
- 当样本不足以支持正向结论或强建议时，使用 `insufficient`

## 5. 跨来源综合规则

混合多来源分析时：
- 通过共享分析维度对齐，不是抹平来源差异
- 在汇总与附录中保留来源归因
- 标注样本量、时效性、信息密度不对称
- 不要强行比较本不具可比性的文档或渠道

## 6. 交付前检查

在宣告完成前，确保分析能清楚回答：
- 分析了什么
- 如何编码
- 最强重复模式是什么
- 这些模式出现在哪里
- 应采取什么行动
- 证据如何支撑描述与提示词
- 形态校准是否基于可靠商品图片形成了稳定共识
- 低置信度时是否已经执行了保守降级
- 生图提示词是否通过物理结构检查（部件完整性、连接可行性、受力逻辑、运动学约束）

若上述问题不能清晰回答，即便解析成功，流程仍未完成。

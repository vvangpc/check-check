# ⚙️ Check-Check 源代码核心架构一览

本项目的 `src/` 目录包含了驱动专利形式审查的所有业务逻辑。我们将功能解耦为三层：

## 1. 文档解析层 (`document_parser.py`)

- **功能**：处理 `.docx`, `.rtf`, `.txt` 文件的异构读取。
- **任务**：利用 NLP 特征（如识别“本发明涉及...”或“权利要求 1.”）自动将文档切割为“权利要求书”与“说明书”两部分。
- **关键函数**：`parse_file(path)`, `split_patent_document(text, requirements)`。

## 2. 逻辑审查层 (`rules_checker.py` & `nlp_engine.py`)

这是项目的核心“中枢系统”。

- **附图标记校验**：识别“异名同号/同名异号”，利用 **最长公共后缀聚类算法 (Longest Common Suffix Clustering)** 规避中文粘连导致的误报。
- **权利要求审查**：
    - 多引用多、引用断层、引用回环。
    - 缺乏前序基础 (Lack of Antecedent Basis)。
    - 引用主题一致性拦截 (Topic Consistency)。
    - 说明书支持验证 (Enablement/Support check)。
- **NLP 引擎**：负责实词提取、术语关系挖掘。

## 3. 配置与基础设施层 (`config.py`)

- **功能**：全局配置中心。
- **热加载**：字典变更后的实时热重载 (Hot Reload) 逻辑。
- **正则预编译**：系统启动时预编译几万行正则，确保搜索性能。

---

## 开发自查清单

如果您要新增审查逻辑，请遵循以下步骤：

1. 在 `rules_checker.py` 的 `checker` 类中定义新的检查方法。
2. 将结果封装为标准的 `issue` 字典格式（包含 `text`, `type`, `span`, `target`）。
3. 如果需要新的字典支持，请在 `config.py` 中增加相应的路径和加载函数。

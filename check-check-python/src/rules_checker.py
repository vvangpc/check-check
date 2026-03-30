from src.config import config

class RulesChecker:
    def check_sensitive_words(self, text):
        """扫描全文明感词和残破词汇（例如‘大概’、‘最好是’、‘权利要’）"""
        issues = []
        if config.minganci_regex and text:
            for match in config.minganci_regex.finditer(text):
                issues.append({
                    "type": "形式异常/敏感词",
                    "word": match.group(),
                    "position": match.span()
                })
        return issues
        
    def check_collocation_structures(self, text):
        """寻找特征组件间的装配与位置关系，抽离拓扑"""
        structures = []
        if config.gudingdapei_regex and text:
            for match in config.gudingdapei_regex.finditer(text):
                structures.append({
                    "relation": match.group(0),
                    "components": match.groups()
                })
        return structures
        
    def analyze_patent(self, claims_text, specs_text):
        """综合分析：汇总缺陷报告，并提供结构化错误供GUI高亮和跳转使用"""
        report = []
        issues = [] # 保存提供给界面跳转的元信息
        
        # 1. 扫描权利要求中的敏感词/缺陷
        claims_issues = self.check_sensitive_words(claims_text)
        if claims_issues:
            for issue in claims_issues:
                msg = f"[级别: 确定错误] 权利要求使用了不规范限定或遗漏词：【{issue['word']}】"
                report.append(msg)
                issues.append({
                    "text": msg,
                    "type": "claims_error",
                    "span": issue['position']
                })
                
        # 2. 说明书部分：取消敏感词/形缺审查，因为说明书允许使用“等、大致、特别的”
        # 原有的 specs_issues 扫描段落被移除
                
        # 3. 抽取权利要求的固定组合关系，验证说明书中是否出现（“缺少说明书支持”检查）
        c_structures = self.check_collocation_structures(claims_text)
        import re
        for st in c_structures:
            # st['components'] 是根据正则捕获的一串名词组合
            for component in st['components']:
                if component and component not in specs_text:
                    msg = f"[级别: 可以错误/缺乏支持] 权利要求中的特征【{component}】未在说明书中找到关联支持！"
                    report.append(msg)
                    # 在权利要求中定位该词，供高亮使用
                    try:
                        match = re.search(re.escape(component), claims_text)
                        if match:
                            issues.append({
                                "text": msg,
                                "type": "claims_warning",
                                "span": match.span(),
                                "word": component
                            })
                    except Exception:
                        pass

        if not report:
            report.append("恭喜！未在本文档中检测到明显的形缺问题。")
            
        return report, issues

checker = RulesChecker()

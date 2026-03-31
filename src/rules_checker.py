import re
from src.config import config

class RulesChecker:
    def __init__(self):
        self.pat_claims_split = re.compile(r'^(\d+)[\.、]\s*(.*)', re.MULTILINE)
        self.pat_dep_general = re.compile(r'根据权利要求([\d~、和及到了或\-\s至]+)(?:中任一项)?所述')
        self.pat_dep_title = re.compile(r'根据权利要求[\d~、和及到了或\-\s至]+(?:中任一项)?所述的?\s*([^，,。]+)')
        # 附图标记正则：匹配"部件名 + 数字"，但排除数字后紧跟单位的情况
        # 排除：度、°、%、‰、mm、cm、m、kg、g、Hz、rpm 等物理量单位，避免误匹配"旋转90度"
        self.pat_ref_nums = re.compile(
            r'([\u4e00-\u9fa5]{2,})\s*([\(（]?)\s*(\d+[a-zA-Z]?)(?!\d|[a-zA-Z])\s*([\)）]?)'
            r'(?![\s]*[度°℃℉%‰ⅢⅣⅤmmcmkgmsMHzrpmμnpσ个条项步次轮圈周倍节段级层组道])'
        )
        self.pat_antecedent = re.compile(r'(所述|该)([\u4e00-\u9fa5]{2,10})')

        
    def _has_cycle(self, num, claims_dict, visited=None):
        if visited is None: visited = set()
        if num in visited: return True
        visited.add(num)
        for parent in claims_dict.get(num, {}).get('deps', []):
            if self._has_cycle(parent, claims_dict, visited.copy()):
                return True
        return False
        
    def _get_ancestors(self, curr, claims_dict, ancestors=None):
        if ancestors is None: ancestors = set()
        if curr in claims_dict:
            for p in claims_dict.get(curr, {}).get('deps', []):
                if p not in ancestors:
                    ancestors.add(p)
                    self._get_ancestors(p, claims_dict, ancestors)
        return ancestors

    def check_typos(self, text, target_name):
        """检查重复输入的多字或漏字错误 (AA, ABAB, ABCABC等)"""
        issues = []
        if not text: return issues
        
        valid_aa = {"各个", "往往", "仅仅", "种种", "渐渐", "常常", "一一", "微微", "稍稍", "慢慢", "纷纷", "明明", "隐隐", "区区", "丝丝", "频频", "恰恰", "孜孜", "源源", "处处", "人人", "天天", "年年", "岁岁", "时时", "事事", "步步", "条条", "行行", "多多", "久久", "早早", "层层", "阵阵", "端端", "太太", "刚刚", "些些", "声声", "大大", "小小", "高高", "低低", "长长", "短短", "纷纷"}
        
        # 匹配长度为1到15的连续重复。限定最大长度防止跨段落超长匹配引起的性能问题。
        for match in re.finditer(r'([a-zA-Z0-9\u4e00-\u9fa5]{1,15})\1', text):
            repeated_str = match.group(1)
            full_str = match.group(0)
            
            # 过滤1: 纯英文或数字的连续（如 AABB, 1122, 1111），通常是产品型号或引用标号，予以放行
            if not re.search(r'[\u4e00-\u9fa5]', full_str):
                continue
                
            if len(repeated_str) == 1:
                # 过滤2: 针对连续单字 (AA) 的合法叠词
                if full_str in valid_aa:
                    continue
                issues.append({
                    "type": "claims_warning",
                    "word": full_str,
                    "span": match.span(),
                    "target": target_name,
                    "text": f"字词冗余警告：检测到连续的相同字【{full_str}】，请复查是否存在多字漏字或书写错误！"
                })
            else:
                # 针对多字连续重复 (ABAB, ABCABC等)
                issues.append({
                    "type": "claims_warning",
                    "word": full_str,
                    "span": match.span(),
                    "target": target_name,
                    "text": f"字词冗余警告：检测到短语被连续重复输入【{full_str}】(重复了'{repeated_str}')，请复查是否粘贴多余！"
                })
        return issues
        
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

    def _check_claim_dependencies(self, claims_text):
        issues = []
        report = []
        
        claims_dict = {} 
        
        matches = list(self.pat_claims_split.finditer(claims_text))
        
        for i in range(len(matches)):
            m = matches[i]
            claim_num = int(m.group(1))
            start_pos = m.start()
            if i + 1 < len(matches):
                end_pos = matches[i+1].start()
            else:
                end_pos = len(claims_text)
                
            claim_text = claims_text[start_pos:end_pos]
            claims_dict[claim_num] = {
                "text": claim_text,
                "start": start_pos,
                "end": end_pos,
                "deps": [] 
            }
        
        for num, data in claims_dict.items():
            text = data['text']
            dep_match_general = self.pat_dep_general.search(text)
            if dep_match_general:
                dep_str = dep_match_general.group(1).strip()
                
                if "和" in dep_str:
                    msg = f"形式要求：权利要求 {num} 引用了多项权利要求，引用词应当使用“或”而不是“和”！"
                    report.append(msg)
                    issues.append({
                        "text": msg, "type": "claims_error",
                        "span": (data["start"] + dep_match_general.start(1), data["start"] + dep_match_general.end(1)),
                        "target": "claims"
                    })
                    
                nums_str = re.findall(r'\d+', dep_str)
                deps = [int(n) for n in nums_str]
                
                range_matches = re.finditer(r'(\d+)\s*[~到\-至]\s*(\d+)', dep_str)
                for rm in range_matches:
                    start_n = int(rm.group(1))
                    end_n = int(rm.group(2))
                    if start_n < end_n:
                        deps.extend(list(range(start_n, end_n + 1)))
                
                data['deps'] = sorted(list(set(deps)))
                
                # 主题名称一致性检查
                dep_title_match = self.pat_dep_title.search(text)
                if dep_title_match and data['deps']:
                    dep_title = dep_title_match.group(1).strip()
                    if dep_title not in ["其特征在于", "装置", "方法"]: # 过滤一些异常或省略的写法
                        parent_num = data['deps'][0]
                        if parent_num in claims_dict:
                            parent_text = claims_dict[parent_num]['text']
                            ptm = re.match(r'^\d+[\.、]\s*([^，,。]+)', parent_text)
                            if ptm:
                                p_raw = ptm.group(1).strip()
                                p_dep_m = re.match(r'^根据权利要求[\d~、和及到了或\-\s至]+(?:中任一项)?所述的?\s*(.+)', p_raw)
                                if p_dep_m:
                                    p_title = p_dep_m.group(1).strip()
                                else:
                                    p_title = p_raw
                                    
                                p_short = p_title[2:] if p_title.startswith("一种") else p_title
                                
                                if dep_title not in [p_title, p_short]:
                                    msg = f"权利要求主题名称不一致：权利要求 {num} 引用了【{dep_title}】，但被引用的权利要求 {parent_num} 主题为【{p_title}】！"
                                    report.append(msg)
                                    issues.append({
                                        "text": msg, "type": "claims_error",
                                        "span": (data["start"] + dep_title_match.start(1), data["start"] + dep_title_match.end(1)),
                                        "target": "claims"
                                    })
                
        multi_claims = set()
        for num, data in claims_dict.items():
            if len(data['deps']) > 1:
                multi_claims.add(num)
                
        for num, data in claims_dict.items():
            deps = data['deps']
            is_multi = len(deps) > 1
            
            # 1. 多项从属权利要求作为另一项多项从属权利要求的基础 （多引多）
            if is_multi:
                for d in deps:
                    if d in multi_claims:
                        msg = f"多引多违规：多项从属权利要求 {num} 引用了另一项多项从属权利要求 {d}！"
                        report.append(msg)
                        issues.append({
                            "text": msg, "type": "claims_error",
                            "span": (data["start"], data["end"])
                        })
                        
            # 2. 跳项引用检查
            for d in deps:
                if d >= num:
                    msg = f"跳项引用违规：权利要求 {num} 不能引用其自身或其后的权利要求 {d}！"
                    report.append(msg)
                    issues.append({
                        "text": msg, "type": "claims_error",
                        "span": (data["start"], data["end"])
                    })
                    
            # 3. 闭环检查
            if self._has_cycle(num, claims_dict):
                 msg = f"死循环引用违规：权利要求 {num} 存在死循环引用关系！"
                 report.append(msg)
                 issues.append({
                     "text": msg, "type": "claims_error",
                     "span": (data["start"], data["end"])
                 })
                     
        return report, issues, claims_dict

    def _check_reference_numerals(self, claims_text, specs_text):
        issues = []
        report = []
        
        name_to_nums = {}
        num_to_names = {}
        
        # Bug fix 2: 排除不应被视为附图标记的上下文词（如"实施例1"、"附图1"）
        exclude_words = ["权利要求", "项", "第", "步骤", "图", "为", "是", "说明书",
                         "实施例", "附图", "如图", "参图", "见图"]
        
        # Bug fix 1: 提取部件名时去除前置的语境词（连词/介词/指示词），只保留真实的部件名核心
        # 例: "下端通过弹簧平衡器" → "弹簧平衡器", "所述弹簧平衡器" → "弹簧平衡器"
        def clean_name(raw_name):
            """将捕获的冗长前缀上下文剥离，提取最短的真实部件名。"""
            # 按长度从长到短尝试剥离，防止短前缀遮蔽长前缀
            leading_context = [
                '上的穿线孔后与', '的下端通过', '的上端通过', '另一端与所述',
                '进而通过', '以通过', '并通过', '再通过', '经由',
                '下端通过', '上端通过', '端通过', '一端通过', '两端通过',
                '通过', '经过', '穿过', '作用在', '连接在', '固定在',
                '安装在', '设置在', '而在', '并且与', '另一端与',
                '作用在', '一端与', '两端与', '且与', '并与',
                '中的', '上的', '下的', '端的',
                '所述', '该', '此', '本',
                '和', '与', '或', '而', '并', '在',
            ]
            name = raw_name
            for prefix in sorted(leading_context, key=len, reverse=True):
                if name.startswith(prefix) and len(name) > len(prefix):
                    name = name[len(prefix):]
                    break  # 只去一次前缀，然后递归处理剩余（防止反复剥离丢失信息）
            # 递归处理：有时前缀剥完还剩指示词
            if name != raw_name and len(name) >= 2:
                name = clean_name(name)
            return name.strip()
        
        for match in self.pat_ref_nums.finditer(claims_text):
            raw_name = match.group(1)
            name = clean_name(raw_name)     # ← 清洗前置语境
            left_bracket = match.group(2)
            num = match.group(3)
            right_bracket = match.group(4)
            
            is_excluded = any(ex_word in name for ex_word in exclude_words)
            if is_excluded: continue
            
            if not left_bracket or not right_bracket:
                msg = f"形式要求：权利要求中附图标记未完全带括号：【{name}{left_bracket}{num}{right_bracket}】，建议修改为【{name}({num})】"
                report.append(msg)
                issues.append({
                    "text": msg, "type": "claims_warning",
                    "span": match.span(), "word": match.group()
                })
                
            name_to_nums.setdefault(name, set()).add(num)
            num_to_names.setdefault(num, set()).add(name)
            
        for match in self.pat_ref_nums.finditer(specs_text):
            name = clean_name(match.group(1))   # ← 同样清洗说明书侧
            num = match.group(3)
            is_excluded = any(ex_word in name for ex_word in exclude_words)
            if is_excluded: continue
            name_to_nums.setdefault(name, set()).add(num)
            num_to_names.setdefault(num, set()).add(name)
            
        def unify_names(names_set):
            if not names_set: return []
            cores = set(names_set)
            
            # --- 危险修饰词强制隔离机制（防止"第一齿轮"与"第二齿轮"被合并） ---
            if len(names_set) > 1:
                distinguish_words = ["第一", "第二", "第三", "第四", "第五", "第六",
                                     "左", "右", "前", "后", "上", "下", "主", "副", "内", "外"]
                found_flags = set()
                for name in names_set:
                    for dw in distinguish_words:
                        if dw in name:
                            found_flags.add(dw)
                            break
                if len(found_flags) > 1:
                    return list(names_set)
            
            changed = True
            while changed and len(cores) > 1:
                changed = False
                core_list = list(cores)
                for i in range(len(core_list)):
                    for j in range(i+1, len(core_list)):
                        c1 = core_list[i]
                        c2 = core_list[j]
                        lcs = ""
                        min_len = min(len(c1), len(c2))
                        for k in range(1, min_len + 1):
                            if c1[-k:] == c2[-k:]:
                                lcs = c1[-k:]
                            else:
                                break
                        if len(lcs) >= 2 or lcs == c1 or lcs == c2:
                            cores.remove(c1)
                            cores.remove(c2)
                            cores.add(lcs)
                            changed = True
                            break
                    if changed:
                        break
            return list(cores)

        unified_num_to_names = {}
        unified_name_to_nums = {}
        
        for num, names in num_to_names.items():
            unified = unify_names(names)
            unified_num_to_names[num] = unified
            for uname in unified:
                unified_name_to_nums.setdefault(uname, set()).add(num)

        # 异名同号检查（致命）
        for num, unames in unified_num_to_names.items():
            if len(unames) > 1:
                msg = f"附图标记冲突：标号【{num}】关联了多个不同的部件核心名称：{', '.join(unames)}！"
                
                target = "claims"
                span = (0, 0)
                uname = next(iter(unames))
                pattern_str = r'[\u4e00-\u9fa5]*?' + re.escape(uname) + r'\s*[\(（]?\s*' + str(num) + r'[a-zA-Z]?[\)）]?'
                for text, tgt in [(claims_text, "claims"), (specs_text, "specs")]:
                    match = re.search(pattern_str, text)
                    if match:
                        span = match.span()
                        target = tgt
                        break
                        
                report.append(msg)
                issues.append({
                    "text": msg, "type": "claims_error",
                    "span": span, "target": target
                })
                
        # 同名异号检查（跨文与域内警告）
        for uname, nums in unified_name_to_nums.items():
            if len(nums) > 1:
                c_nums = set()
                s_nums = set()
                
                for num in nums:
                    pattern_str = r'[\u4e00-\u9fa5]*?' + re.escape(uname) + r'\s*[\(（]?\s*' + str(num) + r'[a-zA-Z]?[\)）]?'
                    if re.search(pattern_str, claims_text): c_nums.add(num)
                    if re.search(pattern_str, specs_text): s_nums.add(num)
                
                if c_nums and s_nums and not c_nums.intersection(s_nums):
                    msg = f"编号跨文不一致：【{uname}】在权利要求中使用的标号为 {', '.join(c_nums)}，但在说明书中变为了 {', '.join(s_nums)}！请仔细核对！"
                else:
                    msg = f"部件编号不一：部件核心【{uname}】关联了多种标号：{', '.join(nums)}！"
                
                target = "claims"
                span = (0, 0)
                num_iter = next(iter(nums))
                pattern_str = r'[\u4e00-\u9fa5]*?' + re.escape(uname) + r'\s*[\(（]?\s*' + str(num_iter) + r'[a-zA-Z]?[\)）]?'
                for text, tgt in [(claims_text, "claims"), (specs_text, "specs")]:
                    match = re.search(pattern_str, text)
                    if match:
                        span = match.span()
                        target = tgt
                        break
                        
                report.append(msg)
                issues.append({
                    "text": msg, "type": "claims_error" if (c_nums and s_nums and not c_nums.intersection(s_nums)) else "claims_warning",
                    "span": span, "target": target
                })

        return report, issues

    def _check_antecedent_basis(self, claims_text, claims_dict):
        issues = []
        report = []
        
        # 记录已经出现过的词，如果词已经找过了就不必重复找，减轻由于错误造成的满屏红
        reported = set()
        
        for num, data in claims_dict.items():
            text = data['text']
            start_offset = data['start']
            
            for match in self.pat_antecedent.finditer(text):
                word = match.group(2)
                
                if word.startswith("的"):
                    word = word[1:]
                    
                if word in ["发明", "权利要求", "特征", "方法", "系统", "装置", "步骤", "其", "其余", "其它", "其他", "上述"]: 
                    continue
                
                ancestors = self._get_ancestors(num, claims_dict)
                
                search_pool = ""
                for a in sorted(list(ancestors)):
                    if a in claims_dict:
                        search_pool += claims_dict[a]['text'] + "\n"
                        
                search_pool += text[:match.start()]
                
                found_basis = False
                max_check_len = min(6, len(word))
                for length in range(max_check_len, 1, -1):
                    test_word = word[:length]
                    if test_word in search_pool:
                        found_basis = True
                        break
                
                if not found_basis:
                    # 这意味着没有以“一种XXX”或者“XXX”的形式出现过
                    display_word = word[:6] + "..." if len(word) > 6 else word
                    msg_key = f"{num}-{display_word}"
                    if msg_key not in reported:
                        msg = f"缺乏前序基础：权利要求 {num} 出现了“{match.group()}”，但在其前序依赖中未找到“{display_word}”的基础声明！"
                        report.append(msg)
                        issues.append({
                            "text": msg, "type": "claims_error",
                            "span": (start_offset + match.start(), start_offset + match.end()),
                            "word": match.group()
                        })
                        reported.add(msg_key)
                    
        return report, issues
        
    def analyze_patent(self, claims_text, specs_text):
        """综合分析：汇总缺陷报告，并提供结构化错误供GUI高亮和跳转使用"""
        report = []
        issues = []
        
        # 0. 扫描错字 / 多字 / 冗余字
        for text, tgt in [(claims_text, "claims"), (specs_text, "specs")]:
            typo_issues = self.check_typos(text, tgt)
            if typo_issues:
                for issue in typo_issues:
                    report.append(issue["text"])
                    issues.append(issue)
        
        # 1. 扫描权利要求中的敏感词/缺陷
        claims_issues = self.check_sensitive_words(claims_text)
        if claims_issues:
            for issue in claims_issues:
                msg = f"权利要求使用了不规范限定或遗漏词：【{issue['word']}】"
                report.append(msg)
                issues.append({
                    "text": msg,
                    "type": "claims_error",
                    "span": issue['position'],
                    "target": "claims"
                })
                
        # 2. 增强检查
        
        # 2.1 引用关系
        dep_report, dep_issues, claims_dict = self._check_claim_dependencies(claims_text)
        report.extend(dep_report)
        issues.extend(dep_issues)
        
        # 2.2 前序基础
        ant_report, ant_issues = self._check_antecedent_basis(claims_text, claims_dict)
        report.extend(ant_report)
        issues.extend(ant_issues)
        
        # 2.3 附图标记
        ref_report, ref_issues = self._check_reference_numerals(claims_text, specs_text)
        report.extend(ref_report)
        issues.extend(ref_issues)
                
        # 2.4 说明书附图审查
        fig_report, fig_issues = self._check_figures_in_specs(specs_text)
        report.extend(fig_report)
        issues.extend(fig_issues)
                
        # 3. 抽取权利要求的固定组合关系，验证说明书中是否出现（“缺少说明书支持”检查）
        c_structures = self.check_collocation_structures(claims_text)
        for st in c_structures:
            for component in st['components']:
                if component:
                    # 检查说明书是否支持（包含同义词检查）
                    is_supported = False
                    if component in specs_text:
                        is_supported = True
                    else:
                        # 查找同义词
                        synonyms = config.synonyms_dict.get(component, [])
                        for syn in synonyms:
                            if syn in specs_text:
                                is_supported = True
                                break
                    
                    if not is_supported:
                        msg = f"缺乏支持：权利要求中的特征【{component}】未在说明书中找到关联支持（含同义词检索）！"
                        report.append(msg)
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
        
    def _check_figures_in_specs(self, specs_text):
        issues = []
        report = []
        
        desc_start = specs_text.find("附图说明")
        if desc_start == -1:
            desc_start = specs_text.find("附 图 说 明")
            
        impl_start = specs_text.find("具体实施方式")
        if impl_start == -1:
            impl_start = specs_text.find("具体实施例")
            
        if desc_start != -1 and impl_start != -1 and desc_start < impl_start:
            desc_text = specs_text[desc_start:impl_start]
            impl_text = specs_text[impl_start:]
            
            figures_in_desc = set(re.findall(r'图\s*\d+[a-zA-Z]?', desc_text))
            
            for fig in figures_in_desc:
                norm_fig = fig.replace(" ", "")
                num_part = re.search(r'\d+[a-zA-Z]?', fig).group()
                pattern = r'图\s*' + num_part + r'(?![0-9a-zA-Z])'
                
                if not re.search(pattern, impl_text):
                    msg = f"附图说明遗漏：说明书中描述了【{norm_fig}】，但在具体实施方式中未找到对该图的具体引用！"
                    report.append(msg)
                    
                    match = re.search(pattern, desc_text)
                    span = (0, 0)
                    if match:
                        span = (desc_start + match.start(), desc_start + match.end())
                        
                    issues.append({
                        "text": msg, "type": "claims_error",
                        "span": span, "target": "specs"
                    })
                    
            # 实施方式反向核对
            figures_in_impl = set(re.findall(r'图\s*\d+[a-zA-Z]?', impl_text))
            for fig in figures_in_impl:
                norm_fig = fig.replace(" ", "")
                num_part = re.search(r'\d+[a-zA-Z]?', fig).group()
                pattern = r'图\s*' + num_part + r'(?![0-9a-zA-Z])'
                
                if not re.search(pattern, desc_text):
                    msg = f"附图说明遗漏：具体实施方式中引用了【{norm_fig}】，但在附图说明段落中却未进行介绍！"
                    report.append(msg)
                    
                    match = re.search(pattern, impl_text)
                    span = (0, 0)
                    if match:
                        span = (impl_start + match.start(), impl_start + match.end())
                        
                    issues.append({
                        "text": msg, "type": "claims_error",
                        "span": span, "target": "specs"
                    })
        return report, issues

checker = RulesChecker()

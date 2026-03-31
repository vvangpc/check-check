import os
import re
import docx
from striprtf.striprtf import rtf_to_text

def parse_file(file_path):
    """解析 .docx, .rtf 或 .txt 文件并返回纯文本"""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == '.docx':
        doc = docx.Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
    elif ext == '.rtf':
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()
            text = rtf_to_text(content)
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            text = f.read()
    else:
        raise ValueError("不支持的文件格式，请上传 .docx, .rtf 或 .txt 文件")
    return text

def flexible_match(pattern_str, text):
    """将用户输入的包含 XXX 或 * 的锚点字符串转换为正则并匹配"""
    if not pattern_str:
        return None
        
    pattern_str = pattern_str.strip()
    # 使用 X, x, * 作为通配符
    parts = re.split(r'[Xx*]+', pattern_str)
    escaped_parts = [re.escape(p) for p in parts]
    regex_pattern = '.*?'.join(escaped_parts)
    
    # 容错处理：全半角空格一致化，处理 1. 与 1、 的混用
    regex_pattern = regex_pattern.replace(r'\ ', r'\s*')
    regex_pattern = regex_pattern.replace(r'1\.', r'1[.\u3001]\s*')
    
    return re.search(regex_pattern, text, flags=re.DOTALL)


def flexible_match_heading(pattern_str, text):
    """
    专门用于匹配独立标题行（如"技术领域"）的变体。
    要求该关键词独占一行，防止摘要段落中嵌入的同名词语被误识别为说明书起点。
    """
    if not pattern_str:
        return None

    pattern_str = pattern_str.strip()
    parts = re.split(r'[Xx*]+', pattern_str)
    escaped_parts = [re.escape(p) for p in parts]
    core_pattern = '.*?'.join(escaped_parts)
    core_pattern = core_pattern.replace(r'\\ ', r'\\s*')
    core_pattern = core_pattern.replace(r'1\\.', r'1[.\\u3001]\\s*')

    # 关键升级：要求该关键词独占一整行（行首 + 关键词 + 行尾）
    # 这样摘要段落内部包含的"技术领域"就不会被误匹配
    heading_pattern = r'(?:^|\n)[ \t]*' + core_pattern + r'[ \t]*(?:\n|$)'
    return re.search(heading_pattern, text, flags=re.MULTILINE)


def split_patent_document(text, reqs=None):
    """
    根据关键字和设定对整篇专利文档进行自动分割。
    返回: {'claims': 权利要求内容, 'specification': 说明书内容}
    """
    if not reqs:
        reqs = {
            "claims_start": "1. 一种",
            "specs_start": "技术领域",
            "specs_end": "在上述发明的基础上还可以做出其它变化或变型，并且这些变化或变型仍处于本发明的范围内。"
        }
        
    claims = ""
    specification = ""
    
    text = text.replace('\r\n', '\n')
    
    claims_start_str = reqs.get("claims_start", "")
    specs_start_str = reqs.get("specs_start", "")
    specs_end_str = reqs.get("specs_end", "")
    
    c_match = flexible_match(claims_start_str, text)
    # 说明书开头必须是独立标题行，防止摘要中嵌入的相同词被误匹配
    s_match = flexible_match_heading(specs_start_str, text)
    e_match = flexible_match(specs_end_str, text)
    
    claims_start_idx = c_match.start() if c_match else -1
    # heading 匹配时，match.start() 可能包含前置换行符，需跳过非标题字符
    if s_match:
        # 找到匹配行内的关键词真实起始位置（跳过行首空白）
        specs_start_idx = s_match.start()
        # 如果匹配开头是换行符，往前移一位让起点指向内容行
        matched_text = text[specs_start_idx:]
        leading_newline = len(matched_text) - len(matched_text.lstrip('\n'))
        specs_start_idx += leading_newline
    else:
        specs_start_idx = -1
    
    if e_match:
        specs_end_idx = e_match.start()
        actual_specs_end = e_match.end()
    else:
        specs_end_idx = -1
        actual_specs_end = len(text)

    # 如果说明书开头找到了，向上回溯寻找真正的说明书起点（专利标题），即上一个非空段落

    if specs_start_idx != -1:
        prefix_text = text[:specs_start_idx].rstrip()
        last_newline_idx = prefix_text.rfind('\n')
        title_idx = last_newline_idx + 1 if last_newline_idx != -1 else 0
        
        # 确保标题没找得太远（例如不超过200字符），否则可能定位到了过于无关的内容
        if specs_start_idx - title_idx < 200:
            specs_start_idx = title_idx

    actual_specs_end = specs_end_idx + len(specs_end_str) if specs_end_idx != -1 else len(text)

    # 判断两者的相对位置
    if claims_start_idx != -1 and specs_start_idx != -1:
        if claims_start_idx < specs_start_idx:
            # 权利要求在前面
            claims = text[claims_start_idx:specs_start_idx].strip()
            specification = text[specs_start_idx:actual_specs_end].strip()
        else:
            # 说明书在前面
            specification = text[specs_start_idx:claims_start_idx].strip()
            # 如果说明书有指定的结尾语句，并且权利要求在结尾语句之后
            if specs_end_idx != -1 and claims_start_idx > specs_end_idx:
                specification = text[specs_start_idx:actual_specs_end].strip()
            claims = text[claims_start_idx:].strip()
            
    elif claims_start_idx != -1:
        # 只找到了权利要求
        claims = text[claims_start_idx:].strip()
    elif specs_start_idx != -1:
        # 只找到了说明书
        specification = text[specs_start_idx:actual_specs_end].strip()

    # 如果由于格式极端无法自动定位，退回空字符串以强制用户手动操作
    if not claims and not specification:
        claims = ""
        specification = ""
        
    return {
        "claims": claims,
        "specification": specification
    }

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

def split_patent_document(text):
    """
    根据关键字和正则对整篇专利文档进行自动分割。
    返回: {'claims': 权利要求内容, 'specification': 说明书内容}
    """
    claims = ""
    specification = ""
    
    text = text.replace('\r\n', '\n')
    
    # 寻找权利要求书的开头：匹配“1.一种XXX，其特征”或“1、一种XXX，其特征”等描述
    claims_start_match = re.search(r'(?:^|\n)\s*1[.\u3001]\s*一种.*?其特征', text, flags=re.DOTALL)
    
    # 寻找说明书的开头：匹配“技术领域”
    specs_start_match = re.search(r'(?:^|\n)\s*技术领域', text)
    
    # 说明书结尾标语
    specs_end_str = "在上述发明的基础上还可以做出其它变化或变型，并且这些变化或变型仍处于本发明的范围内。"
    specs_end_idx = text.find(specs_end_str)

    claims_start_idx = claims_start_match.start() if claims_start_match else -1
    specs_start_idx = specs_start_match.start() if specs_start_match else -1

    # 尝试将截断点规范化（比如说明书开头往前找“一种”作为标题）
    if specs_start_idx != -1:
        title_idx = text.rfind("一种", 0, specs_start_idx)
        if title_idx != -1 and (specs_start_idx - title_idx) < 100:  # 确保标题没找的太远
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
        # 只找到了权利要求，默认后半部分全是权利要求
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

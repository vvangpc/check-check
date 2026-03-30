import jieba
import re
from src.config import config, DICT_USER_PATH

class NLPEngine:
    def __init__(self):
        print("初始化 NLP 引擎（结巴分词）...")
        jieba.initialize()
        try:
            jieba.load_userdict(DICT_USER_PATH)
        except Exception as e:
            print(f"未能成功加载用户字典 {DICT_USER_PATH}: {e}")
            
        self.useless_regex = config.useless_words_regex
        print("NLP 引擎初始化完成！")

    def clean_text(self, text):
        """在分词前去除设定的无用修饰词"""
        if self.useless_regex and text:
            # 去除连词、冗长副词
            return self.useless_regex.sub("", text)
        return text

    def tokenize(self, text):
        """精确分词，返回词组列表"""
        seg_list = jieba.cut(text, cut_all=False)
        return list(seg_list)
        
    def extract_components(self, text):
        """
        利用现有的 `***` 占位符进行逻辑组件名称过滤，通常用于提取关系之间的专有名词
        """
        cleaned = self.clean_text(text)
        tokens = self.tokenize(cleaned)
        # 过滤空白和标点
        tokens = [t.strip() for t in tokens if t.strip()]
        return tokens

nlp = NLPEngine()

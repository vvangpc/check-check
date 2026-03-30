import os
import re

# Base directory for the dictionary rules
# Since the script is in `./src/`, the project root is `../` relative to `__file__`
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(PROJECT_ROOT, "dicts")

DICT_USER_PATH = os.path.join(DICT_DIR, "userdict.txt")
DICT_USELESS_PATH = os.path.join(DICT_DIR, "useless_word.txt")
DICT_MINGANCI_PATH = os.path.join(DICT_DIR, "minganci.txt")
DICT_GUDINGDAPEI_PATH = os.path.join(DICT_DIR, "gudingdapei.txt")
DICT_WEIZHI_PATH = os.path.join(DICT_DIR, "weizhiguanxi.txt")

class ConfigLoader:
    def __init__(self):
        self.useless_words_regex = None
        self.minganci_regex = None
        self.gudingdapei_regex = None
        self.weizhi_regex = None
        self.load_rules()

    def _read_and_compile(self, file_path, replace_stars=False):
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            
            if replace_stars:
                # Replace *** with capturing group for relation extraction
                # Protect special characters before doing so if necessary, but here it's mostly plain text + basic regex
                content = content.replace("***", r"([\u4e00-\u9fa5]+)")
            
            if content:
                try:
                    return re.compile(content)
                except re.error as e:
                    print(f"Error compiling regex in {file_path}: {e}")
                    return None
        return None

    def load_rules(self):
        print("正在加载和预编译规则字典...")
        self.useless_words_regex = self._read_and_compile(DICT_USELESS_PATH)
        self.minganci_regex = self._read_and_compile(DICT_MINGANCI_PATH)
        
        # for these, we convert *** to capturing groups
        self.gudingdapei_regex = self._read_and_compile(DICT_GUDINGDAPEI_PATH, replace_stars=True)
        self.weizhi_regex = self._read_and_compile(DICT_WEIZHI_PATH, replace_stars=True)
        print("规则字典加载完毕！")

# Singleton instance
config = ConfigLoader()

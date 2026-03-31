import sys
import os
import re
import shutil

# 处理打包后的路径加载逻辑
def get_project_root():
    """获取程序运行根目录（如果是 exe 则返回 exe 目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """获取捆绑在 exe 内部的文件路径（fallback）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = get_project_root()
    return os.path.join(base_path, relative_path)

PROJECT_ROOT = get_project_root()
# 优先寻找同级外部文件夹 dicts，找不到再使用内置的
EXTERNAL_DICT_DIR = os.path.join(PROJECT_ROOT, "dicts")
INTERNAL_DICT_DIR = get_resource_path("dicts")

if os.path.isdir(EXTERNAL_DICT_DIR):
    DICT_DIR = EXTERNAL_DICT_DIR
else:
    DICT_DIR = INTERNAL_DICT_DIR

DICT_USER_PATH = os.path.join(DICT_DIR, "userdict.txt")
DICT_USELESS_PATH = os.path.join(DICT_DIR, "useless_word.txt")
DICT_MINGANCI_PATH = os.path.join(DICT_DIR, "minganci.txt")
DICT_GUDINGDAPEI_PATH = os.path.join(DICT_DIR, "gudingdapei.txt")
DICT_WEIZHI_PATH = os.path.join(DICT_DIR, "weizhiguanxi.txt")
DICT_SYNONYMS_PATH = os.path.join(DICT_DIR, "synonyms.txt")

def ensure_external_dicts():
    """保证存在外部 dicts 文件夹，如果是在打包环境且不存在，则从内部解压过去"""
    global DICT_DIR, DICT_USER_PATH, DICT_USELESS_PATH, DICT_MINGANCI_PATH, DICT_GUDINGDAPEI_PATH, DICT_WEIZHI_PATH, DICT_SYNONYMS_PATH
    
    if os.path.isdir(EXTERNAL_DICT_DIR):
        return True
        
    try:
        if os.path.exists(INTERNAL_DICT_DIR):
            shutil.copytree(INTERNAL_DICT_DIR, EXTERNAL_DICT_DIR)
            
            # 更新全局路径为主机外部路径
            DICT_DIR = EXTERNAL_DICT_DIR
            DICT_USER_PATH = os.path.join(DICT_DIR, "userdict.txt")
            DICT_USELESS_PATH = os.path.join(DICT_DIR, "useless_word.txt")
            DICT_MINGANCI_PATH = os.path.join(DICT_DIR, "minganci.txt")
            DICT_GUDINGDAPEI_PATH = os.path.join(DICT_DIR, "gudingdapei.txt")
            DICT_WEIZHI_PATH = os.path.join(DICT_DIR, "weizhiguanxi.txt")
            DICT_SYNONYMS_PATH = os.path.join(DICT_DIR, "synonyms.txt")
            return True
    except Exception as e:
        print(f"创建外部字典目录失败: {e}")
        return False
    return False




class ConfigLoader:
    def __init__(self):
        self.useless_words_regex = None
        self.minganci_regex = None
        self.gudingdapei_regex = None
        self.weizhi_regex = None
        self.synonyms_dict = {}
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
        self.load_synonyms()
        print("规则字典加载完毕！")

    def load_synonyms(self):
        self.synonyms_dict = {}
        if os.path.exists(DICT_SYNONYMS_PATH):
            try:
                with open(DICT_SYNONYMS_PATH, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        # 每一行以逗号分隔，例如：螺丝,螺钉,紧固件
                        words = [w.strip() for w in line.strip().split(',') if w.strip()]
                        for word in words:
                            self.synonyms_dict[word] = words # 将每个词映射到它的整个同义词列表
            except Exception as e:
                print(f"加载同义词字典出错: {e}")


# Singleton instance
config = ConfigLoader()

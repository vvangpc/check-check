#encoding: utf-8
import sys
sys.path.append(r"e:\check-check")
from src.config import config

text = "最大等级"
# find sensitive words
from src.rules_checker import checker
print(checker.check_sensitive_words(text))

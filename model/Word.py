import re
import json
from threading import Lock
from collections import Counter
from collections import OrderedDict

import tiktoken
import tiktoken_ext
from tiktoken_ext import openai_public

from helper.LogHelper import LogHelper
from helper.TextHelper import TextHelper

class Word:

    TYPE_NOT_PERSON = -20
    TYPE_NEED_CONFIRM = -10
    TYPE_UNKNOWN = 0
    TYPE_PERSON = 10

    CONTEXT_CACHE = {}
    CONTEXT_CACHE_LOCK = Lock()
    CONTEXT_TOKEN_THRESHOLD = 768

    def __init__(self):
        self.type = self.TYPE_UNKNOWN
        self.count = 0
        self.context = []
        self.context_summary = {}
        self.context_translation = []
        self.surface = ""
        self.surface_romaji = ""
        self.surface_translation = ["", ""]
        self.surface_translation_description = ""
        self.attribute = ""
        self.llmresponse = ""

        self.tiktoken_encoding = tiktoken.get_encoding("cl100k_base")

    def __str__(self):
        return (
            f"Word(type={self.type},"
            f"count={self.count},"
            f"context={self.context},"
            f"context_summary={self.context_summary},"
            f"context_translation={self.context_translation},"
            f"surface={self.surface},"
            f"surface_romaji={self.surface_romaji},"
            f"surface_translation={self.surface_translation},"
            f"surface_translation_description={self.surface_translation_description},"
            f"attribute={self.attribute},"
            f"llmresponse={self.llmresponse})"
        )

    # 从原文中提取上下文
    def set_context(self, surface, original):
        if surface in Word.CONTEXT_CACHE:
            with self.CONTEXT_CACHE_LOCK:
                self.context = Word.CONTEXT_CACHE.get(surface)
        else:
            # 匹配原文，并且移除行内换行
            matches = [re.sub(r'[\r\n]+', '', line.strip()) for line in original if surface in line]
            
            # 使用OrderedDict去除重复并保持顺序
            unique_matches = list(OrderedDict.fromkeys(matches))
            
            # 按长度降序排序
            unique_matches.sort(key=lambda x: (-len(self.tiktoken_encoding.encode(x)), x))

            # 在阈值范围内取 Token 最长的条数
            context = []
            context_length = 0
            for k, line in enumerate(unique_matches):
                line_lenght = len(self.tiktoken_encoding.encode(line))

                if context_length + line_lenght > self.CONTEXT_TOKEN_THRESHOLD:
                    break

                context.append(line)
                context_length = context_length + line_lenght

            self.context = context

            # 将结果保存到缓存中
            with self.CONTEXT_CACHE_LOCK:
                Word.CONTEXT_CACHE[surface] = context

    # 按长度截取上下文并返回
    def clip_context(self, threshold):
        context = []
        context_length = 0
        for k, line in enumerate(self.context):
            line_lenght = len(self.tiktoken_encoding.encode(line))

            if context_length + line_lenght > threshold:
                break

            context.append(line)
            context_length = context_length + line_lenght

        return context

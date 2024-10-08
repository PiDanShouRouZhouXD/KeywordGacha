import os
import re
import csv
import copy
import json
import asyncio

import rich
from rich import box
from rich.table import Table
from rich.prompt import Prompt

from model.LLM import LLM
from model.NER import NER
from model.Word import Word
from helper.LogHelper import LogHelper
from helper.TestHelper import TestHelper
from helper.TextHelper import TextHelper
from helper.ProgressHelper import ProgressHelper

# 定义全局对象
# 方便共享全局数据
# 丑陋，但是有效，不服你咬我啊
G = type("GClass", (), {})()

# 读取 .txt 文件
def read_txt_file(file_path):
    lines = []
    names = []
    encodings = ["utf-8", "utf-16", "shift-jis"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding = encoding) as file:
                return file.readlines(), []
        except UnicodeDecodeError as e:
            LogHelper.debug(f"使用 {encoding} 编码读取数据文件时发生错误 - {e}")
        except Exception as e:
            LogHelper.error(f"读取数据文件时发生错误 - {LogHelper.get_trackback(e)}")
            break

    return lines, names

# 读取 .csv 文件
def read_csv_file(file_path):
    lines = []
    names = []

    try:
        with open(file_path, "r", newline = "", encoding = "utf-8") as file:
            reader = csv.reader(file)

            for row in reader:
                lines.append(row[0])         
    except Exception as e:
        LogHelper.error(f"读取数据文件时发生错误 - {LogHelper.get_trackback(e)}")

    return lines, names

# 读取 .json 文件
def read_json_file(file_path):
    lines = []
    names = []

    try:
        # 读取并加载JSON文件
        with open(file_path, "r", encoding = "utf-8") as file:
            datas = json.load(file)

            # 针对 MTool 导出文本
            # {
            #   "「お前かよ。開けて。着替えなきゃ」" : "「お前かよ。開けて。着替えなきゃ」"
            # }
            if isinstance(datas, dict):
                for k, v in datas.items():
                    if isinstance(k, str) and isinstance(v, str):
                        lines.append(k)

            # 针对 SExtractor 导出的带name字段JSON数据
            # [{
            #   "name": "少年",
            #   "message": "「お前かよ。開けて。着替えなきゃ」"
            # }]
            if isinstance(datas, list):
                for data in datas:
                    name = data.get("name", "").strip()
                    if isinstance(name, str) and name != "":
                        names.append(name)
                    
                    message = data.get("message", "").strip()
                    if isinstance(message, str) and message != "":
                        lines.append(message)
    except Exception as e:
        LogHelper.error(f"读取数据文件时发生错误 - {LogHelper.get_trackback(e)}")

    return lines, names

# 读取数据文件
def read_input_file():
    # 先尝试自动寻找数据文件，找不到提示用户输入
    file_path = ""

    num = 0
    if os.path.exists(".\\input") and os.path.isdir(".\\input"):
        for entry in os.scandir(".\\input"):
            if entry.is_file() and entry.name.endswith(".txt"):
                num = num + 1
            elif entry.is_file() and entry.name.endswith(".csv"):
                num = num + 1
            elif entry.is_file() and entry.name.endswith(".json"):
                num = num + 1

    if num > 0:
        user_input = LogHelper.input(f"已在 [green].\\input[/] 路径下找到数据文件 {num} 个，按回车直接使用或输入其他文件路径：").strip('"')
        file_path = user_input if user_input else ".\\input"
    
    if file_path == "":
        file_path = LogHelper.input(f"请输入数据文件的路径: ").strip('"')

    G.config.input_file_path = file_path

    # 开始读取数据
    input_lines = []
    input_names = []
    if file_path.endswith(".txt"):
        input_lines, input_names = read_txt_file(file_path)
    elif file_path.endswith(".csv"):
        input_lines, input_names = read_csv_file(file_path)
    elif file_path.endswith(".json"):
        input_lines, input_names = read_json_file(file_path)
    elif os.path.isdir(file_path):
        for entry in os.scandir(file_path):
            if entry.is_file() and entry.name.endswith(".txt"):
                input_lines_ex, input_names_ex = read_txt_file(entry.path)
                input_lines.extend(input_lines_ex)
                input_names.extend(input_names_ex)
            elif entry.is_file() and entry.name.endswith(".csv"):
                input_lines_ex, input_names_ex = read_csv_file(entry.path)
                input_lines.extend(input_lines_ex)
                input_names.extend(input_names_ex)
            elif entry.is_file() and entry.name.endswith(".json"):
                input_lines_ex, input_names_ex = read_json_file(entry.path)
                input_lines.extend(input_lines_ex)
                input_names.extend(input_names_ex)
    else:
        LogHelper.warning(f"不支持的文件格式: {file_path}")
        os.system("pause")
        exit(1)

    input_lines_filtered = []
    for line in input_lines:
        # 【\N[123]】 这种形式是代指角色名字的变量
        # 直接抹掉就没办法判断角色了，只把 \N 部分抹掉，保留 ID 部分
        line = line.strip().replace(r"\\N", "")

        # 放大或者缩小字体的代码，干掉
        # \{\{ゴゴゴゴゴゴゴゴゴッ・・・\r\n（大地の揺れる音）
        line = re.sub(r"(\\\{)|(\\\})", "", line) 

        # \\C[4] 这种形式的代码，干掉
        line = re.sub(r"\\[A-Z]{1,3}\[\d+\]", "", line, flags = re.IGNORECASE)

        # 由于上面的代码移除，可能会产生空人名框的情况，干掉
        line = line.replace("【】", "") 

        # 干掉行内空字符（包括空格、制表符、换行符等），因为实体名称会过滤掉空格，所以这样可以避免匹配次数时匹配不到
        line = re.sub(r"\s+", "", line) 

        if len(line) == 0:
            continue

        if not TextHelper.has_any_japanese(line):
            continue

        input_lines_filtered.append(line.strip())

    LogHelper.info(f"已读取到文本 {len(input_lines)} 行，其中有效文本 {len(input_lines_filtered)} 行, 角色名 {len(input_names)} 个...")
    return input_lines_filtered, input_names

# 合并、计数并按置信度过滤
def merge_and_count(words, full_lines, per_score_threshold = 0.75, other_score_threshold = 0.90):
    words_categorized = {}
    for v in words:
        if (v.surface, v.ner_type) not in words_categorized:
            words_categorized[(v.surface, v.ner_type)] = [] # 只有文字和类型都一样才视为相同条目，避免跨类词条目合并
        words_categorized[(v.surface, v.ner_type)].append(v)

    words_merged = []
    for k, v in words_categorized.items():
        score = 0
        for w in v:
            score = score + w.score
    
        word = v[0]
        word.score = score / len(v) # 平均分

        if (
            word.ner_type == "PER" and word.score > per_score_threshold
            or
            word.ner_type != "PER" and word.score > other_score_threshold
        ):
            words_merged.append(word)

    lines_joined = "".join(full_lines)
    for word in words_merged:
        word.count = lines_joined.count(word.surface)

    return sorted(words_merged, key = lambda x: x.count, reverse = True)

# 获取指定类型的词
def get_words_by_ner_type(words, ner_type):
    # 显式的复制对象，避免后续修改对原始列表的影响，浅拷贝不复制可变对象（列表、字典、自定义对象等），慎重修改它们
    return [copy.copy(word) for word in words if word.ner_type == ner_type]

# 移除指定类型的词
def remove_words_by_ner_type(words, ner_type):
    return [word for word in words if word.ner_type != ner_type]

# 指定类型的词
def replace_words_by_ner_type(words, in_words, ner_type):
    words = remove_words_by_ner_type(words, ner_type)
    words.extend(in_words)
    return words

# 将 词语字典 写入文件
def write_words_dict_to_file(words, path):
    words_dict = {}
    for k, word in enumerate(words):
        if word.ner_type not in words_dict:
            words_dict[word.ner_type] = []

        t = {}
        t["score"] = float(word.score)
        t["count"] = word.count
        t["surface"] = word.surface
        t["ner_type"] = word.ner_type
        words_dict[word.ner_type].append(t)

    with open(path, "w", encoding = "utf-8") as file:
        file.write(json.dumps(words_dict, indent = 4, ensure_ascii = False))

# 将 词语日志 写入文件
def write_words_log_to_file(words, path):
    with open(path, "w", encoding = "utf-8") as file:
        for k, word in enumerate(words):
            file.write(f"词语原文 : {word.surface}\n")
            file.write(f"出现次数 : {word.count}\n")

            if G.config.translate_surface == 1:
                file.write(f"罗马音 : {word.surface_romaji}\n")
                file.write(f"词语翻译 : {', '.join(word.surface_translation)}, {word.surface_translation_description}\n")
            
            if word.ner_type == NER.NER_TYPES.get("PER"):
                file.write(f"角色性别 : {word.attribute}\n")

            file.write(f"语义分析 : {word.context_summary.get("summary", "")}\n")
            file.write(f"上下文原文 : ※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※\n")
            file.write(f"{'\n'.join(word.context)}\n")

            if G.config.translate_context_per == 1 and len(word.context_translation) > 0:
                file.write(f"上下文翻译 : ※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※※\n")
                file.write(f"{'\n'.join(word.context_translation)}\n")

            file.write(f"置信度 : {word.score}\n")
            if LogHelper.is_debug():
                file.write(f"{word.llmresponse_summarize_context}\n")
                file.write(f"{word.llmresponse_translate_context}\n")
                file.write(f"{word.llmresponse_translate_surface}\n")
                
            file.write("\n")

    LogHelper.info(f"结果已写入 - [green]{path}[/]")

# 将 词语列表 写入文件
def write_words_list_to_file(words, path):
    with open(path, "w", encoding = "utf-8") as file:
        data = {}
        for k, word in enumerate(words):
            if word.surface_translation and len(word.surface_translation) > 0:
                data[word.surface] = word.surface_translation[0]
            else:
                data[word.surface] = ""

        file.write(json.dumps(data, indent = 4, ensure_ascii = False))
        LogHelper.info(f"结果已写入 - [green]{path}[/]")

# 将 AiNiee 词典写入文件
def write_ainiee_dict_to_file(words, path):
    type_map = {
        "PER": "角色",      # 表示人名，如"张三"、"约翰·多伊"等。
        "ORG": "组织",      # 表示组织，如"联合国"、"苹果公司"等。
        "LOC": "地点",      # 表示地点，通常指非地理政治实体的地点，如"房间"、"街道"等。
        "PRD": "物品",      # 表示产品，如"iPhone"、"Windows操作系统"等。
        "EVT": "事件",      # 表示事件，如"奥运会"、"地震"等。
    }

    with open(path, "w", encoding = "utf-8") as file:
        datas = []
        for word in words:
            if not (word.surface_translation and len(word.surface_translation) > 0):
                continue

            data = {}
            data["srt"] = word.surface
            data["dst"] = word.surface_translation[0]

            if word.ner_type == "PER" and "男" in word.attribute:
                data["info"] = f"男性角色的名字"
            elif word.ner_type == "PER" and "女" in word.attribute:
                data["info"] = f"女性角色的名字"
            elif word.ner_type == "PER":
                data["info"] = f"未知性别角色的名字"
            else:
                data["info"] = f"{type_map.get(word.ner_type)}名称"

            datas.append(data)

        file.write(json.dumps(datas, indent = 4, ensure_ascii = False))
        LogHelper.info(f"结果已写入 - [green]{path}[/]")

# 将 GalTransl 词典写入文件
def write_galtransl_dict_to_file(words, path):
    type_map = {
        "PER": "角色",      # 表示人名，如"张三"、"约翰·多伊"等。
        "ORG": "组织",      # 表示组织，如"联合国"、"苹果公司"等。
        "LOC": "地点",      # 表示地点，通常指非地理政治实体的地点，如"房间"、"街道"等。
        "PRD": "物品",      # 表示产品，如"iPhone"、"Windows操作系统"等。
        "EVT": "事件",      # 表示事件，如"奥运会"、"地震"等。
    }

    with open(path, "w", encoding = "utf-8") as file:
        for word in words:
            if not (word.surface_translation and len(word.surface_translation) > 0):
                continue

            line = f"{word.surface}\t{word.surface_translation[0]}"

            if word.ner_type == "PER" and "男" in word.attribute:
                line = line + f"\t男性角色的名字"
            elif word.ner_type == "PER" and "女" in word.attribute:
                line = line + f"\t女性角色的名字"
            elif word.ner_type == "PER":
                line = line + f"\t未知性别角色的名字"
            else:
                line = line + f"\t{type_map.get(word.ner_type)}名称"

            file.write(f"{line}\n")
        LogHelper.info(f"结果已写入 - [green]{path}[/]")



# 查找 NER 实体
def search_for_entity(input_lines, input_names):
    LogHelper.info("即将开始执行 [查找 NER 实体] ...")
    words = G.ner.search_for_entity(input_lines, input_names)

    if LogHelper.is_debug():
        LogHelper.info(f"")
        with LogHelper.status(f"正在将实体字典写入文件 ..."):
            words = merge_and_count(words, input_lines)
            write_words_dict_to_file(words, "words_dict.json")

    # 查找上下文
    LogHelper.info("即将开始执行 [查找上下文] ...")
    LogHelper.info(f"")

    words = merge_and_count(words, input_lines)
    with ProgressHelper.get_progress() as progress:
        pid = progress.add_task("查找上下文", total = None)
        for k, word in enumerate(words):
            word.context = word.search_context(input_lines)
            progress.update(pid, advance = 1, total = len(words))

    LogHelper.info(f"")
    LogHelper.info("[查找上下文] 已完成 ...")

    # 有了上下文以后，开始执行还原词根
    LogHelper.info("即将开始执行 [还原词根] ...")
    words = G.ner.lemmatize_words_by_morphology(words, input_lines)
    words = remove_words_by_ner_type(words, "")
    words = merge_and_count(words, input_lines)
    words = G.ner.lemmatize_words_by_count(words, input_lines)
    words = remove_words_by_ner_type(words, "")
    words = merge_and_count(words, input_lines)
    LogHelper.info(f"[还原词根] 已完成 ...")

    # 按出现次数阈值进行筛选
    LogHelper.info(f"即将开始执行 [阈值筛选] ... 当前出现次数的筛选阈值设置为 {G.config.count_threshold} ...")
    words = [word for word in words if word.count >= G.config.count_threshold]
    LogHelper.info(f"[阈值筛选] 已完成 ... 出现次数 < {G.config.count_threshold} 的条目已剔除 ...")

    return words

# 开始处理日文
async def do_process_japanese():
    # 读取输入文件
    input_lines, input_names = read_input_file()

    # 查找 NER 实体
    words = []
    words = search_for_entity(input_lines, input_names)

    # 等待 语义分析任务 结果
    LogHelper.info("即将开始执行 [语义分析] ...")
    words_person = get_words_by_ner_type(words, NER.NER_TYPES.get("PER"))
    words_person = await G.llm.summarize_context_batch(words_person)
    words_person = remove_words_by_ner_type(words_person, "")
    words = replace_words_by_ner_type(words, words_person, NER.NER_TYPES.get("PER"))

    # 等待 重复性校验任务 结果
    LogHelper.info("即将开始执行 [重复性校验] ...")
    words = G.ner.validate_words_by_duplication(words)
    words = remove_words_by_ner_type(words, "")

    # 等待 实体分类任务 结果
    # LogHelper.info("即将开始执行 [实体分类] ...")
    # words_prd = get_words_by_ner_type(words, "PRD")
    # words_prd = await G.llm.classify_ner_bacth(words_prd)
    # words_prd = remove_words_by_ner_type(words_prd, "")
    # words = replace_words_by_ner_type(words, words_prd, "PRD")

    # 等待翻译词语任务结果
    if G.config.translate_surface == 1:
        LogHelper.info("即将开始执行 [词语翻译] ...")
        words = await G.llm.translate_surface_batch(words)

    ner_type = {
        "PER": "角色实体",
        "ORG": "组织实体",
        "LOC": "地点实体",
        "PRD": "物品实体",
        "EVT": "事件实体",
    }

    # 等待 上下文翻译 任务结果
    for k, v in ner_type.items():
        if (
            (k == "PER" and G.config.translate_context_per == 1)
            or
            (k != "PER" and G.config.translate_context_other == 1)
        ):
            LogHelper.info(f"即将开始执行 [上下文翻译 - {v}] ...")
            word_type = get_words_by_ner_type(words, k)
            word_type = await G.llm.translate_context_batch(word_type)
            words = replace_words_by_ner_type(words, word_type, k)

    dir_name, file_name_with_extension = os.path.split(G.config.input_file_path)
    file_name, extension = os.path.splitext(file_name_with_extension)

    LogHelper.info("")
    os.makedirs(".\\output", exist_ok = True)
    for k, v in ner_type.items():
        words_ner_type = get_words_by_ner_type(words, k)
        write_words_log_to_file(words_ner_type, f".\\output\\{file_name}_{v}_日志.txt")
        write_words_list_to_file(words_ner_type, f".\\output\\{file_name}_{v}_列表.json")
        write_ainiee_dict_to_file(words_ner_type, f".\\output\\{file_name}_{v}_ainiee.json")
        write_galtransl_dict_to_file(words_ner_type, f".\\output\\{file_name}_{v}_galtransl.txt")

    # 等待用户退出
    LogHelper.info("")
    LogHelper.info(f"工作流程已结束 ... 请检查生成的数据文件 ...")
    LogHelper.info("")
    LogHelper.info("")
    os.system("pause")

async def do_api_test():
    if await G.llm.api_test():
        LogHelper.info("接口测试 [green]执行成功[/] ...")
    else:
        LogHelper.warning("接口测试 [red]执行失败[/], 请检查配置文件 ...")

    LogHelper.print("")
    os.system("pause")
    os.system("cls")

# 打印应用信息
def print_app_info():
    LogHelper.print()
    LogHelper.print()
    LogHelper.rule(f"KeywordGacha", style = "light_goldenrod2")
    LogHelper.rule(f"[blue]https://github.com/neavo/KeywordGacha", style = "light_goldenrod2")
    LogHelper.rule(f"使用 OpenAI 兼容接口自动生成小说、漫画、字幕、游戏脚本等任意文本中的词语表的翻译辅助工具", style = "light_goldenrod2")
    LogHelper.print()

    table = Table(
        box = box.ASCII2,
        expand = True, 
        highlight = True,
        show_lines = True,
        border_style = "light_goldenrod2"
    )
    table.add_column("设置", style = "white", ratio = 1, overflow = "fold")
    table.add_column("当前值", style = "white", ratio = 1, overflow = "fold")
    table.add_column("设置", style = "white", ratio = 1, overflow = "fold")
    table.add_column("当前值", style = "white", ratio = 1, overflow = "fold")

    rows = [
        ("接口密钥", str(G.config.api_key), "模型名称", str(G.config.model_name)),
        ("接口地址", str(G.config.base_url)),
        ("出现次数阈值", str(G.config.count_threshold), "是否翻译词语", "是" if G.config.translate_surface == 1 else "否"),
        ("是否翻译角色实体上下文", "是" if G.config.translate_context_per == 1 else "否", "是否翻译其他实体上下文", "是" if G.config.translate_context_other == 1 else "否"),
        ("网络请求超时时间", f"{G.config.request_timeout} 秒" , "网络请求频率阈值", f"{G.config.request_frequency_threshold} 次/秒"),
    ]

    for row in rows:
        table.add_row(*row)

    LogHelper.print(table)
    LogHelper.print()
    LogHelper.print(f"请编辑 [green]config.json[/] 文件来修改应用设置 ...")
    LogHelper.print()

# 打印菜单
def print_menu_main():
    LogHelper.print(f"请选择：")
    LogHelper.print(f"")
    LogHelper.print(f"\t--> 1. 开始处理 [green]日文文本[/]")
    LogHelper.print(f"\t--> 2. 开始执行 [green]接口测试[/]")
    LogHelper.print(f"\t--> 3. 查看常见问题")
    LogHelper.print(f"")
    choice = int(Prompt.ask("请输入选项前的 [green]数字序号[/] 来使用对应的功能，默认为 [green][1][/] ", 
        choices = ["1", "2", "3"],
        default = "1",
        show_choices = False,
        show_default = False
    ))
    LogHelper.print(f"")

    return choice

# 打印常见问题
def print_menu_qa():
    os.system("cls")
    LogHelper.print(f"Q：KeywordGacha 支持读取哪些格式的文本文件？", highlight = True)
    LogHelper.print(f"A：目前支持三种不同的输入文本格式。", highlight = True)
    LogHelper.print(f"\t• .txt 纯文本格式，会将文件内的每一行当作一个句子来处理；", highlight = True)
    LogHelper.print(f"\t• .json 格式，会将文件内的每一条数据的 Key 的值当作一个句子来处理；", highlight = True)
    LogHelper.print(f"\t• .csv 表格，会将文件内的每一行的第一列当作一个句子来处理；", highlight = True)
    LogHelper.print(f"\t• 如果输入路径是一个文件夹，那则会读取这个文件夹内所有的 .txt .csv .json 文件；", highlight = True)
    LogHelper.print(f"", highlight = True)

    LogHelper.print(f"Q：我该如何获得这些格式的文本文件？", highlight = True)
    LogHelper.print(f"A：小说：", highlight = True)
    LogHelper.print(f"\t• 一般都是 .txt 纯文本文件，可直接使用；", highlight = True)
    LogHelper.print(f"A：游戏文本：", highlight = True)
    LogHelper.print(f"\t• 可通过 [blue]MTool[/] 、 [blue]SExtractor[/] 、[blue]Translator++[/] 等工具导出可用的游戏文本；", highlight = True)
    LogHelper.print(f"\t• 注意，虽然 KG 支持对 [blue]MTool[/] 导出文本的分析，但是因 [blue]MTool[/] 文本分割的特殊性，其分析效果较差；", highlight = True)
    LogHelper.print(f"", highlight = True)

    LogHelper.print(f"Q：处理过程中频繁报错错误提示怎么办？", highlight = True)
    LogHelper.print(f"A：少量报错：", highlight = True)
    LogHelper.print(f"\t• 一般不影响结果，不是强迫症可以无视。", highlight = True)
    LogHelper.print(f"A：全部报错：", highlight = True)
    LogHelper.print(f"\t• 一般是 接口信息填写错误 或者 本地服务器配置错误，请检查 [blue]config.cfg[/]。", highlight = True)
    LogHelper.print(f"A：请求频率限制：", highlight = True)
    LogHelper.print(f"\t• 如果报错信息中有错误码 [orange_red1]Error 429[/] 或者类似于 [orange_red1]请求过于频繁[/] 的错误信息，则为接口平台的请求频率限制。", highlight = True)
    LogHelper.print(f"\t• 请在 [blue]config.cfg[/] 中逐步调小 [blue]request_frequency_threshold[/] 的值，一直到不报错为止，这个值可以小于 1。", highlight = True)
    LogHelper.print(f"", highlight = True)

    LogHelper.print(f"")
    os.system("pause")
    os.system("cls")

# 主函数
async def begin():
    choice = -1
    while choice != 1:
        print_app_info()

        choice = print_menu_main()
        if choice == 1:
            await do_process_japanese()
        elif choice == 2:
            await do_api_test()
        elif choice == 3:
            print_menu_qa()

# 一些初始化步骤
def init():
    with LogHelper.status(f"正在初始化 [green]KG[/] 引擎 ..."):
        if LogHelper.is_debug():
            TestHelper.check_duplicates()

        # 注册全局异常追踪器
        rich.traceback.install()

        # 加载配置文件
        try:
            config_file = "config_dev.json" if os.path.exists("config_dev.json") else "config.json"

            with open(config_file, "r", encoding = "utf-8") as file:
                config = json.load(file)
                G.config = type("GClass", (), {})()

                for k, v in config.items():
                    setattr(G.config, k, v[0])
        except FileNotFoundError:
            LogHelper.error(f"文件 {config_file} 未找到.")
        except json.JSONDecodeError:
            LogHelper.error(f"文件 {config_file} 不是有效的JSON格式.")

        # 初始化 LLM 对象
        G.llm = LLM(G.config)
        G.llm.load_blacklist("blacklist.txt")
        G.llm.load_prompt_classify_ner("prompt\\prompt_classify_ner.txt")
        G.llm.load_prompt_summarize_context("prompt\\prompt_summarize_context.txt")
        G.llm.load_prompt_translate_context("prompt\\prompt_translate_context.txt")
        G.llm.load_prompt_translate_surface_common("prompt\\prompt_translate_surface_common.txt")
        G.llm.load_prompt_translate_surface_person("prompt\\prompt_translate_surface_person.txt")

        # 初始化 NER 对象
        G.ner = NER()
        G.ner.load_blacklist("blacklist.txt")

# 确保程序出错时可以捕捉到错误日志
async def main():
    try:
        init()
        await begin()
    except EOFError:
        LogHelper.error(f"EOFError - 程序即将退出 ...")
    except KeyboardInterrupt:
        LogHelper.error(f"KeyboardInterrupt - 程序即将退出 ...")
    except Exception as e:
        LogHelper.error(f"{LogHelper.get_trackback(e)}")
        LogHelper.print()
        LogHelper.print()
        LogHelper.error(f"出现严重错误，程序即将退出，错误信息已保存至日志文件 [green]KeywordGacha.log[/] ...")
        LogHelper.print()
        LogHelper.print()
        os.system("pause")

# 入口函数
if __name__ == "__main__":
    asyncio.run(main())
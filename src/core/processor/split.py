# import datetime
# import re
# from typing import List
#
# from src.core.data.data import ASRData, ASRDataSeg
# from src.core.log.logger import setup_logger
#
# logger = setup_logger("subtitle_splitter")
#
# def is_pure_punctuation(text: str) -> bool:
#     """
#     检查字符串是否仅由标点符号组成
#
#     Args:
#         text: 待检查的文本
#
#     Returns:
#         bool: 是否仅包含标点符号
#     """
#     return not re.search(r"\w", text, flags=re.UNICODE)
#
# def preprocess_segments(
#     segments: List[ASRDataSeg], need_lower: bool = True
# ) -> List[ASRDataSeg]:
#     """
#     预处理ASR数据分段:
#     1. 移除纯标点符号的分段
#     2. 对仅包含字母、数字和撇号的文本进行小写处理并添加空格
#
#     Args:
#         segments: ASR数据分段列表
#         need_lower: 是否需要转换为小写
#
#     Returns:
#         List[ASRDataSeg]: 处理后的分段列表
#     """
#     new_segments = []
#     for seg in segments:
#         if not is_pure_punctuation(seg.text):
#             # 如果文本只包含字母、数字和撇号，则将其转换为小写并添加一个空格
#             if re.match(r"^[a-zA-Z0-9\']+$", seg.text.strip()):
#                 if need_lower:
#                     seg.text = seg.text.lower() + " "
#                 else:
#                     seg.text = seg.text + " "
#             new_segments.append(seg)
#     return new_segments
#
# def count_words(text: str) -> int:
#     """
#     统计多语言文本中的字符/单词数
#     支持:
#     - 英文（按空格分词）
#     - CJK文字（中日韩统一表意文字）
#     - 韩文/谚文
#     - 泰文
#     - 阿拉伯文
#     - 俄文西里尔字母
#     - 希伯来文
#     - 越南文
#     每个字符都计为1个单位，英文按照空格分词计数
#
#     Args:
#         text: 输入文本
#
#     Returns:
#         int: 字符/单词总数
#     """
#     # 定义各种语言的Unicode范围
#     patterns = [
#         r"[\u4e00-\u9fff]",  # 中日韩统一表意文字
#         r"[\u3040-\u309f]",  # 平假名
#         r"[\u30a0-\u30ff]",  # 片假名
#         r"[\uac00-\ud7af]",  # 韩文音节
#         r"[\u0e00-\u0e7f]",  # 泰文
#         r"[\u0600-\u06ff]",  # 阿拉伯文
#         r"[\u0400-\u04ff]",  # 西里尔字母（俄文等）
#         r"[\u0590-\u05ff]",  # 希伯来文
#         r"[\u1e00-\u1eff]",  # 越南文
#         r"[\u3130-\u318f]",  # 韩文兼容字母
#     ]
#
#     # 统计所有非英文字符
#     non_english_chars = 0
#     remaining_text = text
#
#     for pattern in patterns:
#         # 计算当前语言的字符数
#         chars = len(re.findall(pattern, remaining_text))
#         non_english_chars += chars
#         # 从文本中移除已计数的字符
#         remaining_text = re.sub(pattern, " ", remaining_text)
#
#     # 计算英文单词数（处理剩余的文本）
#     english_words = len(remaining_text.strip().split())
#
#     return non_english_chars + english_words
#
#
# def determine_num_segments(word_count: int, threshold: int = 500) -> int:
#     """
#     根据字数确定分段数
#
#     Args:
#         word_count: 总字数
#         threshold: 每段的目标字数
#
#     Returns:
#         分段数
#     """
#     num_segments = word_count // threshold
#     if word_count % threshold > 0:
#         num_segments += 1
#     return max(1, num_segments)
#
# def split_asr_data(asr_data: ASRData, num_segments: int) -> List[ASRData]:
#     """
#     长文本发送LLM前进行进行分割，根据ASR分段中的时间间隔，将ASRData拆分成多个部分。
#
#     处理步骤：
#     1. 计算总字数，并确定每个分段的字数范围。
#     2. 确定平均分割点。
#     3. 在分割点前后一定范围内，寻找时间间隔最大的点作为实际的分割点。
#
#     Args:
#         asr_data: ASR数据对象
#         num_segments: 目标分段数
#
#     Returns:
#         ASR数据对象列表
#     """
#     SPLIT_RANGE = 30  # 在分割点前后寻找最大时间间隔的范围
#
#     total_segs = len(asr_data.segments)
#     total_word_count = count_words(asr_data.to_txt())
#     words_per_segment = total_word_count // num_segments
#
#     if num_segments <= 1 or total_segs <= num_segments:
#         return [asr_data]
#
#     # 计算每个分段的大致字数 根据每段字数计算分割点
#     split_indices = [i * words_per_segment for i in range(1, num_segments)]
#
#     # 调整分割点：在每个平均分割点附近寻找时间间隔最大的点
#     adjusted_split_indices = []
#     for split_point in split_indices:
#         # 定义搜索范围
#         start = max(0, split_point - SPLIT_RANGE)
#         end = min(total_segs - 1, split_point + SPLIT_RANGE)
#
#         # 在范围内找到时间间隔最大的点
#         max_gap = -1
#         best_index = split_point
#
#         for j in range(start, end):
#             gap = (
#                 asr_data.segments[j + 1].start_time - asr_data.segments[j].end_time
#             )
#             if gap > max_gap:
#                 max_gap = gap
#                 best_index = j
#
#         adjusted_split_indices.append(best_index)
#
#     # 移除重复的分割点
#     adjusted_split_indices = sorted(list(set(adjusted_split_indices)))
#
#     # 根据调整后的分割点拆分ASRData
#     segments = []
#     prev_index = 0
#     for index in adjusted_split_indices:
#         part = ASRData(asr_data.segments[prev_index : index + 1])
#         segments.append(part)
#         prev_index = index + 1
#
#     # 添加最后一部分
#     if prev_index < total_segs:
#         part = ASRData(asr_data.segments[prev_index:])
#         segments.append(part)
#
#     return segments
#
#
# def split_subtitle(subtitle_data: ASRData) -> ASRData:
#     try:
#         asr_data = subtitle_data
#         asr_data.segments = preprocess_segments(asr_data.segments, need_lower=False)
#         txt = asr_data.to_txt().replace("\n", "")
#
#         # 确定分段数
#         total_word_count = count_words(txt)
#         num_segments = determine_num_segments(total_word_count)
#         logger.info(f"根据字数 {total_word_count}，确定分段数: {num_segments}")
#
#         # 分割ASR数据
#         asr_data_list = split_asr_data(asr_data, num_segments)
#
#         # 多线程处理每个asr_data
#         processed_segments = process_segments(asr_data_list)
#
#         # 合并所有处理后的分段
#         final_segments = merge_processed_segments(processed_segments)
#
#         # 对短句进行合并优化
#         merge_short_segment(final_segments)
#
#     except Exception as e:
#         logger.error(f"Split subtitle error: {e}")
#         raise RuntimeError(f"Split subtitle error: {e}")
#
# def split_srt(srt_path):
#     """Translate SRT file content to Chinese using Ollama API"""
#
#     asr_data = ASRData.from_subtitle_file(srt_path)
#     asr_data.split_to_word_segments()
#
#     logger.info(f"\n===========字幕处理任务开始===========")
#     logger.info(f"时间：{datetime.datetime.now()}")
#
#     logger.info("正在字幕断句...")
#     asr_data = split_subtitle(asr_data)
#

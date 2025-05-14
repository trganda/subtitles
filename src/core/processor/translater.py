import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from string import Template
from typing import Dict, List

from openai import OpenAI

from src.constants.constant import OPENAI_BASE_URL, OPENAI_API_KEY, MODEL
from src.constants.prompt import TRANSLATE_PROMPT, SINGLE_TRANSLATE_PROMPT
from src.core.data.asr import ASRData, ASRDataSeg
from src.utils import json_repair


def openai_completion(prompt: str, user_content):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]

    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    return client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        timeout=300,
    )

def translate_chunk_single(subtitle_chunk: Dict[str, str]):
    result = {}
    single_prompt = Template(SINGLE_TRANSLATE_PROMPT).safe_substitute(
        target_language="简体中文"
    )

    for idx, text in subtitle_chunk.items():
        try:
            response = openai_completion(single_prompt, text)
            translated_text = response.choices[0].message.content.strip()
            # 删除 DeepSeek-R1 等推理模型的思考过程 #300
            translated_text = re.sub(
                r"<think>.*?</think>", "", translated_text, flags=re.DOTALL
            )
            translated_text = translated_text.strip()
            result[idx] = translated_text
        except Exception as e:
            logging.error(f"单条翻译失败 {idx}: {str(e)}")
            result[idx] = "ERROR"  # 如果翻译失败，返回错误标记

    logging.info(result)
    return result


def translate_chunk(subtitle_chunk: Dict[str, str]):
    prompt = TRANSLATE_PROMPT
    prompt = Template(prompt).safe_substitute(
        target_language="简体中文", custom_prompt=""
    )

    result = {}
    try:
        response = openai_completion(
            prompt, json.dumps(subtitle_chunk, ensure_ascii=False)
        )
        result = json_repair.loads(response.choices[0].message.content)
        # 检查翻译结果数量是否匹配
        if len(result) != len(subtitle_chunk):
            logging.warning(f"翻译结果数量不匹配，将使用单条翻译模式重试")
            logging.warning(f"翻译结果: {subtitle_chunk}, {result}")
            return translate_chunk_single(subtitle_chunk)

        result = {k: f"{v}" for k, v in result.items()}
        return result
    except  Exception as e:
        try:
            return translate_chunk_single(subtitle_chunk)
        except Exception as e:
            logging.info("Failed to translate chunk with LLM", e)
            return result
            # raise RuntimeError(f"OpenAI API调用失败：{str(e)}")


def split_chunks(subtitle_dict: Dict[str, str]):
    """将字幕分割成块"""
    items = list(subtitle_dict.items())
    return [
        dict(items[i : i + 10])
        for i in range(0, len(items), 10)
    ]

def safe_translate_chunk(chunk):
    """安全的翻译块，包含重试逻辑"""
    # for i in range(3):
    result = translate_chunk(chunk)
    return result
    # return None


def parallel_translate(parallels_threads, chunks):
    """并行翻译字幕块，使用固定大小线程池控制并发"""
    translate_dict = {}
    with ThreadPoolExecutor(max_workers=parallels_threads) as executor:
        futures = []
        for chunk in chunks:
            futures.append(executor.submit(safe_translate_chunk, chunk))

        for future in as_completed(futures):
            result = future.result()
            translate_dict.update(result)
    
    return translate_dict


def create_segments(
    original_segments: List[ASRDataSeg], translated_dict: Dict[str, str]
) -> List[ASRDataSeg]:
    """创建新的字幕段"""
    for i, seg in enumerate(original_segments, 1):
        try:
            seg.translated_text = translated_dict[str(i)]  # 设置翻译文本
        except Exception as e:
            # logger.error(f"创建新的字幕段失败：{str(e)}")
            seg.translated_text = seg.text
    return original_segments


def translate_subtitle(parallels_threads, subtitle_data: ASRData) -> ASRData:
    try:
        # 将ASRData转换为字典格式
        subtitle_dict = {
            str(i): seg.text for i, seg in enumerate(subtitle_data.segments, 1)
        }

        # 分批处理字幕
        chunks = split_chunks(subtitle_dict)

        translated_dict = parallel_translate(parallels_threads, chunks)
        new_segments = create_segments(subtitle_data.segments, translated_dict)

        return ASRData(new_segments)
    except Exception as e:
        raise RuntimeError(f"Translating failed{str(e)}")

if __name__ == "__main__":
    asr_data = ASRData.from_subtitle_file("/Users/trganda/Tools/subtitles/output/extracted_audio.srt")
    translated_asr_data = translate_subtitle(6, asr_data)
    for seg in translated_asr_data.segments:
        print(seg.text + " " + seg.translated_text)

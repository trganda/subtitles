# Subtitle Generator

> 该工具主要为了适配 M 系列的 Mac 进行计算加速，其他平台建议使用其他工具，例如：[VideoCaptioner](https://github.com/WEIFENG2333/VideoCaptioner)。

## 使用方法

用到的工具：

1. [ffmpeg](https://ffmpeg.org/)
2. [whisper-cli](https://github.com/ggml-org/whisper.cpp)
3. [ollama/llm](https://ollama.com/)

### 提取音频

从原视频中提取音频，使用 `ffmpeg` 命令，命令如下：

```bash
ffmpeg -i <inptu video file> -map 0:a -ac 1 -ar 16000 -af aresample=async=1 -y <output audio file>
```

- `-i <input video file>`：指定输入视频文件的路径。
- `-map 0:a`：表示映射输入文件的第 1 个音频流。其中，`0` 代表输入文件的第 1 个文件，`a` 代表音频流。
- `-ac 1`：设置输出音频的声道数为单声道。
- `-ar 16000`：设置输出音频的采样率为 16000Hz。
- `-af aresample=async=1`：使用音频重采样滤镜 `aresample`，并设置 `async=1`，表示异步重采样，以提高处理效率。
- `-y`：覆盖输出文件，即如果输出文件已存在，会直接覆盖而不进行提示。
- `<output audio file>`：指定输出音频文件的路径。

### 音频转文本

使用 [whisper](https://github.com/openai/whisper) 模型将语言转化成文本，Apple Slicon 系列的 Mac 可使用以下方式进行 `GPU` 加速

- 项目地址： https://github.com/ggml-org/whisper.cpp

```
git clone https://github.com/ggml-org/whisper.cpp.git && cd whisper.cpp
```

使用脚本下载 `ggml` 格式的 `whisper` 模型，根据个人硬件配置选择模型规模，

```bash
sh ./models/download-ggml-model.sh medium.en
```

对项目进行编译

```bash
# build the project
cmake -B build
cmake --build build --config Release
```

使用下载的模型对音频文件进行处理

```bash
# transcribe an audio file
./build/bin/whisper-cli -m <model_path> -f samples/jfk.wav
```

能看到如下输出，就代表成功使用 `metal` 进行计算加速。

```
whisper_backend_init_gpu: using Metal backend
ggml_metal_init: allocating
ggml_metal_init: found device: Apple M1 Max
ggml_metal_init: picking default device: Apple M1 Max
```

### 字幕文本翻译与校正

借助脚本调用 LLM 对提取后的字幕进行翻译，核心代码如下：

```python
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
```

> [!info]
> 代码借鉴了 [VideoCaptioner](https://github.com/WEIFENG2333/VideoCaptioner) 。

默认使用本地 Ollama 中的模型，如果需要使用其他模型，需要修改 `src/constants/constant.py` 文件中的 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY` 变量。

```
OPENAI_BASE_URL="http://192.168.100.10:11434/v1"
OPENAI_API_KEY="ollama"
MODEL="qwen2.5:7b"
```

### 视频合成

使用以下命令将字幕文件嵌入到原始视频文件中

```
ffmpeg -i original_video.mp4 -acodec copy -vcodec libx264 -preset medium -vf subtitles='<path_to_subtitles>.ass' -y <output_video>
```

这条 `ffmpeg` 命令用于对视频文件进行处理，下面是命令中各个选项及其含义的详细解释：

- `-i original_video.mp4`
    - `-i` 是 `ffmpeg` 中用于指定输入文件的选项，即需要处理的原始视频文件。
- `-acodec copy`
    - `-acodec` 是 `audio codec` 的缩写，用于指定音频编码方式。`copy` 表示直接复制原始音频流，不进行重新编码。这样可以节省处理时间，同时保持音频的原始质量。
- `-vcodec libx264`
    - `-vcodec` 是 `video codec` 的缩写，用于指定视频编码方式。`libx264` 是一种广泛使用的开源 H.264 视频编码器，它可以在保证视频质量的同时，有效地压缩视频文件大小。
- `-preset medium`
    - `-preset` 选项用于控制编码速度和压缩效率之间的平衡。`medium` 是预设值之一，表示中等速度和压缩效率。其他常见的预设值包括 `ultrafast`、`superfast`、`fast`、`slow`、`veryslow` 等，速度越快，压缩效率越低；速度越慢，压缩效率越高。
- `-vf subtitles='<path_to_subtitles>.ass'`
    - `-vf` 是 `video filter` 的缩写，用于指定视频滤镜。`subtitles` 是一个视频滤镜，用于将字幕文件嵌入到视频中。这里指定的字幕文件路径是 `<path_to_subtitles>.ass`，`.ass` 是一种支持高级字幕效果的字幕文件格式。
- `-y`
    - `-y` 选项用于在输出文件已经存在时，自动覆盖该文件，而不需要用户手动确认。

## 参考

1. https://github.com/ggml-org/whisper.cpp/issues/2606

from openai import OpenAI
import os

client = OpenAI(
    api_key="sk-5672a9d81fd8487ab1ac76532ae5ef48",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.embeddings.create(
    model="text-embedding-v4",
    input="这是一段测试文本",
    dimensions=1024  # 仅 v3/v4 支持
)
print(response.data[0].embedding)
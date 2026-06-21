"""
测试所有依赖模块是否可以正常导入
"""
dependencies = [
    "fastapi",
    "starlette",
    "uvicorn",
    "sqlalchemy",
    "pymysql",
    "pydantic",
    "pydantic_settings",
    "jose",
    "passlib",
    "multipart",
    "requests",
    "httpx",
    "langchain_core",
    "langchain_openai",
    "langchain_milvus",
    "langchain_text_splitters",
    "pymilvus",
    "torch",
    "transformers",
    "sentence_transformers",
    "sentencepiece",
    "pypdf",
    "docx",
    "openpyxl"
]

for dep in dependencies:
    try:
        __import__(dep)
        print(f"{dep} 导入成功")
    except ImportError as e:
        print(f"{dep} 导入失败: {e}")
    except Exception as e:
        print(f"{dep} 其他错误: {e}")

print("\n依赖检查完成!")

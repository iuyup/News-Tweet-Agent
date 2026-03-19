"""
python -m src.agent 入口
"""
import asyncio
import logging

from src.agent import run_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

asyncio.run(run_agent())

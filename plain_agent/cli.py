import os

from dotenv import load_dotenv

from plain_agent.agent_loop import SimpleAgent
from plain_agent.compaction import (
    CompactionConfig,
    ConversationCompactor,
)
from plain_agent.config import AppConfig
from plain_agent.llm_client import OpenAICompatibleClient
from plain_agent.terminal_loop import approve_run_command, run_interactive_terminal


def main() -> None:
    load_dotenv()
    config = AppConfig.from_env(os.environ)

    llm_client = OpenAICompatibleClient(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
    )
    compactor = ConversationCompactor(
        llm_client=llm_client,
        model=config.llm.model,
        config=CompactionConfig(
            keep_recent_exchanges=config.compaction.keep_recent_exchanges,
            model=config.compaction.model,
        ),
    )
    agent = SimpleAgent(
        llm_client=llm_client,
        model=config.llm.model,
        command_approver=approve_run_command,
        compactor=compactor,
        auto_compact_max_tokens=config.compaction.auto_max_tokens,
    )

    run_interactive_terminal(agent)

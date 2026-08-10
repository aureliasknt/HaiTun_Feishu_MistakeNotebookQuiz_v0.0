async def system_prompt_builder() -> str:
    return "You are helpful."

async def compact_history(history, complete_fn) -> str:
    return "SUMMARY: " + str(len(history))

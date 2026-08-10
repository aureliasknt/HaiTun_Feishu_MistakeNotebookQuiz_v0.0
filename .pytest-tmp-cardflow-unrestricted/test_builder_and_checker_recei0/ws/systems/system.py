async def system_prompt_builder(user_message):
    return user_message['content']

async def system_prompt_rebuild_checker(user_message):
    return user_message['content'] == 'rebuild'

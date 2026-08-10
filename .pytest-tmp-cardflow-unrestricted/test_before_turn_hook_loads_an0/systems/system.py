async def system_before_turn(user_message):
    return {'breakout': {'needed': True}, 'seen': user_message['content']}

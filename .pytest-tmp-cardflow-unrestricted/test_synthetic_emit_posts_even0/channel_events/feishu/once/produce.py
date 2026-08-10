async def produce(ctx):
    await ctx.emit({'payload': {'n': 1}, 'routing': {'open_id': 'ou_x'}})

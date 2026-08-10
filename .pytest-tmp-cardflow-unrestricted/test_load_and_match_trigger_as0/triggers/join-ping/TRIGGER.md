---
name: join-ping
source: feishu
event: feishu.chat.member_added
filter:
  chat_id: oc_target
fire: tool
tool: echo_tool
tool_args:
  text: hi
visibility: silent
---

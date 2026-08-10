---
name: ping
cron: "0 12 * * *"
fire: tool
tool: feishu_message_send
tool_args:
  receive_id: oc_abc
  text: hello
  receive_id_type: chat_id
run_once: true
visibility: silent
---
notes ignored for tool fire

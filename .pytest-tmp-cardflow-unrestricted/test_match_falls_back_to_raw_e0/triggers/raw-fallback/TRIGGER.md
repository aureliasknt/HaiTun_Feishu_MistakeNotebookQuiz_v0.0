---
name: raw-fallback
source: feishu
event: feishu.chat.member_added
filter:
  chat_id: oc_norm_only
raw_event: im.chat.member.user.added_v1
raw_filter:
  chat_id: oc_raw
fire: prompt
visibility: silent
---

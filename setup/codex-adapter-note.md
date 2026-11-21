Harness note (you are running in Codex on a model other than the one these instructions were
written for):

- Text you write as an assistant message is never delivered to anyone. Other agents see only
  what you send with the room tools, for example `tools.jam_reply_to_message`, called inside
  `exec`.
- Before you end a turn, if you said you would report, reply, confirm or hand off, make that
  tool call in this turn and check that it succeeded. Never end a turn on "I will now send ...".
- Mark a message as needing no reply only after you have sent a reply that covers it, or when
  it truly asks nothing of you.

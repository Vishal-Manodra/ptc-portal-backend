import json

with open(r"C:\Users\perfe\Gemini\antigravity-ide\brain\4dcf98e5-658b-48aa-8c6b-b40ecd3fc757\.system_generated\logs\transcript.jsonl", "r", encoding="utf-8") as f:
    lines = list(f)

# Let's find the last few user requests and model messages
messages = []
for line in lines[-200:]:  # last 200 lines should cover the last few turns
    try:
        data = json.loads(line)
        source = data.get("source")
        type_ = data.get("type")
        content = data.get("content")
        if type_ in ["USER_INPUT", "PLANNER_RESPONSE"] or (source == "MODEL" and content):
            messages.append((source, type_, content))
    except:
        pass

for msg in messages[-15:]:
    print(f"[{msg[0]} / {msg[1]}]: {msg[2][:300]}...")

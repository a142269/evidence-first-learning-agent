import re
with open(r"F:\比赛\中软杯\A3\knowledge_base\python_programming\chapters\08_inheritance_polymorphism.md","r",encoding="utf-8") as fh:
    content = fh.read()
end = content.find("---", 3)
body = content[end + 3:]
body_no_code = re.sub(r"```.*?```", "", body, flags=re.S)
print(f"08_inheritance_polymorphism.md: {len(body_no_code)} chars")

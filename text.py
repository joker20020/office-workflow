# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2026/3/16 15:31
# @version  : V1

async def get_json(text: str):
    group = []
    result = ""
    bracket_count = 0
    for s in text:
        if s == "{":
            bracket_count += 1
        elif s == "}":
            bracket_count -= 1
        if bracket_count:
            group.append(s)
        elif bracket_count == 0 and s == "}":
            group.append(s)
            result += "".join(group)
            group = []

    return result
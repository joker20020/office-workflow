# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2025/7/22 16:25
# @version  : V1
import re

from wxauto import WeChat

class WxAssistance(WeChat):

    def __init__(self, nickname=None):
        super().__init__(nickname=nickname)
        self.innerVar = ["name"]

    def SendWithTemplate(self, FriendNames, template):
        pattern = r'(\{\{.*?\}\})'
        tokens = re.split(pattern, template)

        for name in FriendNames:
            output = []
            for token in tokens:
                if token.startswith('{{') and token.endswith('}}'):
                    var_name = token[2:-2].strip()
                    if var_name in self.innerVar:
                        if var_name == "name":
                            output.append(name)
                else:
                    output.append(token)

            result = "".join(output)
            self.SendMsg(result, name)


if __name__ == "__main__":
    wx = WxAssistance()
    wx.SendWithTemplate(["文件传输助手", "文件传输助手"], r"{{name}},你好")
    # wx.SendMsg("你好", who="文件传输助手")
    #
    # # 获取当前聊天窗口消息
    # msgs = wx.GetAllMessage()
    #
    # for msg in msgs:
    #     print('==' * 30)
    #     print(f"{msg.sender}: {msg.content}")
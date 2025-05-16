import json


class ControllerAgent:
    def __init__(self):
        self.mcp_config = None

        with open("mcp_config/controller.json", "r") as f:
            self.mcp_config = json.load(f)

    def get_controller(self, controller_name: str):
        pass

class CommandRegistry:
    def __init__(self):
        self.commands = []

    def register(self, command):
        self.commands.append(command)

    def get_command(self, intent: str):
        for command in self.commands:
            if command.can_handle(intent):
                return command
        return None

    def list_commands(self):
        return [command.name for command in self.commands]
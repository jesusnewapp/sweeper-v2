import sys
import unittest
from pathlib import Path

from supervise_controller import controller_command


class ControllerSupervisorTests(unittest.TestCase):
    def test_controller_command_forwards_exact_arguments(self):
        arguments = ["--config", "/tmp/controller.json", "--port", "8790"]
        command = controller_command(arguments)
        self.assertEqual(sys.executable, command[0])
        self.assertEqual("-u", command[1])
        self.assertEqual("server.py", Path(command[2]).name)
        self.assertEqual(arguments, command[3:])


if __name__ == "__main__":
    unittest.main()

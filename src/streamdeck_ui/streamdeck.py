import hid

VID = 0x0FD9
PID = 0x00B9
ROWS = 3
COLS = 5


def _get_bytes(data: bytes, offset: int, length: int = 1) -> bytes:
    return data[offset : offset + length]


def _bytes_to_int(data: bytes, signed: bool = True) -> int:
    return int.from_bytes(data, byteorder="little", signed=signed)


def _int_to_bytes(value: int, length: int, signed: bool = True) -> bytes:
    return value.to_bytes(length, byteorder="little", signed=signed)


class InputReport:
    data: bytes
    report_id: bytes
    command: bytes
    payload_length: int
    payload: bytes

    def __init__(self, input_data: bytes):
        self.data = input_data

        self.report_id = _get_bytes(input_data, 0)
        self.command = _get_bytes(input_data, 1)

        self.payload_length = _bytes_to_int(
            _get_bytes(input_data, 2, length=2),
            signed=False,
        )
        self.payload = _get_bytes(input_data, 4, length=self.payload_length)


class OutputReport:
    data: bytes
    report_id: bytes
    command: bytes
    payload: bytes

    payload_length: int = 1022

    def __init__(self, report_id: bytes, command: bytes, payload: bytes):
        assert len(report_id) == 1, "Report ID must be 1 byte"
        assert len(command) == 1, "Command must be 1 byte"
        assert len(payload) <= self.payload_length, "Payload exceeds maximum length"

        self.report_id = report_id
        self.command = command

        self.payload = payload

        self.data = report_id + command + (b"\0" * (self.payload_length - len(payload))) + payload


class StreamDeck(hid.Device):
    key_state: list[list[bool]] = [[False] * COLS for _ in range(ROWS)]
    previous_key_state: list[list[bool]] = [[False] * COLS for _ in range(ROWS)]

    def __init__(self):
        super().__init__(VID, PID)

    def read_input(self):
        input_data = self.read(19)
        input_report = InputReport(input_data)

        assert input_report.report_id == 0x01, f"Invalid report ID: {input_report.report_id}"
        assert input_report.command == 0x01, f"Invalid command: {input_report.command}"

        for i in range(ROWS):
            for j in range(COLS):
                self.key_state[i][j] = bool(input_report.payload[i * COLS + j] & 0x01)

    def get_serial(self):
        self.get_feature_report(0x00, 8)
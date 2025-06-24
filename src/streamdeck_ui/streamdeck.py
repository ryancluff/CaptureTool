import hid

VID = 0x0FD9
PID = 0x00B9
ROWS = 3
COLS = 5


def _get_bytes(data: bytes, offset: int, length: int = 1) -> bytes:
    return data[offset : offset + length]


def _bytes_to_int(data: bytes, signed=True) -> int:
    return int.from_bytes(data, byteorder="little", signed=signed)


class StreamDeck(hid.Device):
    def __init__(self):
        super().__init__(VID, PID)

    def read_input(
        self,
        size: int = 19,
    ) -> tuple[int, int]:
        """Read input from the Stream Deck."""
        input_bytes = self.read(size)
        report = _get_bytes(input_bytes, 0)
        command = _get_bytes(input_bytes, 1)

        payload_length = _bytes_to_int(
            _get_bytes(input_bytes, 2, length=2),
            signed=False,
        )
        assert payload_length == ROWS * COLS, "Payload length does not match expected size."

        payload = _get_bytes(input_bytes, 4, length=payload_length)
        for 

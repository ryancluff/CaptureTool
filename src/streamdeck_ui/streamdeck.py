import hid

VID = 0x0FD9
PID = 0x00B9
ROWS = 3
COLS = 5


def _pop_bytes(data: bytearray, length: int = 1) -> bytes:
    """Pop bytes from the start of the data."""
    result = bytes(data[:length])
    del data[:length]
    return result


def _pop_int(data: bytearray, length: int = 1) -> int:
    """Pop a single byte and convert it to a signed integer."""
    return int.from_bytes(
        _pop_bytes(data, length=length), byteorder="little", signed=True
    )


def _pop_uint(data: bytearray, length: int = 1) -> int:
    """Pop a single byte and convert it to an unsigned integer."""
    return int.from_bytes(
        _pop_bytes(data, length=length), byteorder="little", signed=False
    )


def _pop_chars(data: bytearray, length: int = 1) -> str:
    """Pop a single byte and convert it to an ASCII character."""
    return _pop_bytes(data, length=length).decode("ascii")


class StreamDeck(hid.Device):
    key_state: list[list[bool]] = [[False] * COLS for _ in range(ROWS)]
    previous_key_state: list[list[bool]] = [[False] * COLS for _ in range(ROWS)]

    def __init__(self):
        super().__init__(VID, PID)

    def read_input(self) -> tuple[bytes, bytes, int, bytes]:
        response = bytearray(self.read(19))

        report_id = _pop_bytes(response)
        command = _pop_bytes(response)
        data_length = _pop_uint(response, length=2)
        data = _pop_bytes(response, length=data_length)

        return report_id, command, data_length, data

    def write_output(self, report_id: bytes, command: bytes, payload: bytes):
        pass

    def get_firmware_version(self, name: str) -> tuple[bytes, int, bytes, str]:
        firmware = {"LD": 0x04, "AP1": 0x05, "AP2": 0x07}
        assert (
            name in firmware.keys()
        ), f"Invalid firmware name - {name} not in {firmware.keys()}"

        response = bytearray(self.get_feature_report(firmware[name], 14))

        report_id = _pop_bytes(response)
        data_length = _pop_uint(response)
        checksum = _pop_bytes(response, length=4)
        version = _pop_chars(response, length=8)

        return report_id, data_length, checksum, version

    def get_serial_number(self) -> tuple[bytes, int, str]:
        response = bytearray(self.get_feature_report(0x06, 16))

        report_id = _pop_bytes(response)
        data_length = _pop_uint(response)
        serial_number = _pop_chars(response, length=14)

        return report_id, data_length, serial_number

    def get_sleep_idle(self) -> tuple[bytes, int, int]:
        response = bytearray(self.get_feature_report(0x0A, 6))

        report_id = _pop_bytes(response)
        data_length = _pop_uint(response)
        sleep_idle = _pop_uint(response)

        return report_id, data_length, sleep_idle

    def get_unit_info(
        self,
    ) -> tuple[bytes, int, int, int, int, int, int, int, int, int, int, int, bytes]:
        response = bytearray(self.get_feature_report(0x08, 32))

        report_id = _pop_bytes(response)
        matrix_rows = _pop_uint(response)
        matrix_cols = _pop_uint(response)
        key_width = _pop_uint(response, length=2)
        key_height = _pop_uint(response, length=2)
        lcd_width = _pop_uint(response, length=2)
        lcd_height = _pop_uint(response, length=2)
        image_bpp = _pop_uint(response)
        image_color_scheme = _pop_uint(response)
        num_key_images = _pop_uint(response)
        num_lcd_images = _pop_uint(response)
        num_frames = _pop_uint(response)
        reserved = _pop_bytes(response)

        return (
            report_id,
            matrix_rows,
            matrix_cols,
            key_width,
            key_height,
            lcd_width,
            lcd_height,
            image_bpp,
            image_color_scheme,
            num_key_images,
            num_lcd_images,
            num_frames,
            reserved,
        )

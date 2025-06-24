from streamdeck_ui.streamdeck import StreamDeck


def main():
    with StreamDeck() as streamdeck:
        result = streamdeck.read_input()
        print(result)

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="capture or calibrate")
    args = parser.parse_args()

    if args.mode == "capture":
        from src.capture import run
        run()
    elif args.mode == "calibrate":
        from src.calibrate import run
        run()
    else:
        print("Invalid mode")


if __name__ == "__main__":
    main()

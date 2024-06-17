import argparse
import queue
import sys

from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("-l", "--list-devices", action="store_true", help="show list of audio devices and exit")
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[parser]
)

parser.add_argument("-d", "--device", type=int, help="output device (numeric xID or substring)")
parser.add_argument(
    "frequency",
    nargs="?",
    metavar="FREQUENCY",
    type=float,
    default=1000,
    help="frequency in Hz (default: %(default)s)",
)
parser.add_argument("-a", "--amplitude", type=float, default=0.5, help="amplitude (default: %(default)s)")

parser.add_argument("-fs", "--samplerate", type=int, default=48000, help="sampling rate of the device")
parser.add_argument("-t", "--dtype", type=str, default="int24", help="data type")

parser.add_argument("-o", "--output_channel", type=int, default=1, help="output channel")
parser.add_argument("-i", "--input_channel", type=int, default=1, help="input channel")

parser.add_argument(
    "-n", "--downsample", type=int, default=10, metavar="N", help="display every Nth sample (default: %(default)s)"
)
parser.add_argument(
    "-w",
    "--window",
    type=float,
    default=100,
    metavar="DURATION",
    help="visible time slot (default: %(default)s ms)",
)
parser.add_argument(
    "--interval", type=float, default=30, help="minimum time between plot updates (default: %(default)s ms)"
)

args = parser.parse_args(remaining)

q_in = queue.Queue()
q_out = queue.Queue()
start_idx = 0
length = int(args.window * args.samplerate / (1000 * args.downsample))
plotdata = np.zeros((length, 2))

try:

    def callback(indata, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        global start_idx
        t = (start_idx + np.arange(frames)) / args.samplerate
        outdata[:, args.output_channel - 1] = args.amplitude * np.sin(2 * np.pi * args.frequency * t)
        start_idx += frames
        q_out.put(outdata[:: args.downsample, args.output_channel - 1])
        q_in.put(indata[:: args.downsample, args.input_channel - 1])

    def update_plot(frame):
        """This is called by matplotlib for each plot update.

        Typically, audio callbacks happen more frequently than plot updates,
        therefore the queue tends to contain multiple blocks of audio data.

        """
        global plotdata
        while True:
            try:
                data_out = q_out.get_nowait()
                data_in = q_in.get_nowait()
            except queue.Empty:
                break
            shift = len(data_out)
            plotdata = np.roll(plotdata, -shift, axis=0)
            plotdata[-shift:, 0] = data_out
            plotdata[-shift:, 1] = data_in
        for column, line in enumerate(lines):
            line.set_ydata(plotdata[:, column])
        return lines

    fig, ax = plt.subplots()
    lines = ax.plot(plotdata)
    # if len(args.channels) > 1:
    #     ax.legend([f'channel {c}' for c in args.channels],
    #             loc='lower left', ncol=len(args.channels))
    ax.axis((0, len(plotdata), -1, 1))
    ax.set_yticks([0])
    ax.yaxis.grid(True)
    ax.tick_params(bottom=False, top=False, labelbottom=False, right=False, left=False, labelleft=False)
    fig.tight_layout(pad=0)

    device_info = sd.query_devices(args.device, "output")

    stream = sd.Stream(device=args.device, channels=1, callback=callback, samplerate=args.samplerate)

    ani = FuncAnimation(fig, update_plot, interval=args.interval, blit=True)
    with stream:
        plt.show()

except KeyboardInterrupt:
    exit(0)
except Exception as e:
    parser.exit(type(e).__name__ + ": " + str(e))

import math
import struct
from pathlib import Path

import lameenc


SAMPLE_RATE = 44100
DURATION_SECONDS = 0.65
OUTPUT_PATH = Path(__file__).resolve().parents[1] / 'task-completed.mp3'


def create_pcm():
    sample_count = int(SAMPLE_RATE * DURATION_SECONDS)
    samples = []
    for index in range(sample_count):
        time = index / SAMPLE_RATE
        envelope = math.exp(-7 * time)
        tone = (
            math.sin(2 * math.pi * 880 * time)
            + 0.45 * math.sin(2 * math.pi * 1320 * time)
        )
        sample = int(12000 * envelope * tone)
        samples.append(struct.pack('<h', sample))
    return b''.join(samples)


def main():
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    encoded = encoder.encode(create_pcm()) + encoder.flush()
    OUTPUT_PATH.write_bytes(encoded)
    print(f'Created {OUTPUT_PATH}')


if __name__ == '__main__':
    main()

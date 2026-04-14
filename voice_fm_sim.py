#!/usr/bin/env python3
"""Real-time microphone -> NBFM TX -> noisy channel -> NBFM RX -> speaker simulation.

This script avoids SDR hardware and runs entirely in software.
"""

import argparse
import signal
import sys

from gnuradio import analog
from gnuradio import audio
from gnuradio import blocks
from gnuradio import channels
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window


class VoiceFmSim(gr.top_block):
    def __init__(
        self,
        audio_rate=48000,
        quad_rate=240000,
        max_dev=5000.0,
        tau=75e-6,
        noise_voltage=0.01,
        tx_gain=1.0,
        rx_volume=1.0,
        mic_device="default",
        spk_device="default",
    ):
        super().__init__("Voice FM Simulation")

        # Audio I/O (real-time pacing comes from these blocks).
        self.audio_source = audio.source(audio_rate, mic_device, True)
        self.audio_sink = audio.sink(audio_rate, spk_device, True)

        # Keep speech bandwidth near telephony voice range before FM modulation.
        self.voice_lpf = filter.fir_filter_fff(
            1,
            filter.firdes.low_pass(
                1.0,
                audio_rate,
                3400,
                600,
                window.WIN_HAMMING,
            ),
        )

        self.nbfm_tx = analog.nbfm_tx(
            audio_rate=audio_rate,
            quad_rate=quad_rate,
            tau=tau,
            max_dev=max_dev,
            fh=-1.0,
        )

        # Simulated air channel: attenuation + AWGN.
        self.tx_attn = blocks.multiply_const_cc(tx_gain)
        self.channel = channels.channel_model(
            noise_voltage=noise_voltage,
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0 + 0.0j],
            noise_seed=0,
            block_tags=False,
        )

        self.nbfm_rx = analog.nbfm_rx(
            audio_rate=audio_rate,
            quad_rate=quad_rate,
            tau=tau,
            max_dev=max_dev,
        )

        self.volume = blocks.multiply_const_ff(rx_volume)

        self.connect((self.audio_source, 0), (self.voice_lpf, 0))
        self.connect((self.voice_lpf, 0), (self.nbfm_tx, 0))
        self.connect((self.nbfm_tx, 0), (self.tx_attn, 0))
        self.connect((self.tx_attn, 0), (self.channel, 0))
        self.connect((self.channel, 0), (self.nbfm_rx, 0))
        self.connect((self.nbfm_rx, 0), (self.volume, 0))
        self.connect((self.volume, 0), (self.audio_sink, 0))


def parse_args():
    parser = argparse.ArgumentParser(description="GNU Radio voice NBFM simulation")
    parser.add_argument("--audio-rate", type=int, default=48000, help="Audio sample rate")
    parser.add_argument("--quad-rate", type=int, default=240000, help="NBFM quad rate")
    parser.add_argument("--max-dev", type=float, default=5000.0, help="FM max deviation (Hz)")
    parser.add_argument("--tau", type=float, default=75e-6, help="Pre/de-emphasis time constant")
    parser.add_argument("--noise", type=float, default=0.01, help="Channel noise voltage")
    parser.add_argument("--tx-gain", type=float, default=1.0, help="Channel attenuation/gain")
    parser.add_argument("--volume", type=float, default=1.0, help="Output volume")
    parser.add_argument("--mic", default="default", help="Microphone device name")
    parser.add_argument("--spk", default="default", help="Speaker device name")
    return parser.parse_args()


def main():
    args = parse_args()

    tb = VoiceFmSim(
        audio_rate=args.audio_rate,
        quad_rate=args.quad_rate,
        max_dev=args.max_dev,
        tau=args.tau,
        noise_voltage=args.noise,
        tx_gain=args.tx_gain,
        rx_volume=args.volume,
        mic_device=args.mic,
        spk_device=args.spk,
    )

    def stop_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    tb.start()
    print("Voice FM simulation running. Press Ctrl+C to stop.")
    signal.pause()


if __name__ == "__main__":
    main()

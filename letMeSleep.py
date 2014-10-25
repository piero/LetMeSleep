#!/usr/bin/python

# The MIT License (MIT)
#
# Copyright (c) 2014 Piero Cornice
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import math
import time
import signal
import os.path
import logging
import argparse
import subprocess

try:
    # This will only work on RPi
    import RPi.GPIO as GPIO
except ImportError, e:
    if e.message != 'No module named RPi.GPIO':
        raise

# FM range in Europe
fm_start = 87.5
fm_end = 108.0

interrupted = False
jamming = False
freq_delta = 0.2


def resetGpio4():
    try:
        # This will only work on RPi
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(4, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
        GPIO.cleanup()
    except NameError:
        pass


def cleanupAndExit():
    resetGpio4()
    print("Bye :)")
    sys.exit(0)


def sigint_handler(signum, frame):
    global interrupted
    global jamming

    print('[x] SIGINT')
    interrupted = True
    if jamming:
        cleanupAndExit()


def jam(frequency, wav_file, sweeping=True):
    pifm = 'tools/pifm'

    if not os.path.exists(pifm) or not os.path.isfile(pifm):
        print("Command not found: %s" % pifm)
        return

    cmd = "%s %s %s 44100 stereo" % (pifm, wav_file, frequency)

    if sweeping:
        p = subprocess.Popen(cmd, shell = True)
        time.sleep(1)
        try:
            os.killpg(p.pid, signal.SIGINT)
        except Exception:
            pass
        resetGpio4()

    else:
        # We use 'call' to wait for the process to finish.
        # However we pass out process group, so that it can get signals.
        p = subprocess.call(cmd, shell = True, preexec_fn=os.setsid)


def getFrequencyToJam(freq):
    global jamming
    jamming = True

    freqToJam = ""

    while len(freqToJam) == 0:
        try:
            choice = raw_input("""
Which frequency shall I jam?
    1) %.2f (current)
    2) %.2f (previous)
    or enter another frequency.

Choice: """ % (freq, freq - freq_delta))

            if choice == "1": freqToJam = "{:.2f}".format(freq)
            elif choice == "2": freqToJam = "{:.2f}".format(freq - freq_delta)
            else: freqToJam = choice
        except ValueError:
            pass

    return freqToJam


def sweepFrequencies(freq, endFreq):
    global interrupted

    while freq <= endFreq and not interrupted:
        try:
            freqToJam = "{:.2f}".format(freq)
            print("Jamming %s" % freqToJam)

            jam(freqToJam, 'sounds/sine.wav', sweeping = True)

            if freq < endFreq:
                freq += freq_delta
            else:
                break

        except KeyboardInterrupt:
            break

    interrupted = False
    return freq


def check_file_esists(value):
    if not os.path.exists(value) or not os.path.isfile(value):
        raise argparse.ArgumentTypeError("File not found: %s" % value)
    return value


def check_min_fm_range(value):
    fvalue = float(value)
    if fvalue < fm_start:
        raise argparse.ArgumentTypeError("StartFreq %s is below the minimum (%.2f)" % value, fm_start)
    return fvalue


def check_max_fm_range(value):
    fvalue = float(value)
    if fvalue > fm_end:
        raise argparse.ArgumentTypeError("StartFreq %s is above the maximum (%.2f)" % value, fm_end)
    return fvalue


def initArgParser():
    parser = argparse.ArgumentParser(description = "Let me f***n' sleep!")
    parser.add_argument('-f', '--file',
        nargs = '?',
        help = 'Give priority to frequency in the given file',
        default = 'common_frequencies.txt')
    parser.add_argument('-v', '--verbose',
        type = int,
        choices = (1, 2, 3),
        nargs = '?',
        help = 'Verbosity level (1 = error, 2 = normal, 3 = debug',
        default = 2)
    parser.add_argument('wavFile',
        metavar = 'WavFile',
        help = 'File to jam the air with (WAV 44100 stereo',
        type = check_file_esists)
    parser.add_argument('startFreq',
        metavar = 'StartFreq',
        help = 'Starting frequency (min %.2f)' % fm_start,
        type = check_min_fm_range)
    parser.add_argument('endFreq',
        metavar = 'EndFreq',
        help = 'Ending frequency (max %.2f)' % fm_end,
        type = check_max_fm_range)
    return parser


def main():
    if not os.geteuid() == 0:
        print("You must be root to run this script.")
        sys.exit(1)

    signal.signal(signal.SIGINT, sigint_handler)

    resetGpio4()

    parser = initArgParser()
    args = parser.parse_args()
    
    verbosity = logging.INFO
    if args.verbose == 1:
        verbosity = logging.WARNING
    elif args.verbose == 3:
        verbosity = logging.DEBUG

    wavFile = args.wavFile
    startFreq = args.startFreq
    endFreq = args.endFreq
    print("Sweeping frequencies between %.2f and %.2f.\nPress CTRL+C to stop.\n" % (startFreq, endFreq))

    freq = sweepFrequencies(startFreq, endFreq)
    freqToJam = getFrequencyToJam(freq)

    print('Jamming %s' % freqToJam)
    jam(freqToJam, wavFile, sweeping = False)
    cleanupAndExit()


if __name__ == '__main__':
    main()

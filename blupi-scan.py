#!/usr/bin/env python

import sys
import time
import os
import subprocess as sp
from os import devnull
from collections import deque
from math import sqrt


freqmin = 380000000 # european uplink
freqmax = 385000000 # this should work for most for europe

sensitivity = 50
sysdamping = 10
freqdamping = 100
powerfftw_path = "/usr/local/bin/rtl_power_fftw"
baseline_path = "./baseline_data.dat"
totalbins = 960 * 3 # DO NOT CHANGE
ppm_offset = 7
bline_int_t = 600 # Set to around 600 (10m)

# Global that we'll keep
dvnll = open(devnull, 'wb')

# Functions
def average(p): return sum(p) / float(len(p))

def variance(p): return [(x - average(p))**2 for x in p]

def std_dev(p): return sqrt(average(variance(p)))

def alert(p):
	freq = round(p[0] /1000000, 4)
	print("At " + time.strftime("%H:%M:%S") + ", a " + str(round(p[1], 1)) + " dB/Hz signal was detected at " + str(freq) + " MHz.")
	# here, you can add a custom alert like gpio buzzers, leds or displays

def bline_build(fmin, fmax, bins, b_time, offset, bpath):
	t = "-t " + str(b_time)
	array = []
	spect = "-f " + str(fmin) + ":" + str(fmax)
	b_bins = "-b " + str(int(bins/3))

	base_gen = sp.Popen([powerfftw_path, spect, t, offset, b_bins], stdout=sp.PIPE, stderr=dvnll, shell=False)
	print([powerfftw_path, spect, t, offset, b_bins])
	for line in iter(base_gen.stdout.readline, b""):

		with open(baseline_path, 'a') as baselinefile:
			baselinefile.write(str(line)[2:-3] + '\n')

if __name__ == '__main__':

	# Parameter formatting
	spect = "-f " + str(freqmin) + ":" + str(freqmax)

	fftb = totalbins / 3

	fftbins = "-b " + str(int(fftb))
	ppm = "-p " + str(int(ppm_offset))
	otherargs = "-c"
	rolling = []
	rolling_avg = deque([])
	sweep = deque([])
	i = 0
	stddev = 100
	baseline_file = "-B " + str(baseline_path)
	

	# Ready, set, GO!
	try:
		print("Starting up at", time.strftime("%H:%M:%S") + "...")
		
		# Check for baseline file
		if not os.path.isfile(baseline_path):

			print("Couldn't find a baseline file. Generating. This will take",bline_int_t/60,"min")

			# Generate said baseline file
			bline_build(freqmin, freqmax, fftb, bline_int_t, ppm, baseline_path)
			print("Baseline file generation completed at", time.strftime("%H:%M:%S") + ". Starting up!")

		rpf = sp.Popen([powerfftw_path, spect, otherargs, ppm, fftbins, baseline_file], stdout=sp.PIPE, stderr=dvnll, shell=False)
		print([powerfftw_path, spect, otherargs, ppm, fftbins, baseline_file])
		# Let's see what's going on with rtl_power_fftw
		for line in iter(rpf.stdout.readline, b""):
			# Ignore garbage output
			if not (bytes('#', "utf-8") in line or not line.strip()):

				floats = list(map(float, line.split()))

				# Create 2D array if it isn't already defined
				if len(rolling) < totalbins: rolling.append(deque([]))

				rolling[i].append(floats[1])
				sweep.append(floats[1])

				# Let's start filtering...
				if len(rolling[i]) >= freqdamping:
					rolling[i].popleft()
					alarmthresh = average(rolling[i]) + stddev / sensitivity * 25000

					# There be coppers!
					if floats[1] > alarmthresh:
						alert(floats)

				# Maintain sweep length at the total number of samples
				if len(sweep) > totalbins: sweep.popleft()

				# Increment or reset indexer (i)
				if i < totalbins - 1: i = i + 1
				else: 
					i = 0

					# Maintain rolling_avg
					rolling_avg.append(average(sweep))

					if len(rolling_avg) > sysdamping: 
						rolling_avg.popleft()
						stddev = std_dev(rolling_avg)


	except (KeyboardInterrupt, SystemExit): # Press ctrl-c
		print("\n", "Buh-bye")
#!/usr/bin/env python3

# Joana Cabrera
# 3/15/2020 
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
import time
import matplotlib as mpl
from TubeToWell import *


class Well:
	""" A class for individual wells in the matplotlib plot
	"""
	def __init__(self, center, shape, size_param):
		self.center = center
		self.size_param = size_param
		if shape == 'circle':
			self.marker = Circle(self.center, radius=size_param, color='gray', zorder=0)
		elif shape == 'square':
			self.marker = Rectangle(self.center, width=size_param, height=size_param, color = 'gray', zorder=0)
		self.barcode = ''

	def markEmpty(self):
		self.marker.set_color('gray')
		self.marker.zorder=0
		
	def markFilled(self):
		self.marker.set_color('red')
		self.marker.zorder=1

	def markTarget(self):
		self.marker.set_color('yellow')
		self.marker.zorder=2

	def markRescanned(self):
		self.marker.set_color('blue')
		self.marker.zorder=2

class PlateLighting:
	""" A class for lighting up the corresponding well using matplotlib
	"""
	def __init__(self, a1_x, a1_y, shape, size_param, well_spacing):

		# set up plot 
		mpl.rcParams['toolbar'] = 'None'
		plt.style.use('dark_background')
		self.fig, self.ax = plt.subplots()
		self.fig.tight_layout()
		self.ax.axis('equal')
		self.fig.subplots_adjust(bottom=0)
		self.ax.axis('off')
		self.well_dict = {} # links barcode to Well object

		# set up tube to well
		self.ttw = TubeToWell()

		# draw all the empty wells
		self.wells = [] # column wise list of wells

		# load config file

		for x in range(12):
			x_coord = a1_x + (well_spacing * x)
			for y in range(8):
				y_coord = a1_y - (well_spacing * y)
				well = Well((x_coord,y_coord), shape, size_param)
				self.wells.append(well)
				self.ax.add_artist(well.marker)
		
		# keep track of target index
		self.well_idx = 0

	def switchWell(self, check_input):
		location = self.ttw.checkTubeBarcode(check_input)
		if location:
			self.target = self.wells[self.well_idx]
			self.well_idx += 1
			self.target.markTarget()
			self.target.location = location
			self.target.barcode = check_input
			self.fig.canvas.draw()

			# the well will be marked as filled when the next target is marked 
			self.target.markFilled()

			# link target well object to a barcode in the well_dict dictonary
			self.well_dict[self.target.barcode] = self.target

			return True # return true if new tube

		elif check_input in self.ttw.scanned_tubes:
			already_scanned_tube = self.well_dict[check_input]
			already_scanned_tube.markRescanned()
			self.fig.canvas.draw()
			
			# the well will be marked as filled when the next target is marked 
			already_scanned_tube.markFilled()
			return False # return false if not new tube

	def show(self):
		plt.show()

	def reset(self):
		# mark all wells as empty
		for w in self.wells:
			w.markEmpty()
		self.fig.canvas.draw()

		# clear well dictionary
		self.well_dict.clear()
		self.well_idx = 0

		# reset TubeToWell object
		self.ttw.reset()
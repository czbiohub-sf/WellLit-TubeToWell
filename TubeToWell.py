#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020


# updated 8/24/2020 Andrew Cote

import csv, time, os, re, json, uuid
from WellLit.Transfer import TStatus, TError, TransferProtocol, Transfer
import numpy as np

class TubeToWell:
	""" A class for mapping scanned tubes to a well location.
	"""
	def __init__(self):

		# load in configuration settings
		# if records_dir is not present, default to folder in this repo
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.num_wells = configs['num_wells']
		self.records_path = configs['records_dir']
		self.csv_name = ''

		if not os.path.isdir(self.records_path):
			self.records_path = cwd + '/records/'

		# make a list of the well row characters and well columns
		if self.num_wells == '384':
			self.well_rows = [chr(x) for x in range(ord('A'), ord('P') + 1)]
			self.well_cols = [i for i in range(1, 25)]
		else:
			self.well_rows = [chr(x) for x in range(ord('A'), ord('H') + 1)]
			self.well_cols = [i for i in range(1, 13)]

		# make a list of well names in column wise order
		# and a dictionary of samples, where key is well and value is sample barcode
		self.well_names = []
		self.tube_locations = {}
		self.scanned_tubes = []
		self.current_idx = 0

		self.canUndo = False
		self.warningsMade = False

		for num in self.well_cols:
			for letter in self.well_rows:
				well_name = letter + str(num)
				self.well_names.append(well_name)
				self.tube_locations[well_name] = None

		self.aliquoter = ''
		self.recorder = ''
		self.plate_timestr = ''
		self.plate_barcode = ''
		self.metadata = ''

	def makeWarningFile(self):
		self.warningsMade = True
		warning_file_path = os.path.join(self.records_path + self.csv_name + '_WARNING')

		with open(warning_file_path + '.csv', 'w', newline='') as csvFile:
			writer = csv.writer(csvFile)
			writer.writerows(self.metadata)
			csvFile.close()

	def openCSV(self, recorder, aliquoter, plate_barcode): 
		# metadata
		self.aliquoter = aliquoter
		self.recorder = recorder
		self.plate_timestr = time.strftime("%Y%m%d-%H%M%S")
		self.plate_barcode = plate_barcode

		# this will be the filename header for all files associated with this run
		self.csv_name = self.plate_timestr + '_' + plate_barcode + '_tube_to_plate'

		# set up file path for the output file
		csv_file_path = os.path.join(self.records_path, self.csv_name)

		# use the first 5 rows of the output file for metadata
		self.metadata = [['%Plate Timestamp: ', self.plate_timestr], ['%Plate Barcode: ', plate_barcode], ['%Recorder Name: ', recorder], ['%Aliquoter Name: ', aliquoter], ['%Timestamp', 'Tube Barcode', 'Location']]
		with open(self.csv_file_path + '.csv', 'w', newline='') as csvFile:
			writer = csv.writer(csvFile)
			writer.writerows(self.metadata)

	def undoTube(self):
		# will not enable undo button if there is nothing in scanned tubes or the user has not scanned the plate and barcode
		if not self.canUndo:
			raise TError('Cannot undo previous transfer')

		elif self.scanMode and self.plateLighting.ttw.scanned_tubes:
			if not self.warningsMade:
				self.makeWarningFile()

			# remove last row from CSV file
			original_rows = []
			with open(self.plateLighting.ttw.csv_file_path + '.csv', 'r') as csvFile:
				reader = csv.reader(csvFile)
				for row in reader:
					original_rows.append(row)
			original_rows_edited = original_rows[:-1]
			with open(self.plateLighting.ttw.csv_file_path + '.csv', 'w', newline='') as csvFile:
				writer = csv.writer(csvFile)
				writer.writerows(original_rows_edited)
				csvFile.close()

			# clear the target on the plate lighting plot
			self.plateLighting.target.markEmpty()
			self.plateLighting.fig.canvas.draw()

			# move back one index the TubeToWell and PlateLighting objects
			self.plateLighting.ttw.scanned_tubes = self.plateLighting.ttw.scanned_tubes[:-1]
			undone_barcode = self.plateLighting.target.barcode
			undone_location = self.plateLighting.ttw.tube_locations[undone_barcode]
			self.plateLighting.ttw.tube_locations[undone_barcode] = ''
			self.plateLighting.well_idx -= 1
			self.plateLighting.ttw.current_idx -= 1
			self.canUndo = False  # do not allow the user to undo more than once in a row

			# write to warning file
			warn_timestr = time.strftime("%Y%m%d-%H%M%S")
			warning_row = [[warn_timestr, undone_barcode, undone_location, 'unscanned']]
			with open(self.warning_file_path + '.csv', 'a', newline='') as csvFile:
				writer = csv.writer(csvFile)
				writer.writerows(warning_row)
				csvFile.close()

			# show popup confirming that the tube was unscanned
			self.error_popup.title = "Notification"
			self.ids.tube_barcode_label.text = ''
			self.error_popup.show('Tube Unscanned')

			self.ids.notificationLabel.font_size = 50
			self.ids.notificationLabel.text = 'Please scan tube'

	def isPlate(self, check_input):
		if re.match(r'SP[0-9]{6}$', check_input) or check_input == 'EDIT':
			return True
		return False

	def isName(self, check_input):
		if any(char.isdigit() for char in check_input):
			return False
		elif check_input == 'EDIT':
			return True
		return True

	def isTube(self, check_input):
		if re.match(r'[A-Z][0-9]{1,5}', check_input):
			return True
		elif check_input == 'CONTROL' or check_input == 'EDIT' :
			return True
		return False

	def checkTubeBarcode(self, check_input):
		# check if the barcode was already scanned
		if check_input in self.scanned_tubes and check_input != 'CONTROL' and check_input != 'EDIT':
			print('this tube was already scanned')
			return False
			# light up corresponding well
		else: 
			# write to csv if it is a new barcode
			with open(self.csv_file_path +'.csv', 'a', newline='') as csvFile:
				# log scan time
				scan_time = time.strftime("%Y%m%d-%H%M%S")
				location = self.well_names[self.current_idx]
				self.current_idx += 1
				row = [[scan_time, check_input, location]]
				writer = csv.writer(csvFile)
				writer.writerows(row)
				csvFile.close()

			# add to barcode to scanned_tubes list
			self.scanned_tubes.append(check_input)

			# link barcode to a well location
			self.tube_locations[check_input] = location
			# print (location)
			return location

	def reset(self):
		# clear tube locations
		for w in self.well_names:
			self.tube_locations[w] = None

		# reset index
		self.current_idx = 0

		# reset scanned tubes
		self.scanned_tubes.clear()

class TTWTransferProtocol(TransferProtocol):

	def __init__(self, wtw=None, df=None, **kwargs):
		super(TTWTransferProtocol, self).__init__(**kwargs)
		self.msg = ''
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.num_wells = configs['num_wells']
		self.well_names = []

	def buildTransferProtocol(self, ttw: TubeToWell):
		# build list of wells
		if self.num_wells == '384':
			self.well_rows = [chr(x) for x in range(ord('A'), ord('P') + 1)]
			self.well_cols = [i for i in range(1, 25)]
		else:
			self.well_rows = [chr(x) for x in range(ord('A'), ord('H') + 1)]
			self.well_cols = [i for i in range(1, 13)]

		for num in self.well_cols:
			for letter in self.well_rows:
				well_name = letter + str(num)
				self.well_names.append(well_name)

		# build transfer protocol:
		self.num_transfers = len(self.num_wells)
		self.tf_seq = np.empty(self.num, dtype=object)

		current_idx = 0
		for well in self.well_names:
			unique_id = str(uuid.uuid1())
			tf = Transfer(unique_id, dest_plate=ttw.plate_barcode, dest_well=well)
			self.transfers[unique_id] = tf
			self.tf_seq[current_idx] = unique_id

		self._current_idx = 0  # index in tf_seq
		self.current_uid = self.tf_seq[self._current_idx]

	def plateComplete(self):
		self.synchronize()
		self.sortTransfers()
		for unique_id in self.tf_seq:
			if self.transfers[unique_id].status == TStatus.uncompleted:
				return False
		return True

	def complete(self, barcode):
		if self.plateComplete():
			self.log('Plate is complete, press reset to start a new plate')
		if self.canUpdate():
			self.transfers[self.current_uid]['source_tube'] = barcode
			self.transfers[self.current_uid].updateStatus(TStatus.completed)
			self.log('transfer complete: %s' % self.tf_id())




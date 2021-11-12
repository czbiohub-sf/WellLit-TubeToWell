#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020


# updated 8/24/2020 Andrew Cote

import csv, time, os, re, json, uuid, logging
from WellLit.Transfer import TStatus, TError, TConfirm, TransferProtocol, Transfer
import numpy as np
from pathlib import Path
import pandas as pd

class TubeToWell:
	""" A class for mapping scanned tubes to a well location.

	functions at this level throw exceptions caught by TubeToWellWidget
	"""
	def __init__(self):

		# load in configuration settings
		# if records_dir is not present, default to folder in this repo
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.num_wells = configs['num_wells']
		self.records_dir = configs['records_dir']
		self.samples_dir = configs['samples_dir']
		self.controls = configs['controls']
		self.barcode_to_well = {}
		self.csv = ''
		self.warning_file_path = ''

		if not os.path.isdir(self.records_dir):
			self.records_dir = cwd + '/records/'

		if not os.path.isdir(self.samples_dir):
			self.samples_dir = cwd + '/samples/'

		self.warningsMade = False
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
		self.user = ''
		self.tp = None
		self.sample_list = None
		self.tp = TTWTransferProtocol(self, controls=self.controls)

	def reset(self):
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
		self.user = ''
		self.csv = ''
		self.tp = TTWTransferProtocol(self, controls=self.controls)
		self.warningsMade = False
		self.warning_file_path = ''
		self.sample_list = None

	def tp_present(self):
		if self.tp is not None:
			return True
		else:
			self.log('Cannot perform action, finish entering metadata to begin transfer process')
			raise TError(self.msg)

	def next(self, barcode):
		"""
		Checks to see if a transfer protocol is present, and if a sample list has been loaded
		marks the current scanned barcode as complete and writes transfer record file
		"""
		if self.tp_present():

			# First check to see if this is a specifically assigned barcode
			# (i.e a tube that should go to a specific well)
			if barcode in self.barcode_to_well.keys():
				if self.tp.uniqueBarcode(barcode):
					unique_id  = str(uuid.uuid1())
					well = self.barcode_to_well[barcode]
					tf = Transfer(unique_id, dest_plate=self.plate_barcode, dest_well=well)
					self.tp.tf_seq.insert(self.tp._current_idx, tf)

			if self.sample_list is None:
				self.tp.next(barcode)
				self.writeTransferRecordFiles()
			else:
				self.checkSampleList(barcode)
				self.tp.next(barcode)
				self.writeTransferRecordFiles()

	def skip(self):
		if self.tp_present():
			self.tp.skip()
			self.writeTransferRecordFiles()

	def failed(self):
		if self.tp_present():
			self.tp.failed()
			self.writeTransferRecordFiles()

	def undo(self):
		if not self.warningsMade:
			self.makeWarningFile()
			self.warningsMade = True
		self.writeWarning()
		if self.tp_present():
			self.tp.undo()
			self.writeTransferRecordFiles()

	def log(self, msg):
		self.msg = msg
		logging.info(msg)

	def checkSampleList(self, barcode):
		if barcode not in self.sample_list:
			raise TError('Sample barcode not in list of pre-defined sample names.')

	def loadCSV(self, filename):
		"""
		Loads in a csv file of sample names to be verified.
		"""
		try:
			# read the spreadsheet assuming first column is list of sample names, skipping the first row
			samples_df = pd.read_csv(filename, skiprows=1, names=['sample'], dtype=str)
			self.sample_list = [s for s in samples_df['sample']]
			self.log('Successfully loaded %s sample names' % len(self.sample_list))
		except:
			self.log('Failed to load file csv \n %s' % csv)
			raise TError(self.msg)

	def loadWellConfigurationCSV(self, filename):
		"""Loads a well configuration csv/excel sheet.

		This sheet uses a pre-defined template which maps well numbers (e.g A1/A2/D3/H5, etc.)
		to their availability (i.e whether a sample can be pipetted into that well or not).
		Additionally instead of marking a well as "Available" or "Not Available", users can also map a well
		to a specific sample barcode. If a well is mapped to a specific barcode, only the sample with the corresponding barcode
		can be aliquoted into that well.
		"""

		try:
			wells_config_df = pd.read_csv(filename, header=0, names=["wells", "availability", "barcodes"])
		except:
			self.log(f"Failed to load well configuration csv (tried to load {filename}).")
			raise TError(self.msg)

		self.parseWellConfigurationCSV(wells_config_df)

	def parseWellConfigurationCSV(self, wells_config_df):
		"""Parses the well_configuration.csv and performs some basic input validation.

		Note that by default wells are assumed to be available (i.e you don't need to explicitly mark
		wells as being "Available" in the csv, however there is no harm in doing so). Only wells that 
		should be exempt from aliquoting or wells which map to a specific tube need to be stated in the CSV sheet.

		If there are any input errors, this function will fail and raise a specific error alerting the user 
		of the error(s) in the csv sheet that need to be rectified.
		"""
		valid_wells = self.tp.generateWellList()

		# Clean-up data
		wells_config_df["wells"] = wells_config_df["wells"].str.upper()
		wells_config_df["availability"] = wells_config_df["availability"].str.upper()

		# First validate that the user entered wells are valid
		no_nan_wells = wells_config_df[wells_config_df["wells"].notna()]["wells"]
		invalid_wells = ~no_nan_wells.isin(valid_wells)
		if any(invalid_wells):
			list_of_invalid_rows = wells_config_df[invalid_wells]
			self.log(f"Invalid well(s) encountered in column A: {list_of_invalid_rows}).")
			raise TError(self.msg)

		# Well names are valid, next check available/not available column for invalid entries
		no_nan_availability = wells_config_df[wells_config_df["availability"].notna()]["availability"]
		invalid_availability = ~no_nan_availability.isin(["AVAILABLE", "NOT AVAILABLE"])
		if any(invalid_availability):
			list_of_invalid_rows = wells_config_df[invalid_availability]
			self.log(f"Invalid Available/Not Available entry in column B: \n{list_of_invalid_rows}")
			raise TError(self.msg)

		# Add the unavailable wells and mark the wells reserved for specific barcodes
		for _, row in wells_config_df.iterrows():
			well_number = row["wells"]
			availability = row["availability"]
			barcode = row["barcodes"]

			if availability == "NOT AVAILABLE" and not pd.isna(barcode):
				self.log(f"A well has been specified as 'Not Available' AND a barcode has been assigned to this well. \
				Only one or the other should be assigned. Please fix this in the sheet and try again.\
				This issue was found on the row with: {well_number, availability, barcode}")
				raise TError(self.msg)
			elif availability == "NOT AVAILABLE":
				self.controls.append(well_number)
			elif barcode != None:
				self.barcode_to_well[barcode] = well_number
		

	def setSaveDirectory(self, directory):
		"""Sets the location to save records """
		self.records_dir = directory

	def writeWarning(self):
		""""
		Generates warning file of undone transfers
		"""
		if self.tp is not None:
			self.tp.current_idx_decrement()
			transfer = self.tp.current_transfer
			self.tp.current_idx_increment()
			keys = ['timestamp', 'source_tube', 'dest_plate', 'dest_well', 'status']
			with open(self.warning_file_path + '.csv', 'a', newline='') as csvFile:
				writer = csv.writer(csvFile)
				warning_row = [transfer[key] for key in keys]
				warning_row.append(' Marked Undone at ' + time.strftime("%Y%m%d-%H%M%S"))
				writer.writerow(warning_row)
				csvFile.close()

	def makeWarningFile(self):
		"""
		Creates a warning file is none exists already
		"""
		self.warningsMade = True
		self.warning_file_path = os.path.join(self.records_dir + self.csv + '_WARNING')
		with open(self.warning_file_path + '.csv', 'w', newline='') as csvFile:
			writer = csv.writer(csvFile)
			writer.writerows(self.metadata)
			writer.writerow(['Timestamp', 'Source Tube', 'Destination well'])
			csvFile.close()

	def setMetaData(self, plate_barcode, user):
		"""
		Sets metadata for records produced and assigns a new Transfer Protocol to this class
		"""
		self.user = user
		self.timestamp = time.strftime("%Y%m%d-%H%M%S")
		self.plate_barcode = plate_barcode
		self.csv = self.timestamp + '_' + self.plate_barcode + '_tube_to_plate'

	def writeTransferRecordFiles(self):
		"""
		Writes metadata from current transfer sequence to a csv file
		"""
		record_path_filename = Path(self.records_dir + self.csv + '.csv')

		# use the first 5 rows of the output file for metadata
		self.metadata = [['%Plate Timestamp: ', self.timestamp],
						 ['%Username: ', self.user],
						 ['%Plate Barcode: ', self.plate_barcode],
						 ['%Timestamp', 'Tube Barcode', 'Location']]
		try:
			with open(record_path_filename, 'w', newline='') as logfile:
				log_writer = csv.writer(logfile)
				log_writer.writerows(self.metadata)
				keys = ['timestamp', 'source_tube', 'dest_well']
				for transfer_id in self.tp.tf_seq:
					transfer = self.tp.transfers[transfer_id]
					if transfer['status'] is not 'uncompleted':
						log_writer.writerow([transfer[key] for key in keys])
				self.log('Wrote transfer record to ' + str(record_path_filename))
		except:
			raise TError('Cannot write record file to ' + str(record_path_filename))

	def isPlate(self, check_input):
		return True

	def isName(self, check_input):
		return True


class TTWTransferProtocol(TransferProtocol):
	"""
	Data model for iterating through a sequence of transfers into Wells by column order, capturing metadata
	and tracking tube origins and transfer status
	"""
	def __init__(self, ttw: TubeToWell, controls=None, **kwargs):
		super(TTWTransferProtocol, self).__init__(**kwargs)
		self.msg = ''
		self.controls = controls
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.num_wells = configs['num_wells']
		self.buildTransferProtocol(ttw)
		self.lightup_well = None               # special well that can be lit up under different edge cases (e.g. rescan)

	def generateWellList(self):
		"""Returns a list of well names (e.g A1, A2, etc.) (depending on whether a 96/384 well plate is used)."""
		well_names = []
		# build list of wells
		if self.num_wells == '384':
			well_rows = [chr(x) for x in range(ord('A'), ord('P') + 1)]
			well_cols = [i for i in range(1, 25)]
		else:
			well_rows = [chr(x) for x in range(ord('A'), ord('H') + 1)]
			well_cols = [i for i in range(1, 13)]

		for num in well_cols:
			for letter in well_rows:
				well_name = letter + str(num)
				well_names.append(well_name)

		return well_names

	def buildTransferProtocol(self, ttw: TubeToWell):
		well_names = self.generateWellList()
		valid_well_names = []
		for well_name in well_names:
			if (well_name not in self.controls) and (well_name not in ttw.barcode_to_well.keys()):
				valid_well_names.append(well_name)

		# build transfer protocol:
		self.tf_seq = []

		current_idx = 0
		for well in valid_well_names:
			unique_id = str(uuid.uuid1())
			# TODO set well here (check dictionary for barcode -> well mapping, otherwise just use the next well)
			tf = Transfer(unique_id, dest_plate=ttw.plate_barcode, dest_well=well)
			self.transfers[unique_id] = tf
			self.tf_seq.append(unique_id)
			current_idx += 1

		self._current_idx = 0
		self.synchronize()

	def canUpdate(self):
		"""
		Checks to see that current transfer has not already been timestamped with a status.
		Raises TError if transfer has already been updated
		Raises TConfirm is plate is complete
		"""
		self.synchronize()
		self.sortTransfers()
		if self.current_transfer['timestamp'] is None:
			return True
		else:
			self.log('Cannot update transfer: %s Status is already marked as %s ' %
					 (self.tf_id(), self.transfers[self.current_uid]['status']))
			msg = self.msg

			if self.plateComplete():
				self.log('Plate is complete, press reset to start a new plate')
				raise TConfirm(msg + self.msg)
			else:
				raise TError(self.msg)

	def step(self):
		"""
		Moves index to the next transfer in a plate.
		Raises TConfirm is plate is complete
		"""
		self.sortTransfers()
		self.canUndo = True
		if self.plateComplete():
			pass
		else:
			self.current_idx_increment()

	def undo(self):
		"""
		Overwrites default undo action to step back twice, overwrite the completed transfer and mark as started,
		then step forwards and mark the started transfer as uncomplete
		"""
		self.synchronize()
		self.sortTransfers()
		if self.canUndo:
			self.current_idx_decrement()
			self.current_idx_decrement()

			if self._current_idx > 0:
				self.current_transfer.updateStatus(TStatus.started)
				self.current_idx_increment()
				self.current_transfer.resetTransfer()
			else:
				self.current_transfer.resetTransfer()
			self.sortTransfers()
			self.canUndo = False
			self.log('transfer marked incomplete: %s' % self.tf_id())
		else:
			self.log('Cannot undo previous operation')
			raise TError('Cannot undo previous operation')

	def plateComplete(self):
		"""
		"""
		self.synchronize()
		self.sortTransfers()
		for unique_id in self.tf_seq:
			if self.transfers[unique_id].status == TStatus.uncompleted:
				return False
		return True

	def next(self, barcode):
		"""
		Marks the current transfer as complete if started and the next transfer as started is uncomplete
		if current transfer is complete, raises
		"""
		self.synchronize()

		if self.plateComplete():
			self.log('Plate is complete, press Finish Plate to start a new plate')
			raise TConfirm(self.msg)

		if self.canUpdate():
			if self.isTube(barcode):
				if self.uniqueBarcode(barcode):
					# assign barcode to current transfer and update it as started
					self.current_transfer['source_tube'] = barcode
					self.current_transfer.updateStatus(TStatus.started)

					# if it's after the first transfer, update the previous transfer as complete
					if self._current_idx > 0:
						previous_transfer = self.transfers[self.tf_seq[self._current_idx - 1]]
						previous_transfer.updateStatus(TStatus.completed)

					self.sortTransfers()
					self.log('transfer started: %s' % self.tf_id())
					self.lightup_well = None
					self.step()
				else:

					if self._current_idx > 0:
						previous_transfer = self.transfers[self.tf_seq[self._current_idx - 1]]
						previous_transfer.updateStatus(TStatus.completed)

					self.sortTransfers()
					tf = self.findTransferByBarcode(barcode)
					self.log('Tube already scanned into well %s' % tf['dest_well'])
					self.lightup_well = tf['dest_well']
					raise TError(self.msg)
			else:
				self.log('%s is not a valid barcode' % barcode)
				raise TError(self.msg)

		self.sortTransfers()


	def complete(self, barcode):
		"""
		Assignes a tube barcode to a specified transfer according to the transfer sequence
		raises TError if the barcode is improperly formatted or already scanned
		raises TConfirm if the plate is already complete
		"""
		self.synchronize()
		self.sortTransfers()
		if self.plateComplete():
			self.log('Plate is complete, press reset to start a new plate')
			raise TConfirm(self.msg)
		if self.canUpdate():
			if self.isTube(barcode):
				if self.uniqueBarcode(barcode):
					self.current_transfer['source_tube'] = barcode
					self.current_transfer.updateStatus(TStatus.completed)
					self.log('transfer complete: %s' % self.tf_id())
					self.step()
				else:
					tf = self.findTransferByBarcode(barcode)
					self.log('Tube already scanned into well %s' % tf['dest_well'])
					raise TError(self.msg)
			else:
				self.log('%s is not a valid barcode' % barcode)
				raise TError(self.msg)

	def uniqueBarcode(self, barcode):
		for tf_id in self.tf_seq:
			tf = self.transfers[tf_id]
			if barcode == tf['source_tube']:
				return False
		return True

	def findTransferByBarcode(self, barcode):
		for tf_id in self.tf_seq:
			tf = self.transfers[tf_id]
			if barcode == tf['source_tube']:
				return tf
		return None

	def isTube(self, check_input):
		return True



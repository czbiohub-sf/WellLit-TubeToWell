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
		self.csv = ''
		self.warning_file_path = ''

		if not os.path.isdir(self.records_dir):
			self.records_dir = cwd + '/records/'

		if not os.path.isdir(self.samples_dir):
			self.samples_dir = cwd + '/samples/'

		self.warningsMade = False
		self.aliquoter = ''
		self.recorder = ''
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
		self.tp = None
		self.sample_list = None

	def reset(self):
		self.aliquoter = ''
		self.recorder = ''
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
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
		if self.tp_present():
			if self.sample_list is None:
				self.tp.complete(barcode)
				self.writeTransferRecordFiles()
			else:
				self.checkSampleList(barcode)
				self.tp.complete(barcode)
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
		try:
			# read the spreadsheet assuming first column is list of sample names, skipping the first row
			samples_df = pd.read_csv(filename, skiprows=1, names=['sample'])
			samples_list = [s for s in samples_df['sample']]
		except:
			self.log('Failed to load file csv \n %s' % csv)
			raise TError(self.msg)

	def writeWarning(self):
		# looks back one step to mark this as undone
		if self.tp is not None:
			self.tp.current_idx_decrement()
			transfer = self.tp.current_transfer
			self.tp.current_idx_increment()
			keys = ['timestamp', 'source_tube', 'dest_plate', 'status']
			with open(self.warning_file_path + '.csv', 'a', newline='') as csvFile:
				writer = csv.writer(csvFile)
				warning_row = [transfer[key] for key in keys]
				warning_row.append(' Marked Undone at ' + time.strftime("%Y%m%d-%H%M%S"))
				writer.writerow(warning_row)
				csvFile.close()

	def makeWarningFile(self):
		self.warningsMade = True
		self.warning_file_path = os.path.join(self.records_dir + self.csv + '_WARNING')
		with open(self.warning_file_path + '.csv', 'w', newline='') as csvFile:
			writer = csv.writer(csvFile)
			writer.writerows(self.metadata)
			writer.writerow(['Timestamp', 'Source Tube', 'Destination plate', 'Destination well', 'Status'])
			csvFile.close()

	def setMetaData(self, recorder, aliquoter, plate_barcode):
		"""
		Sets metadata for records produced and assigns a new Transfer Protocol to this class
		"""
		self.aliquoter = aliquoter
		self.recorder = recorder
		self.timestamp = time.strftime("%Y%m%d-%H%M%S")
		self.plate_barcode = plate_barcode
		self.csv = self.timestamp + '_' + self.plate_barcode + '_tube_to_plate'
		self.tp = TTWTransferProtocol(self, controls=self.controls)

	def writeTransferRecordFiles(self):
		"""
		Writes metadata from current transfer sequence to a csv file
		"""
		record_path_filename = Path(self.records_dir + self.csv + '.csv')

		# use the first 5 rows of the output file for metadata
		self.metadata = [['%Plate Timestamp: ', self.timestamp],
						 ['%Plate Barcode: ', self.plate_barcode],
						 ['%Recorder Name: ', self.recorder],
						 ['%Aliquoter Name: ', self.aliquoter],
						 ['%Timestamp', 'Tube Barcode', 'Location']]
		try:
			with open(record_path_filename, 'w', newline='') as logfile:
				log_writer = csv.writer(logfile)
				log_writer.writerows(self.metadata)
				log_writer.writerow(['Timestamp', 'Source Tube', 'Destination plate', 'Destination well', 'Status'])
				keys = ['timestamp', 'source_tube', 'dest_plate', 'dest_well', 'status']
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

	def buildTransferProtocol(self, ttw: TubeToWell):
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
				if well_name not in self.controls:
					well_names.append(well_name)

		# build transfer protocol:
		self.tf_seq = np.empty(len(well_names), dtype=object)

		current_idx = 0
		for well in well_names:
			unique_id = str(uuid.uuid1())
			tf = Transfer(unique_id, dest_plate=ttw.plate_barcode, dest_well=well)
			self.transfers[unique_id] = tf
			self.tf_seq[current_idx] = unique_id
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
			self.log('Plate is complete, press reset to start a new plate')
			raise TConfirm(self.msg)
		else:
			self.current_idx_increment()

	def plateComplete(self):
		"""

		"""
		self.synchronize()
		self.sortTransfers()
		for unique_id in self.tf_seq:
			if self.transfers[unique_id].status == TStatus.uncompleted:
				return False
		return True


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



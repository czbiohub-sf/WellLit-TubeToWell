#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020


# updated 8/24/2020 Andrew Cote

import csv, time, os, re, json, uuid, logging
from WellLit.Transfer import TStatus, TError, TConfirm, TransferProtocol, Transfer
import numpy as np
from pathlib import Path

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
		self.records_dir = configs['records_dir']
		self.csv = ''

		if not os.path.isdir(self.records_dir):
			self.records_dir = cwd + '/records/'

		self.canUndo = False
		self.warningsMade = False

		self.aliquoter = ''
		self.recorder = ''
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
		self.tp = None

	def reset(self):
		self.aliquoter = ''
		self.recorder = ''
		self.timestamp = ''
		self.plate_barcode = ''
		self.metadata = ''
		self.msg = ''
		self.csv = ''
		self.tp = TTWTransferProtocol(self)

	def tp_present(self):
		if self.tp is not None:
			return True
		else:
			self.log('Cannot undo, finish entering metadata to begin transfer process')
			raise TError(self.msg)

	def next(self, barcode):
		if self.tp_present():
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
		if self.tp_present():
			self.tp.undo()
			self.writeTransferRecordFiles()

	def log(self, msg):
		self.msg = msg
		logging.info(msg)

	def makeWarningFile(self):
		self.warningsMade = True
		warning_file_path = os.path.join(self.records_dir + self.csv + '_WARNING')

		with open(warning_file_path + '.csv', 'w', newline='') as csvFile:
			writer = csv.writer(csvFile)
			writer.writerows(self.metadata)
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
		self.tp = TTWTransferProtocol(self)

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
				keys = ['timestamp', 'source_tube', 'dest_plate', 'status']
				for transfer_id in self.tp.tf_seq:
					transfer = self.tp.transfers[transfer_id]
					log_writer.writerow([transfer[key] for key in keys])
				self.log('Wrote transfer record to ' + str(record_path_filename))
		except:
			raise TError('Cannot write record file to ' + str(record_path_filename))

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


class TTWTransferProtocol(TransferProtocol):
	"""
	Data model for iterating through a sequence of transfers into Wells by column order, capturing metadata
	and tracking tube origins and transfer status
	"""
	def __init__(self, ttw: TubeToWell, **kwargs):
		super(TTWTransferProtocol, self).__init__(**kwargs)
		self.msg = ''
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.num_wells = configs['num_wells']
		self.buildTransferProtocol(ttw)

	def buildTransferProtocol(self, ttw: TubeToWell):
		self.well_names = []
		# build list of wells
		if self.num_wells == '384':
			self.well_rows = [chr(x) for x in range(ord('A'), ord('P') + 1)]
			self.well_cols = [i for i in range(1, 25)]
		else:
			self.well_rows = [chr(x) for x in range(ord('A'), ord('H') + 1)]
			self.well_cols = [i for i in range(1, 13)]

		# build transfer protocol:
		self.tf_seq = np.empty(int(self.num_wells), dtype=object)

		for num in self.well_cols:
			for letter in self.well_rows:
				well_name = letter + str(num)
				self.well_names.append(well_name)

		current_idx = 0
		for well in self.well_names:
			unique_id = str(uuid.uuid1())
			tf = Transfer(unique_id, dest_plate=ttw.plate_barcode, dest_well=well)
			self.transfers[unique_id] = tf
			self.tf_seq[current_idx] = unique_id
			current_idx += 1

		self._current_idx = 0  # index in tf_seq
		self.current_uid = self.tf_seq[self._current_idx]

	def canUpdate(self):
		"""
		Checks to see that current transfer has not already been timestamped with a status.
		Raises TError if transfer has already been updated
		Raises TConfirm is plate is complete
		"""
		self.synchronize()
		self.sortTransfers()
		current_transfer = self.transfers[self.current_uid]
		if current_transfer['timestamp'] is None:
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
					self.transfers[self.current_uid]['source_tube'] = barcode
					self.transfers[self.current_uid].updateStatus(TStatus.completed)
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
		if re.match(r'[A-Z][0-9]{1,5}', check_input):
			return True
		return False



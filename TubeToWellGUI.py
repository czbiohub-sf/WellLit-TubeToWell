#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import kivy
kivy.require('1.11.1')
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
# noinspection ProblematicWhitespace
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, StringProperty
from datetime import datetime
from pathlib import Path
import logging, os, time, json, csv
from WellLit.WellLitGUI import WellLitWidget, WellLitPopup, ConfirmPopup
from WellLit.Transfer import TError, TConfirm
from TubeToWell import TubeToWell


def on_focus(instance, value):
	# refocus on the text box after defocused by the enter key
	if value:
		pass
	else:
		instance.focus = True

class TubeToWellApp(App):
	def build(self):
		return TubeToWellWidget()

class TubeToWellWidget(WellLitWidget):
	"""
	Scans barcoded tubes and assigns the contents to wells in sequential order on a well plate of either 96 or 384 wells.
	Catches errors thrown by invalid user actions and displays error message in popups
	"""
	dest_plate = StringProperty()

	def __init__(self, **kwargs):
		super(TubeToWellWidget, self).__init__(**kwargs)
		self.ttw = TubeToWell()
		self.ids.textbox.bind(focus=on_focus)
		self.plateLighting = self.ids.dest_plate.pl
		self.scanMode = False
		self.ids.textbox.bind(on_text_validate=self.scanRecorder)
		self.error_popup = WellLitPopup()
		self.confirm_popup = ConfirmPopup()
		self.status = ''


	def undoTube(self):
		try:
			self.ttw.undoTube()
		except TError as err:
			self.showPopup(err, "Unable to undo")
			self.status = self.ttw.status


	def finishPlate(self):
		self.confirm_popup.show()

	def resetAll(self): 
		self.plateLighting.reset()
		
		# restart metadata collection
		self.ids.textbox.funbind('on_text_validate', self.ttw.switchWell)
		self.ids.textbox.funbind('on_text_validate', self.scanAliquoter)
		self.ids.textbox.funbind('on_text_validate', self.scanPlate)
		self.ids.textbox.bind(on_text_validate=self.scanRecorder)
		self.ids.notificationLabel.text = "Please scan the recorder's barcode"

		# reset metadata text
		self.ids.recorder_label.text = '[b]Recorder:[/b] \n'
		self.ids.aliquoter_label.text = '[b]Aliquoter:[/b] \n'
		self.ids.plate_barcode_label.text = '[b]Plate Barcode:[/b] \n'
		self.ids.tube_barcode_label.text = '[b]Tube Barcode:[/b] \n'
		self.ids.notificationLabel.font_size = 50

		self.scanMode = False
		self.canUndo = False
		self.warningsMade = False

	def showBarcodeError(self, barcode_type):
		self.error_popup.title =  "Barcode Error"
		self.error_popup.show('Not a valid ' + barcode_type +' barcode')
		self.ids.textbox.text = ''

	def scanRecorder(self, *args):
		check_input = self.ids.textbox.text
		if self.plateLighting.ttw.isName(check_input):
			self.recorder = check_input
			self.ids.recorder_label.text += check_input 
			self.ids.textbox.text = ''

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind('on_text_validate',self.scanRecorder)
			self.ids.textbox.bind(on_text_validate=self.scanAliquoter)
			self.ids.notificationLabel.text = "Please scan the aliquoter's barcode"
		else: 
			self.showBarcodeError('name')

	def scanAliquoter(self, *args):
		check_input = self.ids.textbox.text
		if self.plateLighting.ttw.isName(check_input):
			self.aliquoter = check_input
			self.ids.aliquoter_label.text += check_input 
			self.ids.textbox.text = ''

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind('on_text_validate',self.scanAliquoter)
			self.ids.textbox.bind(on_text_validate=self.scanPlate)
			self.ids.notificationLabel.text = 'Please scan plate'
		else: 
			self.showBarcodeError('name')

		# bind textbox to scanPlate
	def scanPlate(self, *args):
		check_input = self.ids.textbox.text
		if self.plateLighting.ttw.isPlate(check_input):
			self.plate_barcode = check_input
			self.ids.plate_barcode_label.text += check_input 
			self.ids.textbox.text = ''

			# openCSV 
			self.plateLighting.ttw.openCSV(recorder=self.recorder, aliquoter=self.aliquoter, plate_barcode=self.plate_barcode)

			# set up text file confirmation
			self.txt_file_path = os.path.join(self.plateLighting.ttw.csv_file_path +'_FINISHED.txt')
			self.confirm_popup = ConfirmPopup(self.txt_file_path)

			# bind textbox to switchwell after barcode is scanned
			self.ids.textbox.funbind('on_text_validate',self.scanPlate)
			self.ids.textbox.bind(on_text_validate=self.switchWell)

			self.ids.notificationLabel.text = 'Please scan tube'
			self.scanMode = True

		else: 
			self.showBarcodeError('plate')

	def switchWell(self, *args):
		self.ttw.switchWell()

		check_input = self.ids.textbox.text 

		# switch well if it is a new tube
		if self.plateLighting.ttw.isTube(check_input):
			self.ids.tube_barcode_label.text = check_input
			self.canUndo = self.plateLighting.switchWell(check_input) # can only undo if it's a new target
			self.ids.notificationLabel.font_size = 100
			self.ids.notificationLabel.text = self.plateLighting.well_dict[check_input].location
			print(self.plateLighting.well_dict[check_input].location)
			self.ids.textbox.text = '' #clear textbox after scan
		else: 
			self.showBarcodeError('tube')
		
if __name__ == '__main__':
	Window.size =(1600, 1200)
	Window.fullscreen = True
	TubeToWellApp().run()

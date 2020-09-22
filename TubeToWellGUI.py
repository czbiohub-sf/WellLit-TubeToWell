#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import kivy, os
kivy.require('1.11.1')
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.properties import StringProperty
from kivy.properties import ObjectProperty, StringProperty
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


class LoadDialog(FloatLayout):
	load = ObjectProperty(None)
	cancel = ObjectProperty(None)
	load_path = StringProperty('')

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
		self.scanMode = False
		self.ids.textbox.bind(on_text_validate=self.scanRecorder)
		self.error_popup = WellLitPopup()
		self.confirm_popup = ConfirmPopup()
		self.load_path = self.ttw.samples_dir
		self.status = ''
		self.ids.dest_plate.initialize()
		self.filename = None

	def _on_keyboard_up(self, keyboard, keycode, text, modifiers):
		if keycode[1] == 'esc':
			self.showPopup('Are you sure you want to exit?', 'Confirm exit', func=self.quit)

	def quit_button(self):
		self.showPopup('Are you sure you want to exit?', 'Confirm exit', func=self.quit)

	def show_load(self):
		content = LoadDialog(load=self.load, cancel=self.dismiss_popup, load_path=self.load_path)
		self._popup = Popup(title='Load File', content=content)
		self._popup.size_hint = (0.4, .8)
		self._popup.pos_hint = {'x': 10.0 / Window.width, 'y': 100 / Window.height}
		self._popup.open()

	def load(self, filename):
		self.dismiss_popup()
		self.filename = filename
		self.showPopup(TConfirm(
			'Loading a list of samples will limit any scanned or keyed in sample IDs to only those on the loaded sample sheet. '
			'Are you sure?'),
			'Confirm sample name load',
			func=self.loadSamples)

	def loadSamples(self, button):
		if self.filename:
			filename = self.filename[0]
		else:
			self.showPopup(TError('Invalid target to load'), 'Unable to load file')

		if os.path.isfile(str(filename)):
			try:
				self.ttw.loadCSV(filename)
			except TError as err:
				self.showPopup(err, 'Load Failed')
			except TConfirm as conf:
				self.showPopup(conf, 'Load Successful')

	def updateLights(self):
		"""
		For tube to well applications, scanning a barcode will light up the well it should be pipetted into.
		Internally that transfer is already marked as complete, and can be undone by the user.
		Therefore the well being lit up is actually the previous transfer, i.e the one just completed.
		"""
		if self.ids.dest_plate.pl is not None:
			if self.ttw.tp_present():
				# reset all wells for each refresh
				self.ids.dest_plate.pl.emptyWells()
				if self.ttw.tp._current_idx > 0:
					# mark completed wells as filled
					for tf_id in self.ttw.tp.lists['completed']:
						self.ids.dest_plate.pl.markFilled(self.ttw.tp.transfers[tf_id]['dest_well'])

					# overwrite the previously completed transfer and mark it as the current target
					previous_transfer = self.ttw.tp.transfers[self.ttw.tp.tf_seq[self.ttw.tp._current_idx - 1]]
					# mark current well as target
					self.ids.dest_plate.pl.markTarget(previous_transfer['dest_well'])
				for control_well in self.ttw.controls:
					self.ids.dest_plate.pl.markControl(control_well)
			self.ids.dest_plate.pl.show()

	def showPopup(self, error, title: str, func=None):
		self._popup = WellLitPopup()
		self._popup.size_hint = (0.6, .3)
		self._popup.pos_hint = {'left': 1, 'top':  1}
		self._popup.title = title
		self._popup.show(error.__str__(), func=func)

	def next(self, blank):
		barcode = self.ids.textbox.text
		self.ids.tube_barcode = barcode
		self.ids.textbox.text = ''
		try:
			self.ttw.next(barcode)
			self.updateLights()
		except TError as err:
			self.showPopup(err, "Unable to complete")
			self.status = self.ttw.msg
		except TConfirm as conf:
			self.showPopup(conf, "Plate complete")
			self.status = self.ttw.msg

	def undoTube(self):
		try:
			self.ttw.undo()
			self.updateLights()
			self.showPopup('Previous tube un-scanned', "Action undone")
			self.status = self.ttw.msg
		except TError as err:
			self.showPopup(err, "Unable to undo")
			self.status = self.ttw.msg

	def finishPlate(self):
		# def showPopup(self, error, title: str, func=None):
		self.showPopup('Are you sure you want to finish the plate?', 'Confirm plate finish', self.resetAll)

	def resetAll(self, button):
		# restart metadata collection
		self.ids.textbox.funbind('on_text_validate', self.next)
		self.ids.textbox.funbind('on_text_validate', self.scanAliquoter)
		self.ids.textbox.funbind('on_text_validate', self.scanPlate)
		self.ids.textbox.bind(on_text_validate=self.scanRecorder)
		self.ids.status.text = "Please scan the recorder's barcode"

		# reset metadata text
		self.ids.recorder_label.text = '[b]Recorder:[/b] \n'
		self.ids.aliquoter_label.text = '[b]Aliquoter:[/b] \n'
		self.ids.plate_barcode_label.text = '[b]Plate Barcode:[/b] \n'
		self.ids.tube_barcode_label.text = '[b]Tube Barcode:[/b] \n'
		self.ids.status.font_size = 50

		self.scanMode = False

		if self.ids.dest_plate.pl is not None:
			self.ids.dest_plate.pl.emptyWells()

	def showBarcodeError(self, barcode_type):
		self.error_popup.title =  "Barcode Error"
		self.error_popup.show('Not a valid ' + barcode_type +' barcode')
		self.ids.textbox.text = ''

	def scanRecorder(self, *args):
		"""
		First step when starting a new plate. Checks to see if its a valid name with no numbers
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isName(check_input):
			self.recorder = check_input
			self.ids.recorder_label.text += check_input 
			self.ids.textbox.text = ''

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind('on_text_validate',self.scanRecorder)
			self.ids.textbox.bind(on_text_validate=self.scanAliquoter)
			self.ids.status.text = "Please scan the aliquoter's barcode"
		else: 
			self.showBarcodeError('name')

	def scanAliquoter(self, *args):
		"""
		Second step when starting a new plate. Checks to see if its a valid name with no numbers
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isName(check_input):
			self.aliquoter = check_input
			self.ids.aliquoter_label.text += check_input 
			self.ids.textbox.text = ''

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind('on_text_validate',self.scanAliquoter)
			self.ids.textbox.bind(on_text_validate=self.scanPlate)
			self.ids.status.text = 'Please scan plate'
		else: 
			self.showBarcodeError('name')


	def scanPlate(self, *args):
		"""
		Third step when starting a new plate.
		Passes metadata to TubeToWell class to generate record files and transfer sequence
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isPlate(check_input):
			self.plate_barcode = check_input
			self.ids.plate_barcode_label.text += check_input 
			self.ids.textbox.text = ''

			self.ttw.setMetaData(recorder=self.recorder, aliquoter=self.aliquoter, plate_barcode=self.plate_barcode)

			# set up text file confirmation
			self.txt_file_path = os.path.join(self.ttw.csv +'_FINISHED.txt')
			self.confirm_popup = ConfirmPopup(self.txt_file_path)

			# bind textbox to ttw.next() after barcode is scanned
			self.ids.textbox.funbind('on_text_validate', self.scanPlate)
			self.ids.textbox.bind(on_text_validate=self.next)

			self.ids.status.text = 'Please scan tube'
			self.scanMode = True

		else: 
			self.showBarcodeError('plate')


		
if __name__ == '__main__':
	Window.size =(1600, 1200)
	Window.fullscreen = False
	TubeToWellApp().run()

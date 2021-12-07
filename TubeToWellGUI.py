#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import kivy, os
kivy.require('1.11.1')
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
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

class ChooseSaveDirDialog(FloatLayout):
	choose = ObjectProperty(None)
	cancel = ObjectProperty(None)
	save_dir = StringProperty('')

class ChooseTemplateDialog(FloatLayout):
	choose = ObjectProperty(None)
	cancel = ObjectProperty(None)
	template_path = StringProperty('')

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
		self.ids.textbox.bind(on_text_validate=self.scanUser)
		self.error_popup = WellLitPopup()
		self.confirm_popup = ConfirmPopup()
		self.load_path = self.ttw.samples_dir
		self.templates_path = self.ttw.templates_dir
		self.status = ''
		self.ids.dest_plate.initialize()
		self.filename = None
		self.save_directory = None
		self.template_file = None
		self.user = ''

	def _on_keyboard_up(self, keyboard, keycode, text, modifiers):
		if keycode[1] == 'esc':
			self.showPopup('Are you sure you want to exit?', 'Confirm exit', func=self.quit)

	def quit_button(self):
		self.ttw.writeTransferRecordFiles()
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

	def showChooseTemplateFile(self):
		content = ChooseTemplateDialog(choose=self._chooseTemplateFile, cancel=self.dismiss_popup, template_path=self.templates_path)
		self._popup = Popup(title="Choose template file", content=content)
		self._popup.size_hint = (0.4, 0.8)
		self._popup.pos_hint = {'x': 10.0 / Window.width, 'y': 100 / Window.height}
		self._popup.open()

	def _chooseTemplateFile(self, filename):
		self.dismiss_popup()
		self.template_file = filename
		self.showPopup(TConfirm(
			'Loading a template file sets the availability of wells. Any well-to-barcode mappings present in the csv file will be enforced.'
			'Are you sure?'),
			'Confirm template file load',
			func=self._loadTemplateFile)
	
	def _loadTemplateFile(self, _):
		if self.template_file:
			filename = self.template_file[0]
		else:
			self.showPopup(TError('Invalid target to load'), 'Unable to load file')

		if os.path.isfile(str(filename)):
			try:
				self.ttw.loadWellConfigurationCSV(filename)
			except TError as err:
				self.showPopup(err, 'Load Failed')
			except TConfirm as conf:
				self.showPopup(conf, 'Load Successful')

	def showChooseSaveDirectory(self):
		content = ChooseSaveDirDialog(choose=self.chooseDirectory, cancel=self.dismiss_popup, save_dir=self.load_path)
		self._popup = Popup(title='Choose folder', content=content)
		self._popup.size_hint = (0.4, 0.8)
		self._popup.pos_hint = {'x': 10.0 / Window.width, 'y': 100 / Window.height}
		self._popup.open()

	def chooseDirectory(self, directory):
		self.dismiss_popup()
		self.save_directory = directory + "/"
		self.showPopup(TConfirm(
			f'The outputted csv file will be saved to: {directory}. '
			'Are you sure?'),
			'Confirm save directory location',
			func=self._chooseDirectory)

	def _chooseDirectory(self, _):
		if self.save_directory:
			directory = self.save_directory

			if os.path.isdir(directory):
				try:
					self.ttw.setSaveDirectory(directory)
				except TError as err:
					self.showPopup(err, "Failed to set directory")
				except TConfirm as conf:
					self.showPopup(conf, "Directory set")
		else:
			self.showPopup(TError("Invalid save directory location."), "Unable to set save directory")

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

				# mark completed wells as filled
				for tf_id in self.ttw.tp.lists['completed']:
					self.ids.dest_plate.pl.markFilled(self.ttw.tp.transfers[tf_id]['dest_well'])

				# mark current in-progress transfer as the target
				for tf_id in self.ttw.tp.lists['started']:
					self.ids.dest_plate.pl.markTarget(self.ttw.tp.transfers[tf_id]['dest_well'])

				# mark failed wells as discarded
				for tf_id in self.ttw.tp.lists["failed"]:
					self.ids.dest_plate.pl.markDiscarded(self.ttw.tp.transfers[tf_id]['dest_well'])

				# mark the control wells
				for control_well in self.ttw.controls:
					self.ids.dest_plate.pl.markControl(control_well)

				if self.ttw.tp.lightup_well is not None:
					self.ids.dest_plate.pl.markRescan(self.ttw.tp.lightup_well)

			# update and show plot
			self.ids.dest_plate.pl.show()

	def showPopup(self, error, title: str, func=None):
		self._popup = WellLitPopup()
		self._popup.size_hint = (0.6, .3)
		self._popup.pos_hint = {'left': 1, 'top':  1}
		self._popup.title = title
		self._popup.show(error.__str__(), func=func)

	def showPopupWithScroll(self, msg, title: str, func=None):
		scroll = ScrollView()
		grid = GridLayout(cols=1, size_hint=(1, None))
		scroll.add_widget(grid)
		grid.bind(minimum_height=grid.setter('height'))
		label = Label(text=msg, font_size=24, size_hint=(None, None))
		label.bind(texture_size=label.setter('size'))
		grid.add_widget(label)
		self._popup = Popup(title=title, content=scroll)
		self._popup.size_hint = (0.5, 0.3)
		self._popup.pos_hint = {"x": 0.25, "y": 850 / Window.height}
		self._popup.open()

	def next(self, blank):
		barcode = self.ids.textbox.text
		self.ids.tube_barcode.text = barcode
		self.ids.textbox.text = ''

		# Ensure a blank barcode can't be used
		if barcode == "":
			return

		try:
			self.ttw.next(barcode)
			self.updateLights()
		except TError as err:
			self.showPopup(err, "Unable to complete")
			self.status = self.ttw.msg
			self.updateLights()
		except TConfirm as conf:
			self.ttw.writeTransferRecordFiles()
			self.showPopup(conf, "Plate complete")
			self.status = self.ttw.msg
			self.updateLights()
	
	def undoCurrentScan(self):
		"""Cancel the current scan.
		
		If the user accidentally scans an incorrect tube, this allows them to 
		cancel the current scan, and scan a new (correct) tube to aliquot into the well.
		"""
		try:
			self.ttw.undoCurrentScan()
			self.updateLights()
			self.showPopup("Current scan cancelled. A new tube can be scanned for aliquoting into this well.", "Current scan cancelled")
			self.status = self.ttw.msg
			self.ids.tube_barcode.text = ''
		except TError as err:
			self.ttw.writeTransferRecordFiles()
			self.updateLights()
			self.showPopup(err, "Unable to cancel current scan")
			self.status = self.ttw.msg

	def undoTube(self):
		try:
			self.ttw.undo()
			self.updateLights()
			self.showPopup("Previous tube un-scanned", "Action undone")
			self.status = self.ttw.msg
		except TError as err:
			self.ttw.writeTransferRecordFiles()
			self.updateLights()
			self.showPopup(err, "Unable to undo")
			self.status = self.ttw.msg

	def discardLastWell(self):
		if self.ttw.tp._current_idx > 1:
			prev_id = self.ttw.tp.tf_seq[self.ttw.tp._current_idx - 2]
			prev_transfer = self.ttw.tp.transfers[prev_id]
			dest_well = prev_transfer['dest_well']
			self.ids.textbox.text = dest_well
			self.discardWellConfirmation()
		else:
			self.showPopup("No previous well to discard", "Invalid well")

	def discardWellConfirmation(self):
		text = self.ids.textbox.text
		is_well = text in self.ttw.tp.valid_wells
		if is_well:
			if self.ttw.tp.isWellUsed(text):
				self.showPopup(f'Are you sure you want to discard well {text}?', 'Confirm', func=self.discardSpecificWell)
			else:
				self.showPopup("This well hasn't been used yet! Nothing to discard.", "Invaid well")
		else:
			self.showPopup("Invalid well name entered.", "Invalid well")

	def discardSpecificWell(self, _):
		text = self.ids.textbox.text
		self.ttw.tp.discardSpecificWell(text)
		self.ttw.writeTransferRecordFiles()
		self.ids.textbox.text = ''
		self.updateLights()
		self.showPopup(f"Discarded well: {text}. The tube associated with {text} (w/ barcode: {self.ttw.tp.discarded_well_barcode}) can be aliquoted into another well.", f"Discarded well {text}")

	def showAllTransfers(self):
		"""Display the currently completed transfers to the user."""

		output = "{:<30}{:^10}{:>15}".format("Barcode", "Tube", "Status")
		output += "\n"
		for transfer_id in self.ttw.tp.tf_seq:
			transfer = self.ttw.tp.transfers[transfer_id]
			if transfer['status'] is not 'uncompleted':
				barcode = transfer["source_tube"]
				dest_well = transfer["dest_well"]
				status = transfer["status"]
				line = "{:<30}{:^10}{:>15}".format(barcode, dest_well, status)
				output += line 
				output += "\n"
		self.showPopupWithScroll(output, "Current Transfers")
		
	def finishPlate(self):
		self.showPopup('Are you sure you want to finish the plate?', 'Confirm plate finish', self.resetAll)

	def resetAll(self, button):
		# Flush the data
		self.ttw.writeTransferRecordFiles()

		# restart metadata collection
		self.ids.textbox.funbind('on_text_validate', self.next)
		self.ids.textbox.funbind('on_text_validate', self.scanPlate)
		self.ids.status.text = "Please type in your name"

		# reset metadata text
		self.ids.plate_barcode_label.text = 'Plate Barcode: \n'
		self.ids.tube_barcode_label.text = 'Tube Barcode: \n'
		self.ids.status.font_size = 50

		self.scanMode = False

		if self.ids.dest_plate.pl is not None:
			self.ids.dest_plate.pl.emptyWells()

		self.ttw.reset()
		self.updateLights()

	def showBarcodeError(self, barcode_type):
		self.error_popup.title =  "Barcode Error"
		self.error_popup.show('Not a valid ' + barcode_type +' barcode')
		self.ids.textbox.text = ''

	def scanUser(self, *args):
		"""
		First step when starting a new plate. Checks to see if its a valid name with no numbers
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isName(check_input):
			self.user = check_input
			self.ids.user.text = check_input
			self.ids.textbox.text = ''

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind('on_text_validate', self.scanUser)
			self.ids.textbox.bind(on_text_validate=self.scanPlate)
			self.ids.status.text = "Please type in your name"
		else:
			self.showBarcodeError('name')

	def scanPlate(self, *args):
		"""
		First step when starting a new plate.
		Passes metadata to TubeToWell class to generate record files and transfer sequence
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isPlate(check_input):
			self.plate_barcode = check_input
			self.ids.plate_barcode.text = check_input
			self.ids.textbox.text = ''

			self.ttw.setMetaData(plate_barcode=self.plate_barcode, user=self.user)

			# set up text file confirmation
			self.txt_file_path = os.path.join(self.ttw.csv +'_FINISHED.txt')
			self.confirm_popup = ConfirmPopup(self.txt_file_path)

			# bind textbox to ttw.next() after barcode is scanned
			self.ids.textbox.funbind('on_text_validate', self.scanPlate)
			self.ids.textbox.bind(on_text_validate=self.next)

			self.ids.status.text = 'Please scan tube'
			self.scanMode = True
			self.updateLights()

		else: 
			self.showBarcodeError('plate')


		
if __name__ == '__main__':
	Window.size =(1600, 1200)
	Window.fullscreen = True
	TubeToWellApp().run()

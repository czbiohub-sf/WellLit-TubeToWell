#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import kivy, os

kivy.require("1.11.1")
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
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
		self.t = TubeToWellWidget()
		return self.t

	def on_start(self):
		self.t.showChooseConfigFile()

class LoadDialog(FloatLayout):
	load = ObjectProperty(None)
	cancel = ObjectProperty(None)
	load_path = StringProperty("")


class ChooseSaveDirDialog(FloatLayout):
	choose = ObjectProperty(None)
	cancel = ObjectProperty(None)
	save_dir = StringProperty("")

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
		self.configs_path = self.ttw.config_dir
		self.status = ""
		self.filename = None
		self.save_directory = None
		self.template_file = None
		self.user = ""
		self.initialized = False

	def _on_keyboard_up(self, keyboard, keycode, text, modifiers):
		if keycode[1] == "esc":
			self.showPopup(
				"Are you sure you want to exit?", "Confirm exit", func=self.quit
			)

	def quit_button(self):
		self.ttw.writeTransferRecordFiles()
		self.showPopup("Are you sure you want to exit?", "Confirm exit", func=self.quit)

	def chooseFileDialog(self, load_file_func, cancel_func, dir_path, popup_title):
		content = LoadDialog(
			load=load_file_func, cancel=cancel_func, load_path=dir_path
		)
		self._popup = Popup(title=popup_title, content=content, auto_dismiss=False)
		self._popup.size_hint = (0.4, 0.8)
		self._popup.pos_hint = {"x": 10.0 / Window.width, "y": 100 / Window.height}
		self._popup.open()

	def show_load(self):
		self.chooseFileDialog(self.load, self.dismiss_popup, self.load_path, popup_title="Load File")

	def load(self, filename):
		self.dismiss_popup()
		self.filename = filename
		self.showPopup(
			TConfirm(
				"Loading a list of samples will limit any scanned or keyed in sample IDs to only those on the loaded sample sheet. "
				"Are you sure?"
			),
			"Confirm sample name load",
			func=self.loadSamples,
		)

	def loadSamples(self, _):
		if self.filename:
			filename = self.filename[0]
		else:
			self.showPopup(TError("Invalid target to load"), "Unable to load file")

		if os.path.isfile(str(filename)):
			try:
				self.ttw.loadCSV(filename)
			except TError as err:
				self.showPopup(err, "Load Failed")
			except TConfirm as conf:
				self.showPopup(conf, "Load Successful")

	def showChooseTemplateFile(self):
		self.chooseFileDialog(self._chooseTemplateFile, self.dismiss_popup, self.templates_path, popup_title="Choose template file")

	def _chooseTemplateFile(self, filename):
		self.dismiss_popup()
		self.template_file = filename
		self.showPopup(
			TConfirm(
				"Loading a template file sets the availability of wells. Any well-to-barcode mappings present in the csv file will be enforced."
				"Are you sure?"
			),
			"Confirm template file load",
			func=self._loadTemplateFile,
		)

	def _loadTemplateFile(self, _):
		if self.template_file:
			filename = self.template_file[0]
		else:
			self.showPopup(TError("Invalid target to load"), "Unable to load file")

		if os.path.isfile(str(filename)):
			try:
				self.ttw.loadWellConfigurationCSV(filename)
			except TError as err:
				self.showPopup(err, "Load Failed")
			except TConfirm as conf:
				self.showPopup(conf, "Load Successful")

	def showChooseConfigFile(self):
		self.chooseFileDialog(self._chooseConfigFile, self.loadDefaultConfig, self.configs_path, popup_title="Choose configuration file")

	def _chooseConfigFile(self, filename):
		self.dismiss_popup()
		self.config_file = filename
		self.showPopup(
			TConfirm(
				"Load a configuration file which sets the plate type (96 or 384) and other parameters."
				" Are you sure?"
			),
			"Confirm configuration file load",
			func=self._loadConfigurationFile,
		)

	def _loadConfigurationFile(self, _):
		if self.config_file:
			filename = self.config_file[0]
		else:
			self.showPopup(TError("Invalid target to load"), "Unable to load file")

		if os.path.isfile(str(filename)):
			try:
				if not self.initialized:
					self.ttw.setConfigurationFile(filename)
					self.ids.dest_plate.initialize(filename)
					self.initialized = True
			except TError as err:
				self.showPopup(err, "Load Failed")
			except TConfirm as conf:
				self.showPopup(conf, "Load Successful")

	def loadDefaultConfig(self):
		cwd = os.getcwd()
		config_path = os.path.join(cwd, "configs", "DEFAULT_CONFIG.json")
		self.ttw.setConfigurationFile(config_path)
		self.ids.dest_plate.initialize(config_path)
		self.dismiss_popup()

	def showChooseSaveDirectory(self):
		content = ChooseSaveDirDialog(
			choose=self.chooseDirectory,
			cancel=self.dismiss_popup,
			save_dir="/configs/",
		)
		self._popup = Popup(title="Choose folder", content=content)
		self._popup.size_hint = (0.4, 0.8)
		self._popup.pos_hint = {"x": 10.0 / Window.width, "y": 100 / Window.height}
		self._popup.open()

	def chooseDirectory(self, directory):
		self.dismiss_popup()
		self.save_directory = directory + "/"
		self.showPopup(
			TConfirm(
				f"The outputted csv file will be saved to: {directory}. "
				" Are you sure?"
			),
			"Confirm save directory location",
			func=self._chooseDirectory,
		)

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
			self.showPopup(
				TError("Invalid save directory location."),
				"Unable to set save directory",
			)

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
				for tf_id in self.ttw.tp.lists["completed"]:
					self.ids.dest_plate.pl.markFilled(
						self.ttw.tp.transfers[tf_id]["dest_well"]
					)

				# mark current in-progress transfer as the target
				for tf_id in self.ttw.tp.lists["started"]:
					self.ids.dest_plate.pl.markTarget(
						self.ttw.tp.transfers[tf_id]["dest_well"]
					)
				# mark discarded wells as discarded
				for tf_id in self.ttw.tp.lists["discarded"]:
					self.ids.dest_plate.pl.markDiscarded(
						self.ttw.tp.transfers[tf_id]["dest_well"]
					)

				# mark the control wells
				for control_well in self.ttw.controls:
					self.ids.dest_plate.pl.markControl(control_well)

				if self.ttw.tp.lightup_well is not None:
					self.ids.dest_plate.pl.markRescan(self.ttw.tp.lightup_well)

			# update and show plot
			self.ids.dest_plate.pl.show()

	def showPopup(self, error, title: str, func=None):
		self._popup = WellLitPopup()
		self._popup.size_hint = (0.6, 0.3)
		self._popup.pos_hint = {"left": 1, "top": 1}
		self._popup.title = title
		self._popup.show(error.__str__(), func=func)

	def showPopupWithScroll(self, msg, title: str, func=None):
		scroll = ScrollView()
		grid = GridLayout(cols=1, size_hint=(1, None))
		scroll.add_widget(grid)
		grid.bind(minimum_height=grid.setter("height"))
		label = Label(text=msg, font_size=24, size_hint=(None, None))
		label.bind(texture_size=label.setter("size"))
		grid.add_widget(label)
		self._popup = Popup(title=title, content=scroll)
		self._popup.size_hint = (0.5, 0.3)
		self._popup.pos_hint = {"x": 0.25, "y": 0.7}
		self._popup.open()

	def next(self, blank):
		barcode = self.ids.textbox.text
		self.ids.tube_barcode.text = barcode
		self.ids.textbox.text = ""

		# Ensure a blank barcode can't be used
		if barcode == "":
			return

		try:
			self.ttw.next(barcode)
			self.updateLights()
			well = 'COMPLETED'
			for tf_id in self.ttw.tp.lists["started"]:
				well = self.ttw.tp.transfers[tf_id]["dest_well"]
			self.ids.status.text = f"Current scan:\n{barcode} -> {well}"
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
			self.showPopup(
				"Current scan cancelled. A new tube can be scanned for aliquoting into this well.",
				"Current scan cancelled",
			)
			self.status = self.ttw.msg
			self.ids.tube_barcode.text = ""
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
			dest_well = prev_transfer["dest_well"]
			self.ids.textbox.text = dest_well
			self.discardWellConfirmation()
		else:
			self.showPopup("No previous well to discard", "Invalid well")

	def discardWellConfirmation(self):
		text = self.ids.textbox.text.upper()
		is_well = text in self.ttw.tp.valid_wells
		if is_well:
			if self.ttw.tp.isWellUsed(text):
				self.showPopup(
					f"Are you sure you want to discard well {text}?",
					"Confirm",
					func=self.discardSpecificWell,
				)
			else:
				self.showPopup(
					"This well hasn't been used yet! Nothing to discard.", "Invaid well"
				)
		elif text in self.ttw.barcode_to_well.values():
			barcode = list(self.ttw.barcode_to_well.keys())[
				list(self.ttw.barcode_to_well.values()).index(text)
			]
			self.showPopup(
				f"Well {text} was specifically reserved for barcode {barcode} in the loaded template file. Are you sure you want to discard this well?",
				"Reserved well",
				func=self.discardSpecificWell,
			)
		else:
			self.showPopup("Invalid well name entered.", "Invalid well")

	def discardSpecificWell(self, _):
		text = self.ids.textbox.text.upper()
		self.ttw.tp.discardSpecificWell(text)
		self.ttw.writeTransferRecordFiles()
		self.ids.textbox.text = ""
		self.updateLights()
		self.showPopup(
			f"Discarded well: {text}. The tube associated with {text} (w/ barcode: {self.ttw.tp.discarded_well_barcode}) can be aliquoted into another well.",
			f"Discarded well {text}",
		)

	def showAllTransfers(self):
		"""Display the currently completed transfers to the user."""

		output = "{:<30}{:^15}{:>15}".format("Barcode", "Well", "Status")
		output += "\n"
		for transfer_id in self.ttw.tp.tf_seq:
			transfer = self.ttw.tp.transfers[transfer_id]
			if transfer["status"] is not "uncompleted":
				barcode = transfer["source_tube"]
				dest_well = transfer["dest_well"]
				status = transfer["status"]
				line = "{:<30}{:^25}{:>15}".format(barcode, dest_well, status)
				output += line
				output += "\n"
		self.showPopupWithScroll(output, "Current Transfers")

	def skipWellConfirmation(self):
		"""Allow the user to skip the next well (it will be marked as empty in the records file)."""

		prev_id = self.ttw.tp.tf_seq[self.ttw.tp._current_idx ]
		prev_transfer = self.ttw.tp.transfers[prev_id]
		dest_well = prev_transfer["dest_well"]
		self.showPopup(
			f"Are you sure you want to skip the next well {dest_well}? It will be marked as 'Empty' in the records file.",
			"Confirm",
			func=self.skipWell,
		)

	def skipWell(self, _):
		self.ttw.tp.skipNextWell()
		self.ttw.writeTransferRecordFiles()
		self.ids.textbox.text = ""
		self.updateLights()

	def finishPlate(self):
		self.showPopup(
			"Are you sure you want to finish the plate?",
			"Confirm plate finish",
			self.resetAll,
		)

	def resetAll(self, button):
		# Flush the data
		self.ttw.writeTransferRecordFiles()

		# restart metadata collection
		self.ids.textbox.funbind("on_text_validate", self.next)
		self.ids.textbox.bind(on_text_validate=self.scanPlate)
		self.ids.status.text = "Please scan or key in plate barcode"

		# reset metadata text
		self.ids.plate_barcode_label.text = "Plate Barcode: \n"
		self.ids.tube_barcode_label.text = "Tube Barcode: \n"
		self.ids.status.font_size = 50

		self.scanMode = False

		if self.ids.dest_plate.pl is not None:
			self.ids.dest_plate.pl.emptyWells()

		self.ttw.reset()
		self.updateLights()

	def showBarcodeError(self, barcode_type):
		self.error_popup.title = "Barcode Error"
		self.error_popup.show("Not a valid " + barcode_type + " barcode")
		self.ids.textbox.text = ""

	def scanUser(self, *args):
		"""
		First step when starting a new plate. Checks to see if its a valid name with no numbers
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isName(check_input):
			self.user = check_input
			self.ids.user.text = check_input
			self.ids.textbox.text = ""

			# bind textbox to scanPlate after name is scanned
			self.ids.textbox.funbind("on_text_validate", self.scanUser)
			self.ids.textbox.bind(on_text_validate=self.scanPlate)
			self.ids.status.text = "Please scan or key in plate barcode"
		else:
			self.showBarcodeError("name")

	def scanPlate(self, *args):
		"""
		First step when starting a new plate.
		Passes metadata to TubeToWell class to generate record files and transfer sequence
		"""
		check_input = self.ids.textbox.text
		if self.ttw.isPlate(check_input):
			self.plate_barcode = check_input
			self.ids.plate_barcode.text = check_input
			self.ids.textbox.text = ""

			self.ttw.setMetaData(plate_barcode=self.plate_barcode, user=self.user)

			# set up text file confirmation
			self.txt_file_path = os.path.join(self.ttw.csv + "_FINISHED.txt")
			self.confirm_popup = ConfirmPopup(self.txt_file_path)

			# bind textbox to ttw.next() after barcode is scanned
			self.ids.textbox.funbind("on_text_validate", self.scanPlate)
			self.ids.textbox.bind(on_text_validate=self.next)

			self.ids.status.text = "Please scan tube"
			self.scanMode = True
			self.updateLights()

		else:
			self.showBarcodeError("plate")


if __name__ == "__main__":
	Window.size = (1600, 1200)
	Window.fullscreen = True
	TubeToWellApp().run()

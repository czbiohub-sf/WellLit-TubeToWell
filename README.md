# TubeToWell

This repository contains the code needed to run the CZ Biohub's Well-Lit device in the "Tube to Well-Lit" configuration, as described in the manuscript at:
https://www.biorxiv.org/content/10.1101/2021.12.17.473010v2

The files needed to build the Well-Lit device can be downloaded from https://osf.io/f9nh5/.


## Installation Instructions for Windows

1. Install Anaconda or Miniconda Python 3.7 (from www.anaconda.com - tested on Anaconda version 4.8.3) selecting the option 'ADD TO PATH' in the installer.
2. Make anaconda environment:<br/>
        Open up anaconda prompt and type: `conda create -n WellLit python=3.7.6`
3. Activate the environment with `conda activate WellLit`
4. Install dependencies:<br/>
        `conda install matplotlib==3.1.3`<br/>
        `conda install pandas`<br/>
        `conda install -c conda-forge kivy`<br/>
        `pip install kivy-garden`<br/>
        `garden install graph`<br/>
        `garden install matplotlib`<br/>
5. Clone this repo https://github.com/czbiohub/WellLit-TubeToWell or download as a zip file and then unzip.
6. Open a git bash terminal in the repository folder you just downloaded and enter the commands 'git submodule update --init' and then run `git submodule update --remote` to finish obtaining the required files. If you are not using git and downloaded a zipped folder, then download and extract the repository at 'https://github.com/czbiohub/WellLit.git' into the '../WellLit' folder in the first repository you downloaded.
7. Create a shortcut to the 'startup.bat' file located in folder and place it on the desktop.
8. Configure the barcode scanner:<br/>
         If using the same barcode scanner as listed in the bill of materials, users should configure it. Download and print the “Well-Lit Barcode Scanner Configuration Sheet.pdf” file. Connect the scanner to the PC and scan the barcodes on the sheet in a zig-zag pattern, from top to bottom, following the order of the numbers in red. Each barcode in this sheet configures a different aspect of the scanner.


### Software Configuration

To configure the software open 'wellLitConfig.json' in a text editor and modify the following entries to suit the users application. If invalid directory locations are given in this configuration file, the software will default to using subfolders named 'samples', 'records', and 'protocols' in the parent repository folder.

1. 'num_wells' configures the software for either 96 or 384 well format. If an invalid number is entered the software defaults to 96-well format.
2. 'records_dir' configures the directory for storing records. The software automatically records every transfer in a CSV file with timestamps as soon as the action is completed.
3. 'A1_X_dest' and 'A1_Y_dest' control the position of well A1 on the screen. The numeric values are given as fractions of the screen area, and so will likely need to be adjusted if using a screen different than the one specified in this build guide. These values increment from the upper left corner of the Graphical User Interface (GUI). If the lighting is misaligned with the wells on your screen, adjust these parameters to achieve good alignment.
4. 'size_param' controls the size of the illuminated circle or square which appears beneath a well.
5. 'well_spacing' controls the distance between adjacent wells.
6. 'samples_dir' sets the directory to load CSV files from if the user wishes to restrict plated samples to a pre-defined list.
7. If using a barcode scanner, it must be configured to automatically add a return command after each barcode is decoded. If using the same barcode scanner as listed in the bill of materials, users should configure this setting by scanning the appropriate symbol on the 'Well Lit Scanner Configuration Sheet.pdf'.
8. 'controls' specified wells that will be excluded from the sample transfer. If no controls are used this field should be left as empty quotation marks. Note that as of the February 2022 update, a user can now supply a template csv file to select which wells to set as control. An example templating csv file is located in the `templates/` folder in this repository.


## Use instructions

The top area of the screen contains the main user interface, while the bottom displays the colored dots illuminating the wells. The Graphical User Interface (GUI) will always display the user's next step for using the device. The GUI will also display error messages if the user attempts to perform invalid commands.

1. Connect the barcode scanner to the mini PC. The scanner must be configured as described above.
2. Ensure that the 'WellLit-TubeToWell' repository is active, and that the software configurations have been set.
3. Launch the Well-lit software by double clicking on the 'startup.bat' icon, or by launching 'TubeToWellGUI.py' from a python terminal.
4. The user will be prompted to enter the user name and the plate name/barcode. All prompted information can either be scanned or entered manually by clicking in the white text entry box on the top-right corner of the screen.
5. Insert the plate into the holder. Ensure that the A1 well is in the top left corner of the holder (the holder for each type of multi-well plate is designed to ensure that the plate can only be inserted in the right orientation).
6. If the user wishes to restrict tube barcodes to come from a pre-defined list, for example to guard against errors when manually typing by hand or segregating tubes by batches that may have been mixed up, press “Load Sample List” to select a CSV file of tube barcodes. Only barcodes from this list will be accepted by the machine for assigning to a well.
7. Each user action is recorded with a timestamp in a CSV file saved to the folder specified in the the 'wellLitConfig.json' configuration file ('records_dir' parameter - see Software Configuration section).
8. Wells are highlighted with the following colors:<br/>
       a. Yellow: Current transfer target well<br/>
       b. Red: Full wells<br/>
       c. "Darkslate" Gray: Empty wells<br/>
       d. Blue: Re-scanned sample well (full)<br/>
       e. White: Excluded/control wells (see software configuration section) <br/>
       f. Regular Gray: Discarded wells
9. Tube to Well-Lit sample transfer procedure:<br/>
       a. Scan or type a tube name or barcode to light up the first available well in yellow. This is the target well. Wells are assigned to the tubes in a column-wise order (i.e. A1, B1, C1, ... A2, B2, C2, ...).<br/>
       b. After transferring an aliquot from the tube to the target (yellow) well, scan or enter the next tube's barcode to mark the previous transfer as complete and light up the next available well. The filled wells will be lit in red.<br/>
       c. Re-scanning a previously scanned tube will light its assigned well in blue.<br/>
       d. The last transfer can be undone with the “Undo Last Tube” button. The undone transfer is not included in the record file generated. You cannot undo more than one transfer per scan.
       e. "Cancel Current Scan" - a button which allows a user to cancel the current scan and scan another tube. You would use this in cases where you accidentally scanned a tube when you meant to scan another one instead. The "cancelled scan" can still be scanned again later for aliquoting into another well.
       f. "Discard Last Well" / "Discard Specified Well" - discard the last well. This allows the user to RE-SCAN whatever tube was aliquoted into the previous well and aliquot it into another well. The discarded well will be clearly marked in the records file (as "TUBEBARCODE-DISCARDED"). Additionally, the user can specify a specific well in the white-textbox (e.g "A3") and press "Discard Specified Well" to discard that particular well.
       g. "Show Completed Transfers" - display a pop-up box listing all the transfers that have been done so far (including wells that have been discarded/skipped). 
       h. "Skip well" - skips the next well and marks it as empty in the records file. You may want to do this in cases where you notice debris/contamination in a particular well and want to exclude it.
10. Press “Finish Plate” when all the transfers have been completed. The program will automatically start a new record file for the next plate. For a new plate, follow the instructions starting at step 4 for the new plate.
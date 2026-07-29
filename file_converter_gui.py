from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pyqtgraph as pg
import sys
import os
import numpy as np
from QThread_classes.lst_tof_QThread import tof_QThread
from Plotters.ToF_plotter import ToFPlotter
from QThread_classes.convert_taskmanager import FileGatewayManager

pg.setConfigOption('foreground', 'k')
pg.setConfigOption('background', 'w')

class MainWindow(QtWidgets.QWidget):
    run_tof_calc = pyqtSignal(str, int, int)

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        #Load the UI Page
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'GUI_layouts\\file_converter_gui.ui'), self)

        # Set defaults
        self.cur_path = os.path.expanduser(r'~\Documents')

        # Set up threads
        self.initialise_tof_qthread()

        # Set up ToF plotter
        self.ToF_plotter = ToFPlotter(self)

        # Set up the file conversion gateway
        self.gateway_manager = FileGatewayManager()

        # Connections
        self.openFileButton.clicked.connect(lambda: self.select_file(self.inputFileName, 'open'))
        self.saveFileButton.clicked.connect(lambda: self.select_file(self.outputFileName, 'save'))
        self.tofButton.clicked.connect(self.read_tof_pressed)
        self.convertButton.clicked.connect(self.convert_file_pressed)
        self.gateway_manager.file_converted.connect(self.file_conversion_finished)
        self.gateway_manager.file_aborted.connect(self.file_conversion_aborted)
        self.gateway_manager.file_accepted.connect(self.file_conversion_started)
        self.gateway_manager.progress.connect(self.update_progress)

        # Set up tracking variables (for files that are either being processed or are in the queue)
        self.track_infiles = []
        self.track_outfiles = []
        self.in_progress = {}

        # Initialise the display
        self.update_proc_queue_display()

        self._closing = False


    def select_file(self, fileTextBox, type='open'):
        # Two 
        if type == 'open':
            fname = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open file', self.cur_path, 'lst files (*.lst);;All files (*.*)')
        else:
            fname = QtWidgets.QFileDialog.getOpenFileNames(self, 'Save file', self.cur_path, 'hdf5 files (*.h5);;All files (*.*)')
        
        # If a file is chosen, update the display and save the default path
        # Autopopulate the save file list when new files are opened
        if fname[0] != '':
            try:
                fileTextBox.setText(fname[0])
                self.cur_path = os.path.dirname(fname[0])
                if type == 'open':
                    _fname = os.path.join(os.path.dirname(fname[0]), os.path.basename(fname[0]).split('.lst')[0] + '.h5')
                    self.outputFileName.setText(_fname)

            except TypeError:
                if fname[0] != []:
                    fileTextBox.setText('; '.join(fname[0]))
                    self.cur_path = os.path.dirname(fname[0][-1])

                    if type == 'open':
                        _fname_list = [os.path.join(os.path.dirname(_), os.path.basename(_).split('.lst')[0] + '.h5') for _ in fname[0]]
                        self.outputFileName.setText('; '.join(_fname_list))


    @pyqtSlot(object)
    def process_output(self, tof):
        self.tofButton.setText('Plot ToF')
        self.tofButton.setEnabled(True)
        self.ToF_plotter.update(tof)


    @pyqtSlot(str, str)
    def file_conversion_finished(self, in_file, out_file):
        # Remove from the queue variable and in progress, update display
        idx = self.track_outfiles.index(out_file)
        self.track_infiles.pop(idx)
        self.track_outfiles.pop(idx)

        self.in_progress.pop(out_file)

        self.update_proc_queue_display()


    @pyqtSlot(str, str)
    def file_conversion_started(self, in_file, out_file):
        self.in_progress[out_file] = [in_file, 0.0]

        self.update_proc_queue_display()


    @pyqtSlot(str, str)
    def file_conversion_aborted(self, in_file, out_file):
        # Remove from in progress, update display
        self.in_progress.pop(out_file)

        self.update_proc_queue_display()


    @pyqtSlot(str, float)
    def update_progress(self, out_file, percent_read):
        self.in_progress[out_file][1] = percent_read

        self.update_proc_queue_display()


    def read_tof_pressed(self):
        self.run_tof_calc.emit(self.inputFileName.text(),self.tofCyclesCountSpin.value(), self.lineCountSpin.value())
        self.tofButton.setText('Reading')
        self.tofButton.setEnabled(False)


    def convert_file_pressed(self):
        in_file_list = self.inputFileName.text().split(';')
        out_file_list = self.outputFileName.text().split(';')

        total_files = min(len(in_file_list), len(out_file_list))

        for i in range(total_files):
            in_file = in_file_list[i].strip()
            out_file = out_file_list[i].strip()

            # If the pair is already to be processed, skip
            try:
                idx = self.track_outfiles.index(out_file)

                # Only reiterate if this pair isn't already present
                if self.track_infiles[idx] == in_file: continue

            except ValueError:
                idx = ''

            # Check whether file exists or is in the output queue
            file_exists = os.path.exists(out_file)

            if file_exists or out_file in self.track_outfiles:
                response = self.overwrite_warning(in_file, out_file, file_exists)

                # Do not process if not requested
                if response == QtWidgets.QMessageBox.StandardButton.No: continue

            # Overwrite tracking if replacing a file
            try:
                self.track_infiles[idx] = in_file
            except TypeError:
                self.track_infiles.append(in_file)
                self.track_outfiles.append(out_file)

            # Pass to the file conversion handler
            # input_file, output_file, min_time, line_read_count
            self.gateway_manager.request_received.emit(in_file, out_file, self.tofCyclesCountSpin.value(), self.lineCountSpin.value())

        self.update_proc_queue_display()


    def update_proc_queue_display(self):
        running = 'Proc.: '
        pending = 'Pend.: '

        for i in range(len(self.track_infiles)):
            # Extract current files for clarity
            in_file = self.track_infiles[i]
            out_file = self.track_outfiles[i]

            try:
                self.in_progress[out_file]
                running += f'{os.path.basename(in_file)} -> {os.path.basename(out_file)} ({self.in_progress[out_file][1]}%), '

            except KeyError:
                pending += f'{os.path.basename(in_file)} -> {os.path.basename(out_file)}, '

        # Remove delimiter from final item
        if running[-2:] == ', ':
            running = running[:-2]
        else:
            running += 'None'

        if pending[-2:] == ', ':
            pending = pending[:-2]
        else:
            pending += 'None'

        self.fileQueueDisplay.setText(running + ' || ' + pending)


    def initialise_tof_qthread(self):
        # Set up the covariance QThread
        self.tofThread = QThread()

        # Initialise the worker class
        self.worker = tof_QThread()

        # Move the worker to the thread
        self.worker.moveToThread(self.tofThread)

        # Connect signals and slots
        self.run_tof_calc.connect(self.worker.read_tof)
        self.worker.output.connect(self.process_output)

        # Start the thread
        self.tofThread.start()


    def overwrite_warning(self, in_file, out_file, file_already_exists=True):
        if file_already_exists:
            return QtWidgets.QMessageBox.question(
                    self, 
                    'Overwrite File?',
                    f'The file {os.path.basename(out_file)} already exists. Overwrite with file generated from {os.path.basename(in_file)}?',
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No
                )

        else:
            return QtWidgets.QMessageBox.question(
                    self, 
                    'Overwrite File?',
                    f'The file {os.path.basename(out_file)} is already in the queue. Replace with this selection (generated from {os.path.basename(in_file)})?',
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No
                )


    def closeEvent(self, event):
        self._closing = True
        self.fileQueueDisplay.setText('Shutting down. Please wait...')
        self.fileQueueDisplay.setReadOnly(True)

        stopped = self.gateway_manager.shutdown(timeout_ms=10000)

        if stopped:
            # Safely shuts down the the ToF QThread
            if self.tofThread.isRunning():
                # Tell the thread to stop, and wait for this to happen
                self.tofThread.terminate()
                self.tofThread.wait()

            event.accept()
        else:
            # The worker has not cooperatively stopped yet.
            # Do not destroy objects it might still access.
            event.ignore()
            self.fileQueueDisplay.setReadOnly(False)
            self.fileQueueDisplay.setText('Shutdown timed out. Please try again.')


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec()

if __name__ == '__main__':
    main()
from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pyqtgraph as pg
import sys
import os
import numpy as np
from QThread_classes.covariance_QThread import covariance_QThread
from Plotters.covariance_plotter import covariancePlotter
from Plotters.mass_calibration import massCalibration

pg.setConfigOption('foreground', 'k')
pg.setConfigOption('background', 'w')

class MainWindow(QtWidgets.QWidget):
    run_covar_calc = pyqtSignal(str, float, float)

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        #Load the UI Page
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'GUI_layouts', 'covariance_gui.ui'), self)

        # Set defaults
        self.cur_path = os.path.expanduser(r'~\Documents')
        self.plot_type = 'partial'
        self.plot_started = False
        self.processed_files = {}
        self.queue = []

        # Set up QThreads
        self.initialise_cov_qthread()

        # Set up classes
        self.covariance_plotter = covariancePlotter(self, self.covMapWidget, self.contrastSpin)
        self.mass_cali_plotter = massCalibration(self)

        # Connect signals
        self.openFile.clicked.connect(lambda: self.select_file(self.fileName))
        self.plotCovariance.clicked.connect(self.load_covariance)
        self.resetCovMap.clicked.connect(self.reset)
        self.mass_cali_plotter.new_mass_calibration.connect(self.covariance_plotter.update_mass_calibration)


    def initialise_cov_qthread(self):
        # Set up the covariance QThread
        self.thread = QThread()

        # Initialise the worker class
        self.worker = covariance_QThread()

        # Move the worker to the thread
        self.worker.moveToThread(self.thread)

        # Add link to the status label to the worker
        self.worker.statusLabel = self.guiStatus

        # Connect signals and slots
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.run_covar_calc.connect(self.worker.run_covariance)
        self.worker.output.connect(self.process_output)

        # Start the thread
        self.thread.start()


    def load_covariance(self):
        if not self.plot_started:
            # Read the moving average smoothing time and bin size from the GUI
            self.smoothing_t = self.movAvgSpread.value()
            self.bin_size = self.rebinSpin.value()

            # Fix the values by disabling the spin boxes
            self.movAvgSpread.setEnabled(False)
            self.rebinSpin.setEnabled(False)

            self.covariance_plotter.cov_size = int(np.ceil(120_000 / self.bin_size))

        for _fname in self.fileName.text().split(';'):
            _fname = _fname.strip()
            # Check for whether file has already been calculated
            try:
                self.processed_files[_fname]

            except KeyError:
                self.processed_files[_fname] = 0

                # Run the calculation
                self.run_covar_calc.emit(_fname, self.bin_size, self.smoothing_t)


    @pyqtSlot(object, object, object, object, int, str)
    def process_output(self, cov_XY, pcov, cov_size, mass_spec, n_cycles, fname):
        self.processed_files[fname] = n_cycles

        next_row = self.loadDataParamTable.rowCount()

        # Update the loaded data notes
        self.loadDataParamTable.insertRow(next_row)
        self.loadDataParamTable.setItem(next_row, 0, QtWidgets.QTableWidgetItem(os.path.basename(fname)))
        self.loadDataParamTable.setItem(next_row, 1, QtWidgets.QTableWidgetItem(str(n_cycles)))

        # Update image
        self.covariance_plotter.update(cov_XY, pcov, n_cycles)

        # Update mass spec
        self.mass_cali_plotter.update_tof(mass_spec, n_cycles)


    def reset(self):
        # Clear and reset all variables related to the plot
        self.loadDataParamTable.setRowCount(0)
        self.loadDataParamTable.clearContents()

        self.processed_files = {}

        self.movAvgSpread.setEnabled(True)
        self.rebinSpin.setEnabled(True)

        self.plot_started = False

        self.covariance_plotter.reset()

        try: del self.mass_cali_plotter.tof
        except AttributeError: pass

        self.mass_cali_plotter.plotted_cycles = 0


    def select_file(self, fileTextBox):
        fname = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open file', self.cur_path, 'h5 files (*.h5);;All files (*.*)')
        
        # If a file is chosen, update the display and save the default path
        if fname[0] != '':
            try:
                fileTextBox.setText(fname[0])
                self.cur_path = os.path.dirname(fname[0])
            except TypeError:
                if fname[0] != []:
                    fileTextBox.setText('; '.join(fname[0]))
                    self.cur_path = os.path.dirname(fname[0][-1])

                    # # Update the default directories only if they have not been set yet
                    # if self.save_window.cur_path == '':
                    #     self.save_window.set_default_path(default_path = self.cur_path)



    def closeEvent(self, event):
        # Safely shuts down the covariance QThread
        if self.thread.isRunning():
            # Tell the thread to stop
            self.thread.terminate()

            # Wait for the thread to completely finish its cleanup
            self.thread.wait()

        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec()

if __name__ == '__main__':
    main()
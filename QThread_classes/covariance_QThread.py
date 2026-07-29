from PyQt6.QtCore import *
from Functions.plot_partial_covariance import generate_covariance_matrix
import os

class covariance_QThread(QObject):
    output = pyqtSignal(object, object, object, object, int, str)
    finished = pyqtSignal()

    @pyqtSlot(str, float, float)
    def run_covariance(self, fname, bin_size, smoothing_t):
        self.statusLabel.setText(f'Status: Processing {os.path.basename(fname)}...')
        try:
            cov_XY, pcov, cov_size, mass_spec, n_cycles = generate_covariance_matrix(fname, bin_size, smoothing_t, False)

            self.output.emit(cov_XY, pcov, cov_size, mass_spec, n_cycles, fname)

        except OSError:
            # Case where the file does not exist
            pass

        self.statusLabel.setText('Status: Idle')
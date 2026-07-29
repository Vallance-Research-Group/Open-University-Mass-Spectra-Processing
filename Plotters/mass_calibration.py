import pyqtgraph as pg
from PyQt6.QtCore import *
from PyQt6.QtGui import QTransform, QPen
import numpy as np
import scipy.stats

class massCalibration(QObject):
    new_mass_calibration = pyqtSignal(object)

    def __init__(self, main_variables):
        super().__init__()
        # Get references from the GUI
        self.massCaliTable = main_variables.massCaliTable

        # Set up connections
        main_variables.massCaliAddButton.clicked.connect(self.add_row)
        main_variables.massCaliRemoveButton.clicked.connect(self.remove_row)
        main_variables.massCaliClearButton.clicked.connect(self.clear_table)
        main_variables.plotMassCali.clicked.connect(self.generate_mass_cali)
        main_variables.radioToF.clicked.connect(self.plot_tof)
        main_variables.radioMassCharge.clicked.connect(self.plot_tof)

        self.radioMassCharge = main_variables.radioMassCharge

        # Initialise the calibration fit graph
        self.calibrationFitWidget = main_variables.calibrationFitWidget
        self.calibrationFitWidget.showAxis('right')
        self.calibrationFitWidget.showAxis('top')
        self.calibrationFitWidget.setLabel('left', '(m/q)^0.5')
        self.calibrationFitWidget.setLabel('bottom', 'Timecode')
        self.calibrationFitWidget.setLimits(yMin=0)
        self.caliFitScatter = pg.ScatterPlotItem()
        self.calibrationFitWidget.addItem(self.caliFitScatter)
        self.massCaliFit = self.calibrationFitWidget.plot([0], [0.5], pen={'color':'r', 'width': 1, 'style': Qt.PenStyle.DashLine})
        self.plot_line = main_variables.massCaliToF.plot([0], [0.5], pen={'color':'k', 'width': 1})

        self.plotted_cycles = 0


    def add_row(self):
        self.massCaliTable.insertRow(self.massCaliTable.rowCount())

    def remove_row(self):
        # Populate an array with all selected rows
        rows_to_remove = []
        total_rows = self.massCaliTable.rowCount()

        for selection_range in self.massCaliTable.selectedRanges():
            top = selection_range.topRow()
            bottom = selection_range.bottomRow()

            for i in range(top, bottom+1):
                if i not in rows_to_remove:
                    rows_to_remove.append(i)

        if len(rows_to_remove) == total_rows:
            # All rows need removing
            self.clear_table()
        else:
            # Clear only the selected rows (start from the end so removing rows doesn't muck up indexing)
            rows_to_remove = np.flip(np.sort(np.array(rows_to_remove)))
            for i in rows_to_remove:
                self.massCaliTable.removeRow(i)

    def clear_table(self):
        # Clears the table
        self.massCaliTable.setRowCount(2)
        self.massCaliTable.clearContents()

    def remove_non_numerical_data(self):
        # Removes non-numerical data (since this will cause errors)
        for i in np.arange(self.massCaliTable.rowCount()-1, -1, -1):
            try:
                float(self.massCaliTable.item(i, 0).text())
                float(self.massCaliTable.item(i, 1).text())
            except ValueError:
                # Handle text
                self.massCaliTable.removeRow(i)
                
            except AttributeError:
                # Handle empty cell (check second column does not contain text)
                try:
                    float(self.massCaliTable.item(i, 1).text())
                except ValueError:
                    self.massCaliTable.removeRow(i)
                except AttributeError:
                    pass


    def update_tof(self, tof, n_cycles):
        try: self.tof = self.tof * self.plotted_cycles + tof * n_cycles
        except AttributeError: self.tof = tof

        self.plotted_cycles += n_cycles

        self.apply_mass_calibration()
        self.plot_tof()

    def plot_tof(self):
        try:
            if self.radioMassCharge.isChecked() == False:
                # Plot the ToF
                self.plot_line.setData(np.arange(0,len(self.tof)), self.tof)
            else:
                # Plot the data (applying appropriate Jacobian)
                intensity = self.tof[self.min_time:] / self.m_q ** 0.5

                # Handle empty array (not realistic in real data, but oh well)
                if max(intensity) == 0:
                    self.plot_line.setData(self.m_q, intensity)
                else:
                    self.plot_line.setData(self.m_q, intensity / max(intensity) * 100)

        except AttributeError: pass


    def generate_mass_cali(self):
        # Obtain K and t_0 for the following equation (m/q)^0.5 = K * (t_PImMS - t_0)
        self.remove_non_numerical_data()

        # Initialise variables
        no_rows = self.massCaliTable.rowCount()
        time_array = np.zeros(no_rows)
        mass_charge_array = np.zeros(no_rows)

        # Read the table
        for i in range(no_rows):
            try:
                time_array[i] = float(self.massCaliTable.item(i, 0).text())
                mass_charge_array[i] = float(self.massCaliTable.item(i, 1).text())
            except AttributeError:
                pass

        # Remove any rows which contained empty fields
        time_array = time_array[mass_charge_array != 0]
        mass_charge_array = mass_charge_array[mass_charge_array != 0] ** 0.5

        # Plot a graph
        self.caliFitScatter.setData(time_array, mass_charge_array)

        # Check there are sufficient points to generate a mass calibration
        if len(time_array) < 2:
            print('Insufficient points for a mass calibration.')
            return

        # Carry out linear regression to get the slope and intercept
        slope, intercept, *args = scipy.stats.linregress(time_array, mass_charge_array, 'greater')

        self.mass_cali_params = {'prop_const': slope, 'time_zero': -intercept/slope}

        t_limits = np.array([time_array.min(), time_array.max()])

        # Add a line to show the fit
        self.massCaliFit.setData(t_limits, t_limits * slope + intercept)

        # Calculate the m / q values for each time > t_0
        self.min_time = int(np.ceil(self.mass_cali_params['time_zero']))
        if self.min_time < 0:
            self.min_time = 0

        # Set the radio button enabled
        self.radioMassCharge.setEnabled(True)

        self.apply_mass_calibration()

        self.new_mass_calibration.emit(self.mass_cali_params)


    def apply_mass_calibration(self):
        try:
            self.m_q = np.zeros(len(self.tof))
            self.m_q[self.min_time:] = np.round(((np.arange(self.min_time,len(self.tof)) - self.mass_cali_params['time_zero']) * self.mass_cali_params['prop_const']) ** 2, 2)

            # Replot the ToF
            self.plot_tof()

        except AttributeError:
            # Handle case where tof isn't plotted yet
            pass

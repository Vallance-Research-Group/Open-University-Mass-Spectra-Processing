import pyqtgraph as pg
import numpy as np

class ToFPlotter():
    def __init__(self, main_variables):
        # Add the widgets
        self.ToFWidget = main_variables.ToFWidget

        # Add the widgets that need to be updated
        self.minTimeSpin = main_variables.minTimeSpin

        # Set the limits and the initial view
        self.ToFWidget.setLimits(xMin=0, xMax=120000)
        self.ToFWidget.setRange(xRange=(0,100000))

        # Plot axes on top and right
        self.ToFWidget.showAxis('right')
        self.ToFWidget.showAxis('top')

        # Generate limit bar and add to plot
        self.vbar = pg.InfiniteLine(pos=self.minTimeSpin.value(), angle=90, movable=True, bounds=(0,120000))
        self.ToFWidget.addItem(self.vbar)

        # ToF limits moved
        self.vbar.sigPositionChangeFinished.connect(self.vbar_moved)

        # Initialise line
        self.plot_line = self.ToFWidget.plot([0], [0.5], pen={'color':'k', 'width': 1})

        # ToF limits changed
        self.minTimeSpin.valueChanged.connect(self.limits_changed)


    def update(self, tof):
        # Add ToF to the class
        self.tof = tof

        # Plot the ToF
        self.plot_line.setData(np.arange(len(tof)), tof)


    def vbar_moved(self):
        # Update the spin box value
        self.minTimeSpin.blockSignals(True)
        self.minTimeSpin.setValue(int(np.round(self.vbar.value())))
        self.minTimeSpin.blockSignals(False)


    def limits_changed(self, value):
        # Update the slider position to the spin box value
        self.vbar.blockSignals(True)
        self.vbar.setValue(value)
        self.vbar.blockSignals(False)
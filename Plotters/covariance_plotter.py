from timeit import default_timer
import pyqtgraph as pg
from PyQt6.QtCore import *
from PyQt6.QtGui import QTransform
import numpy as np
from copy import deepcopy
import cv2

class covariancePlotter(QObject):
    def __init__(self, main_variables, imageWidget, imageContrastSpin):
        super().__init__()

        # Add the image widget
        self.imageWidget = imageWidget

        # Make sure the image remain square
        self.imageWidget.setAspectLocked()
        self.imageWidget.disableAutoRange()

        # Add widgets from the main class that need to be updated
        self.colourMapCombo = main_variables.colourMapCombo

        # Add the parameters to reference when plotting images
        self.contrastSpin = imageContrastSpin
        self.reverseCMapCheck = main_variables.reverseCMap

        # Set up connections
        imageContrastSpin.valueChanged.connect(self.change_contrast)
        self.colourMapCombo.currentIndexChanged.connect(self.updateImage)
        self.reverseCMapCheck.stateChanged.connect(self.updateImage)

        # Cycles weighting factor is the number of cycles plotted, minus the
        # number of degrees of freedom, so if we have a total of n cycles plotted,
        # from k different images, it's value will be n - k
        # The - k is required since we are dealing with samples, rather than populations.
        self.cycles_weighting_factor = 0

        self.cur_plot_type = 'pcov'
        self.log_scale_applied = False

        # Initialise image_shape as an array of positive integers
        self.image_shape = np.ones(2)

        # Populate the image with an empty array
        self.ionImage = np.zeros((324,324)); self.updateImage()

        # Add the relevant widget references to the class
        self.zeroNegative = main_variables.zeroNegativeCheck
        self.cBarCentreZero = main_variables.cBarCentreZeroCheck
        self.logScale = main_variables.logScaleCheck
        self.gaussBlurCheck = main_variables.gaussBlurCheck
        self.gaussBlurSigma = main_variables.gaussBlurSigma
        self.timeMousePos = main_variables.timeMousePosition
        self.mzMousePos = main_variables.mzMousePosition
        self.valueMousePos = main_variables.valueMousePosition

        # Add plotting connections
        self.zeroNegative.stateChanged.connect(lambda: self.plot_option_changed('zero_neg'))
        self.cBarCentreZero.stateChanged.connect(lambda: self.plot_option_changed('centre_zero'))
        self.logScale.stateChanged.connect(lambda: self.plot_option_changed('log'))
        self.gaussBlurCheck.stateChanged.connect(self.updateImage)
        self.gaussBlurSigma.valueChanged.connect(self.updateImage)
        main_variables.plotRegCovarButton.clicked.connect(lambda: self.toggle_map_type('regcov'))
        main_variables.plotPCovarButton.clicked.connect(lambda: self.toggle_map_type('pcov'))
        self.imageWidget.scene().sigMouseMoved.connect(self.update_mouse_location)

    def reconstruct_square_matrix(self, mat):
        # Convert the input matrix into a full matrix
        full = np.zeros((self.cov_size, self.cov_size))
        iu = np.triu_indices(self.cov_size)
        full[iu] = mat
        full[(iu[1], iu[0])] = mat

        return full


    def update(self, cov_XY, pcov, n_cycles):
        try:
            # Determine the weighting of the two terms
            a = self.cycles_weighting_factor / (self.cycles_weighting_factor + n_cycles - 1)
            b = (n_cycles - 1) / (self.cycles_weighting_factor + n_cycles - 1)

            # Apply the weightings
            self.cov_XY = a * self.cov_XY + b * cov_XY            
            self.pcov = a * self.pcov + b * pcov

        except AttributeError:
            self.cov_XY = cov_XY; self.pcov = pcov

        # Add on the cycles to allow further covariance maps to be combined
        self.cycles_weighting_factor += n_cycles - 1

        # Add the ion image to the plotter class
        self.generate_image()


    def generate_image(self):
        try:
            if self.cur_plot_type == 'pcov':
                self.ionImage = self.reconstruct_square_matrix(self.pcov)

            else:
                self.ionImage = self.reconstruct_square_matrix(self.cov_XY)

            # If plotting on log scale, negative numbers are not defined, so make them a small number
            if self.logScale.isChecked():
                self.ionImage[self.ionImage <= 0] = np.min(self.ionImage[self.ionImage > 0]) / 10
                self.ionImage = np.log10(self.ionImage)

        except AttributeError:
            return

        # Plot the image
        self.updateImage()


    def reset(self):
        self.cycles_weighting_factor = 0
        self.ionImage.fill(0)
        try:
            del self.cov_XY, self.pcov

        except AttributeError:
            pass

        self.updateImage()


    def toggle_map_type(self, clicked_button):
        # Process case where there is no changed
        if self.cur_plot_type == clicked_button: return

        # Update the flag
        self.cur_plot_type = clicked_button

        # Update the plotted image with the appropritate cov map
        self.generate_image()

        
    def plot_option_changed(self, option_changed):
        # Only one of the options regarding the colour scale can be checked at once. None checked is fine.
        self.cBarCentreZero.blockSignals(True)
        self.zeroNegative.blockSignals(True)
        self.logScale.blockSignals(True)
        self.contrastSpin.blockSignals(True)

        # Make the three options exclusive, as they are not compatible
        if option_changed == 'zero_neg' and self.zeroNegative.isChecked():
            self.cBarCentreZero.setChecked(False)
            self.logScale.setChecked(False)

            # Reset image if required
            if self.log_scale_applied:
                self.generate_image()
                self.log_scale_applied = False
                self.contrastSpin.setValue(0.0001)
                self.contrastSpin.setMaximum(1.)

        elif option_changed == 'centre_zero' and self.cBarCentreZero.isChecked():
            self.zeroNegative.setChecked(False)
            self.logScale.setChecked(False)

            # Reset image if required
            if self.log_scale_applied:
                self.generate_image()
                self.log_scale_applied = False
                self.contrastSpin.setValue(0.0001)
                self.contrastSpin.setMaximum(1.)

        elif option_changed == 'log' and self.logScale.isChecked():
            self.zeroNegative.setChecked(False)
            self.cBarCentreZero.setChecked(False)
            self.generate_image()

            self.log_scale_applied = True
            self.contrastSpin.setValue(1.)
            self.contrastSpin.setMaximum(10.)

        elif option_changed == 'log':
            self.generate_image()
            self.log_scale_applied = False
            self.contrastSpin.setValue(0.0001)
            self.contrastSpin.setMaximum(1.)

        # Unblock signals to allow clicks to be registered again
        self.zeroNegative.blockSignals(False)
        self.cBarCentreZero.blockSignals(False)
        self.logScale.blockSignals(False)
        self.contrastSpin.blockSignals(False)

        # Update the colour map
        self.change_contrast()


    def change_contrast(self):
        # The contrast should be stored in the class and changed as required
        contrast = self.contrastSpin.value()

        try:
            # Select the appropriate limits for the chosen contrast
            if self.zeroNegative.isChecked():
                im_max = self.ionImage.max() * contrast
                im_min = 0.

            elif self.cBarCentreZero.isChecked():
                # Pick the greatest extreme and use that to determine the appropriate limits
                im_max = self.ionImage.max() * contrast; im_min = self.ionImage.min() * contrast
                if im_max > abs(im_min):
                    im_min = -im_max
                else:
                    im_max = -im_min

            elif self.logScale.isChecked():
                # We need to fix the im_min, and make sure im_min < im_max.
                min_val = self.ionImage.min()
                im_max = (self.ionImage.max() - min_val) * contrast + min_val
                if min_val < 0:
                    im_min = min_val * 1.000000000001
                else:
                    im_min = min_val * 0.999999999999

            else:
                im_max = self.ionImage.max() * contrast
                im_min = self.ionImage.min() * contrast

            if im_max == im_min:
                # Make sure there is a colour bar when the limits are the same
                self.colourBar.setLevels(values=(im_min,im_min+0.001 * contrast))

            else:
                # Update the colur bar limits
                self.colourBar.setLevels(values=(im_min,im_max))
        except AttributeError:
            pass

    def updateImage(self):
        # Check image has been added
        try:
            self.ionImage
        except AttributeError:
            return

        try:
            # Set the new image
            if self.gaussBlurCheck.isChecked():
                self.img.setImage(self.apply_gaussian_blur(self.ionImage))
            else:
                self.img.setImage(self.ionImage)

            # Update the colour bar if it exists
            cmap = deepcopy(pg.colormap.get(self.colourMapCombo.currentText()))
            if self.reverseCMapCheck.isChecked():
                cmap.reverse()
            self.colourBar.setColorMap(cmap)
            self.colourBar.setImageItem(self.img)

        except AttributeError:
            # Create image data type
            self.img = pg.ImageItem(image = self.ionImage)

            # Add ion image to widget
            self.imageWidget.addItem(self.img)
            
            # # Remove x and y ticks and labels
            # self.imageWidget.getPlotItem().hideAxis('bottom')
            # self.imageWidget.getPlotItem().hideAxis('left')

            # Add colour bar (not visible)
            self.colourBar = pg.ColorBarItem(colorMap=self.colourMapCombo.currentText(), interactive=False)
            self.colourBar.setImageItem(self.img)
            # Add colour bar (visible)
            # self.colourBar = self.imageWidget.addColorBar(self.img, colorMap=self.colourMapCombo.currentText(), interactive=False)
    
        # Define a transform to get numbers in the centre of the pixels and apply
        transform = QTransform()
        transform.translate(-0.5, -0.5)
        self.img.setTransform(transform)

        # Set the range to the image size if it has changed
        imageShape = self.ionImage.shape
        if not np.array_equal(imageShape, self.image_shape):
            self.imageWidget.setLimits(xMin=0, xMax=imageShape[0], yMin=0, yMax=imageShape[1])
            # self.imageWidget.setRange(xRange=(0,imageShape[0]), yRange=(0,imageShape[1]))
            self.imageWidget.enableAutoRange()

            # Set the current shape as the new benchmark
            self.image_shape = imageShape

        self.change_contrast()
        

    def apply_gaussian_blur(self, img):
        return cv2.GaussianBlur(img, (0,0), sigmaX=self.gaussBlurSigma.value())

    
    def update_mouse_location(self, mouse_location):
        # Get the position and add to the display. Note the -0.5 to make the number match with the indexing.
        image_position = self.imageWidget.plotItem.vb.mapSceneToView(mouse_location)
        self.timeMousePos.setText(f'({round(image_position.x(), 1)}, {round(image_position.y(), 1)})')
        
        try:
            intensity = self.ionImage[int(round(image_position.x())), int(round(image_position.y()))]
            self.valueMousePos.setText(f'{intensity:.3g}')

        except IndexError:
            # Case where hovering outside image limits within image widget
            pass

        try:
            if image_position.x() > self.mass_cali_params['time_zero']:
                m_q_x = np.round(((image_position.x() - self.mass_cali_params['time_zero']) * self.mass_cali_params['prop_const']) ** 2, 1)
            else:
                m_q_x = -1

            if image_position.y() > self.mass_cali_params['time_zero']:
                m_q_y = np.round(((image_position.y() - self.mass_cali_params['time_zero']) * self.mass_cali_params['prop_const']) ** 2, 1)
            else:
                m_q_y = -1

            self.mzMousePos.setText(f'({m_q_x}, {m_q_y})')

        except AttributeError:
            # Case where no mass calibration applied
            pass


    @pyqtSlot(object)
    def update_mass_calibration(self, mass_cali_params):
        self.mass_cali_params = mass_cali_params

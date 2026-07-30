# Open University Mass Spectra Processing
This repository contains code for use as part of a collaboration with the Eden group at Open University to determine correlations using high-resolution mass spectrometry. The available scripts are outlined below.

## GUI scripts

### file_converter_gui.py
Used to convert .lst files into compressed .h5 files. To use the script, input files are selected by pressing the button next to the input file name. On selecting files, the output file name will be auto-populated with the same name but with the .h5 file extension. This can be changed if necessary.

Pressing **Convert File** will convert the input **.lst** files into **.h5** files. Any ion arrival times less than *Min time* are discarded. This can be helpful if there is significant noise from the extraction pulse. *Read line count* determines the number of lines of the .lst file to read at once, and needs to be adjusted according to the computer specification used for processing. Multiple files can be queued for conversion, and progress is updated in the *Proc. Queue* display.

Pressing **Plot ToF** will plot the time-of-flight (ToF) based on the first *Cycles to read*, again using *Read line count* to determine the number of lines in a chunk. Plotting the ToF can be useful when setting *Min time*.

In the code, it is assumed that the ion count in an acquisition cycle will not exceed 255. If an error is seen to this effect, it will be necessary to change the data format for ion counts to `<u2` instead of `<u1`.

### covariance_gui.py
Used to plot ToF-ToF covariance maps of the converted **.h5** files. Files are specified in the approprite field, and can be appended to the plot by pressing **Calculate covariance and add**. The covariance maps are weighted according to number of acquisition cycles[1] when combined. There are various options for plotting the covariance maps. *Moving average cycle spread* defines the time spread used when calculating the variable parameter for the partial covariance correction. The details of how this is carried out can be found below [2]. *Rebinning factor* defines the number of arrival times to bin together. Since there are over 100000 arrival times in the original data, the covariance map can become prohibitively large without setting this to a sensible value. The various other plot options should be self-explanatory. Both of these inputs lock on plotting the first covariance map to keep things consistent. To toggle between partial and regular covariance maps, press the appropriate buttons. To reset the plot and allow the input parameters to be changed, press *Reset (clears all data)*.

At present, saving options have not been implemented, but the covariance map image can be saved by right clicking on the plot and selecting export.

On the second tab, a mass calibration can be applied. Pairs of arrival times and known mass-to-charge ratios should be input in the table on the left, then plot calibration pressed. If the calibration is reasonable, points lying on a straight line should appear on the plot to the right, and peaks should appear at sensible m/z values. Rows can be added and removed to the table using the appropriate buttons. Once a mass calibration is completed, the m/z of the current mouse position will be added on the main covariance tab.

Loaded files are listed in the final tab, along with the total number of acquisition cycles in the file. **Please note that files of the same name cannot be included twice, even if they are in different directories.**

## Standalone scripts (found in Functions)

### lst_to_h5 converter.py
Very similar to the GUI version, but just converts a single selected .lst file into an output .h5 file. The minimum time and lines to read will need to be set manually in the back end using this script.

### plot_covariance.py
Plots covariance maps. Offers less flexibility than the GUI, as plot options cannot be changed live, and files cannot be combined at present.

### plot_mass_spec_raw.py
Plot the ToF from a .lst file. Note that the file conversion GUI may be preferable here, as you can set the number of acquisition cycles to read, given the ToF will primarily be plotted at this point to determine where the cut-off for extraction noise.

### plot_mass_spec.py
Plot the ToF from a .h5 file.

### plot_partial_covariance.py
Similar to plot_covariance.py, except plots partial covariance maps.

## Notes on data formats used here

### .lst
The .lst files are text-based files with the following format:

Header (36 line)
Identifier of the start of data: '[DATA]'
The data is a list of arrival times, with zeros denoting the start of an acquisition cycle

For example:
```
0
12
24
52
0
24
0
21
42
```

This dataset would consist of three acquisition cycles. The first would have three ions arriving, as times 12, 24 and 52, the second would have a single ion arriving at time 24, and the third two ions arriving at times 21 and 42.

### .h5
The .h5 file uses the standard hdf5 architecture. It contains three datasets: Header, Ion counts, and Arrival times. The ion counts and arrival times are both compressed using gzip.

The header contains the same information as the header in the lst file. Ion counts is a numerical array containing the total ion counts for each acquisition cycle. For example, ion counts for the dataset in the .lst section above would be `[3, 1, 2]`. Arrival times is also a numerical array, containing a list of all the arrival times. Using the same example, arrival times would be `[12, 24, 52, 24, 21, 42]`. Ion counts are defined as 8-bit unsigned integers, and arrival times as 32-bit unsigned integers (both little-endian). By using the ion counts, the arrival times for each acquisition cycle can be determined. As noted above, if the ion counts increase above 255 per cycle, then a 16-bit integer may be required instead.

## Footnotes
1. Strictly, the code accounts for the fact that the measurements are necessarily samples, so subtracts one from the total number of acquisition cycles for each covariance map plotted. In practice, this difference is negilible for the datasets being used.
1. The variable parameter used for partial covariance is calculated using an exponential moving average of the total ion count in each acquisition cycle. We define a scaling factor, $k = \frac{2}{1+t}$, where $t$ is the value defined in *Moving average cycle spread*. If we define the ion count in the $j^{th}$ acquisition cycle as $S_j$, the $j^{th}$ variable parameter, $I_j$, is then defined as $I_j = S_j k + S_{j-1} (1-k)$. We choose $I_0 = S_0$ as the initial value.

from PyQt6.QtCore import *
import h5py
import numpy as np
from numba import jit
import os

@jit(nopython=True, cache=True)
def process_data(tof, times, counts, proc_tof_cycles, req_tof_cycles):
    start = 0
    for _count in counts:
        stop = start + _count

        for _time in times[start:stop]:
            tof[_time] += 1

        start = stop
        
        proc_tof_cycles += 1

        if proc_tof_cycles == req_tof_cycles:
            break

    return proc_tof_cycles

class tof_QThread(QObject):
    output = pyqtSignal(object)

    @pyqtSlot(str,int,int)
    def read_tof(self, fname, req_tof_cycles, line_read_count=10_000_000):
        # Initialise values
        TOF = np.zeros(120000)
        proc_tof_cycles = 0

        for _ in fname.split(';'):
            if not os.path.exists(_): continue

            with open(_.strip(), 'r') as in_f:
                # Skip the header
                [in_f.readline().strip() for i in range(37)]

                # Set up for buffering (holds hangover from previous chunk, so will either be empty or start with a zero)
                pending = np.empty(0, dtype='<u4')


                while req_tof_cycles > proc_tof_cycles:
                    # Read line_read_count lines to process
                    chunk = np.fromfile(in_f, dtype='<u4', count=line_read_count, sep='\n')

                    # Quit if no more data to read
                    if chunk.size == 0: break

                    if pending.size != 0:
                        chunk = np.concatenate((pending, chunk))
                        pending = np.empty(0, dtype='<u4')

                    zero_positions = np.flatnonzero(chunk == 0)

                    # Check for this, but this is very much not expected!
                    if zero_positions.size < 2:
                        pending = chunk; continue

                    # Get the start and stop positions of all complete cycles in the chunk
                    cycle_start_pos = zero_positions[:-1]
                    cycle_stop_pos = zero_positions[1:]

                    # This is the difference between different zero positions
                    # i.e. it is the number of ions recorded in the cycle
                    # (-1) to as the zero is not counted
                    counts = cycle_stop_pos - cycle_start_pos - 1

                    time_mask = chunk > 0

                    # Keep just the times where time is above or equal to the minimum time
                    times = chunk[:zero_positions[-1]][time_mask[:zero_positions[-1]]]

                    # Add to ToF
                    proc_tof_cycles = process_data(TOF, times, counts, proc_tof_cycles, req_tof_cycles)

                    # Add the remaining chunk to pending
                    pending = chunk[zero_positions[-1]:]


                # Process final bit of file
                if pending.size > 1 and req_tof_cycles > proc_tof_cycles:
                    cycle_data = pending[1:]
                    times = cycle_data[cycle_data > 0]
                    counts = np.array(times.size)

                    proc_tof_cycles = process_data(TOF, times, counts, proc_tof_cycles, req_tof_cycles)

            if req_tof_cycles <= proc_tof_cycles:
                break

        self.output.emit(TOF)
        return TOF

if __name__ == '__main__':
    import matplotlib.pyplot as plt

    fname = r'C:\Users\chem-hert4067\Documents\Open University collaboration\Benzo data for test\Benzonitrile data 23 07 2025-20260604T204042Z-3-001\Benzonitrile data 23 07 2025\4.lst'

    test = tof_QThread()
    tof = test.read_tof(fname, 1000)

    plt.figure()
    plt.plot(tof)
    plt.show()
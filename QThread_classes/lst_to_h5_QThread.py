from PyQt6.QtCore import *
import numpy as np
import os
from timeit import default_timer
import struct
import h5py

def main():
    # Skeleton class to allow this script to be run as a standalone
    class cancelEvent():
        def is_set(self):
            return False

    in_fname = r'C:\Users\chem-hert4067\Documents\Open University collaboration\Benzo data for test\Benzonitrile data 23 07 2025-20260604T204042Z-3-001\Benzonitrile data 23 07 2025\4.lst'
    out_fname = r'C:\Users\chem-hert4067\Documents\Open University collaboration\Benzo data for test\Benzonitrile data 23 07 2025-20260604T204042Z-3-001\Benzonitrile data 23 07 2025\test_4.h5'

    test = lstConvertQRunnable(in_fname, out_fname, cancelEvent(), 2500)

    test.run()


class workerSignals(QObject):
    # Temporary QObject to allow signals to be used
    finished = pyqtSignal(str, str)
    abort = pyqtSignal(str, str)
    start_proc = pyqtSignal(str, str)
    progress = pyqtSignal(str, float)


def append_dataset(dset, data):
    if data.size == 0: return

    old_size = dset.shape[0]
    new_size = old_size + data.size
    dset.resize((new_size,))
    dset[old_size:new_size] = data


class lstConvertQRunnable(QRunnable):
    def __init__(self, in_fname, out_fname, cancel_event, min_time=2500, line_read_count=10_000_000):
        super().__init__()
        self.signals = workerSignals()
        self.cancel_event = cancel_event
        self.files = in_fname, out_fname
        self.params = min_time, line_read_count
        

    def run(self):
        # Unpack the variables
        in_fname, out_fname = self.files
        min_time, line_read_count = self.params

        self.signals.start_proc.emit(in_fname, out_fname)

        # Initial check to see whether the thread has been cancelled
        if self.cancel_event.is_set():
            self.signals.abort.emit(in_fname, out_fname)
            return

        if not min_time > 0:
            raise ValueError('Minimum time must be greater than zero.')

        file_size = os.path.getsize(in_fname)

        x = default_timer()

        with open(in_fname, 'r') as in_f, h5py.File(out_fname, 'w') as out_f:
            # Write header to file
            dt = h5py.string_dtype(encoding='utf-8')
            dset_header = out_f.create_dataset('Header', shape=(36,), dtype=dt)
            dset_header[:] = [in_f.readline().strip() for i in range(36)]

            # Skip the [DATA] line of the file
            in_f.readline()

            # Set up datasets for ion count and arrival times
            dset_counts = out_f.create_dataset('Ion counts',
                shape=(0,),
                maxshape=(None,),
                dtype="<u1",
                chunks=(1_000_000,),
                compression="gzip",
                shuffle=True,
            )

            dset_times = out_f.create_dataset('Arrival times',
                shape=(0,),
                maxshape=(None,),
                dtype="<u4",
                chunks=(10_000_000,),
                compression="gzip",
                shuffle=True,
            )

            # Set up for buffering (holds hangover from previous chunk, so will either be empty or start with a zero)
            pending = np.empty(0, dtype='<u4')

            while True:
                if self.cancel_event.is_set():
                    self.signals.abort.emit(in_fname, out_fname)
                    return

                current_pos = in_f.tell()

                self.signals.progress.emit(out_fname, np.round((current_pos / file_size) * 100, 1))

                # Read line_read_count lines to process
                chunk = np.fromfile(in_f, dtype='<u4', count=line_read_count, sep='\n')

                # Quit if no more data to read
                if chunk.size == 0: break

                if pending.size != 0:
                    chunk = np.concatenate((pending, chunk))
                    pending = np.empty(0, dtype='<u4')

                zero_positions = np.flatnonzero(chunk == 0)

                # Check for case where there is only a single cycle in the chunk, but this is very much not expected!
                if zero_positions.size < 2:
                    pending = chunk; continue

                # Get the start and stop positions of all complete cycles in the chunk
                cycle_start_pos = zero_positions[:-1]
                cycle_stop_pos = zero_positions[1:]

                # Arrival time mask
                time_mask = chunk >= min_time

                # Count retained values in each cycle using cumulative sum.
                # csum is the cumulative sum of keep.
                csum = np.cumsum(time_mask, dtype=np.uint32)

                # This is the difference between csum at different zero positions
                # i.e. it is the number of ions recorded in the cycle
                counts = csum[cycle_stop_pos] - csum[cycle_start_pos]

                if counts.max(initial=0) > 255:
                    raise ValueError(f'Ion count too high for the compressed data format: {counts.max()}')

                counts = counts.astype('<u1', copy=False)

                # Keep just the times where time is above or equal to the minimum time
                times = chunk[:zero_positions[-1]][time_mask[:zero_positions[-1]]]

                # Write to dataset
                append_dataset(dset_counts, counts)
                append_dataset(dset_times, times.astype('<u4', copy=False))

                # Add the remaining chunk to pending
                pending = chunk[zero_positions[-1]:]


            # Process final bit of file
            if pending.size > 1:
                cycle_data = pending[1:]
                times = cycle_data[cycle_data >= min_time]
                n = times.size

                if n > 255:
                    raise ValueError(f"Ion count too high for the compressed data format: {n}")

                append_dataset(dset_counts, np.array([n], dtype="<u1"))
                append_dataset(dset_times, times.astype("<u4", copy=False))

        y = default_timer()

        print(f'File converted in: {np.round(y-x, 1)} s')

        self.signals.finished.emit(in_fname, out_fname)

if __name__ == '__main__':
    main()
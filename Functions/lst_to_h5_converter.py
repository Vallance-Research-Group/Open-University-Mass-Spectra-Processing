import numpy as np
import os
from timeit import default_timer
import struct
import h5py
from tkinter import filedialog, Tk

def main():
    root = Tk()
    root.withdraw()

    #Choose file to open
    fname = filedialog.askopenfilename(title = "Select file",\
    filetypes = (("lst files","*.lst"),("All files","*.*")))
    
    if fname == '': return

    convert_file_chunking_h5(fname, 2500)

###########################
# h5 version

def append_dataset(dset, data):
    if data.size == 0: return

    old_size = dset.shape[0]
    new_size = old_size + data.size
    dset.resize((new_size,))
    dset[old_size:new_size] = data


def convert_file_chunking_h5(fname, min_time=2500, line_read_count=10_000_000):
    if not min_time > 0:
        raise ValueError('Minimum time must be greater than zero.')

    x = default_timer()

    conv_fname = os.path.join(os.path.dirname(fname), os.path.basename(fname).split('.lst')[0] + '.h5')
    with open(fname, 'r') as in_f, h5py.File(conv_fname, 'w') as out_f:
        
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

    print(f'Time elapsed: {np.round(y-x, 1)} s')

if __name__ == '__main__':
    main()
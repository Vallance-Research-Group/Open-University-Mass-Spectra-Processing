import numpy as np
import matplotlib.pyplot as plt
from numba import jit
import h5py
import timeit
from tkinter import filedialog, Tk

def main():
    root = Tk()
    root.withdraw()

    #Choose file to open
    fname = filedialog.askopenfilename(title = "Select file",\
    filetypes = (("hdf5 files","*.h5"),("All files","*.*")))
    
    if fname == '': return

    plot_mass_spec(fname)

def plot_mass_spec(fname):
    data_gen = read_data(fname)

    x = timeit.default_timer()

    try:
        while True:
            counts, arrival_times = next(data_gen)

            try:
                mass_spec += np.bincount(arrival_times, minlength=mass_spec.size)
            except NameError:
                mass_spec = np.bincount(arrival_times, minlength=120000)

    except StopIteration:
        pass

    y = timeit.default_timer()
    print(f'Execution time: {np.round(y-x, 2)} s')

    plt.figure()
    plt.plot(mass_spec)
    plt.show()




def read_data(fname, cycles_per_batch=1_000_000):
    with h5py.File(fname, 'r') as in_h5:
        counts_dset = in_h5['Ion counts']
        times_dset = in_h5['Arrival times']

        n_cycles = counts_dset.shape[0]
        batch_offset = 0

        # Determine the first and last cycle to process for each batch
        for cycle_start in range(0, n_cycles, cycles_per_batch):
            cycle_stop = min(cycle_start + cycles_per_batch, n_cycles)

            # Read the counts for the batch, and determine number of arrival times
            counts = counts_dset[cycle_start:cycle_stop]
            batch_times = int(np.sum(counts, dtype='<u8'))

            times = times_dset[batch_offset:batch_offset + batch_times]

            yield counts, times

            batch_offset += batch_times



if __name__ == '__main__':
    main()
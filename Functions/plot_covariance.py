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

    # plot_mass_spec(fname)
    generate_covariance_matrix(fname)
    # plot_counts(fname)

@jit(nopython=True, cache=True)
def process_batch(XY_term, mass_spec, counts, times, N=12_000, bin_size=10):

    # Process cycle by cycle
    start = 0

    for next_count in counts:

        for a in range(next_count):
            # Determine i from the arrival time (rebin)
            i = int(times[start + a] // bin_size)
            mass_spec[i] += 1

            # Avoid having to calculate each time
            base_idx = N * i - (i * (i-1)) // 2

            for b in range(next_count):
                # Determine j from the arrival time (rebin)
                j = int(times[start + b] // bin_size)

                if j < i: continue

                # Determine the correct index in the triangular matrix and increment
                XY_term[base_idx + (j-i)] += 1

        start += next_count

@jit(nopython=True, cache=True)
def process_X_Y_term(mass_spec, X_Y_term):
    n = mass_spec.size
    k = 0

    # Since we are iterating through all points, use k as an index
    for i in range(n):
        mass_i = mass_spec[i]

        for j in range(i,n):
            X_Y_term[k] += mass_i * mass_spec[j]

            k += 1


def reconstruct_square_matrix(mat, cov_size):
    # Convert the input matrix into a full matrix
    full = np.zeros((cov_size, cov_size))
    iu = np.triu_indices(cov_size)
    full[iu] = mat
    full[(iu[1], iu[0])] = mat

    return full

def generate_covariance_matrix(fname):
    data_gen = read_data(fname)

    base_size = 120_000
    bin_size = 200
    
    cov_size = int(np.ceil(base_size / bin_size))

    x = timeit.default_timer()

    # Define triangle matrix to save space
    # Note that the data is rebinned into 12000, rather than 120000
    mean_XY_term = np.zeros(int(cov_size*(cov_size+1) / 2))
    mean_X_mean_Y_term = np.zeros(int(cov_size*(cov_size+1) / 2))
    mass_spec = np.zeros(cov_size)

    n_cycles = 0

    try:
        while True:
            counts, arrival_times = next(data_gen)
            process_batch(mean_XY_term, mass_spec, counts, arrival_times, cov_size, bin_size)
            n_cycles += counts.size

    except StopIteration:
        pass

    mean_XY_term /= n_cycles
    mass_spec /= n_cycles

    process_X_Y_term(mass_spec, mean_X_mean_Y_term)

    y = timeit.default_timer()
    print(f'Execution time: {np.round(y-x, 2)} s')

    plt.figure()
    plt.imshow(reconstruct_square_matrix(mean_XY_term, cov_size), origin="lower", interpolation="nearest", vmin=-0.0001, vmax=0.0001)
    plt.figure()
    plt.imshow(reconstruct_square_matrix(mean_X_mean_Y_term, cov_size), origin="lower", interpolation="nearest", vmin=-0.0001, vmax=0.0001)
    plt.figure()
    plt.imshow(reconstruct_square_matrix((mean_XY_term - mean_X_mean_Y_term) * n_cycles/(n_cycles-1), cov_size), origin="lower", interpolation="nearest", cmap='PuOr', vmin=-0.0000001, vmax=0.0000001)
    # plt.colorbar(label="Covariance")

    plt.figure()
    plt.plot(mass_spec)
    plt.show()


def plot_counts(fname):
    with h5py.File(fname, 'r') as in_h5:
        counts_dset = in_h5['Ion counts']
        counts = counts_dset[:]

    counts = counts[:10000]

    # Mov avg
    n = 500
    counts = np.sum([counts[i:-(n-i)]  for i in range(n)], axis=0) / n

    plt.figure()
    plt.plot(counts)
    plt.show()


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
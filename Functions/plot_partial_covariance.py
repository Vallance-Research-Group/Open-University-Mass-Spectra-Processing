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
    mean_XY_term, mean_X_mean_Y_term, cov_XY, pcov_term, cov_size, mass_spec, n_cycles = generate_covariance_matrix(fname, 50)
    # plot_counts(fname)

    plot_results(mean_XY_term, mean_X_mean_Y_term, cov_XY, pcov_term, cov_size, mass_spec)

@jit(nopython=True, cache=True)
def process_batch(counts, times, prev_count_mov_avg, cov_calc_variables, cov_calc_constants, welford_algorithm_terms):
    # Unpack structures
    XY_term, XI_term, mass_spec = cov_calc_variables
    N, bin_size, smoothing_t = cov_calc_constants
    counts_procd, count_run_mean, count_run_sum_sq = welford_algorithm_terms

    # Process cycle by cycle
    start = 0

    # Determine the scaling factor k for the exponential moving average. m is defined to avoid repeatedly calculating 1 - k
    k = 2 / (1 + smoothing_t)
    m = 1 - k

    for next_count in counts:
        # Determine the count value to use as the variable parameter for XI
        prev_count_mov_avg = next_count * k + prev_count_mov_avg * m

        # Update the Welford algorithm terms
        counts_procd += 1
        # Difference w.r.t. existing mean (using moving average value for count)
        delta_old = prev_count_mov_avg - count_run_mean
        # Update mean
        count_run_mean += delta_old / counts_procd
        # Difference w.r.t. existing mean (using moving average value for count)
        delta_new = prev_count_mov_avg - count_run_mean
        # Update sum of squares
        count_run_sum_sq += delta_old * delta_new

        for a in range(next_count):
            # Determine i from the arrival time (rebin)
            i = int(times[start + a] // bin_size)

            # Increment the appropriate term of the mass spectrum and <XI> term
            mass_spec[i] += 1
            XI_term[i] += prev_count_mov_avg

            # Avoid having to calculate each time
            base_idx = N * i - (i * (i-1)) // 2

            for b in range(next_count):
                # Determine j from the arrival time (rebin)
                j = int(times[start + b] // bin_size)

                # Only contributes if j at least as big as i
                # Since binning means there can be multiple ions arriving at the same time,
                # this is required to ensure the diagonal intensity is not underestimated.
                if j < i: continue

                # Determine the correct index in the triangular matrix and increment
                XY_term[base_idx + (j-i)] += 1

        start += next_count

    return prev_count_mov_avg, (counts_procd, count_run_mean, count_run_sum_sq)


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


@jit(nopython=True)
def exponential_moving_average(count_rate, time_period=1):
    if time_period < 1:
        print('Time period for exponential moving average must be at least one. Setting to one')
        time_period = 1

    smoothed_data = np.zeros(count_rate.size)

    # Determine the scaling factor k for the exponential moving average. m is defined to avoid repeatedly calculating 1 - k
    k = 2 / (1 + time_period)
    m = 1 - k
    
    # No historic data for the first point
    smoothed_data[0] = count_rate[0]

    # Apply exponential moving average
    for i in range(1, count_rate.size):
        smoothed_data[i] = count_rate[i] * k + smoothed_data[i-1] * m

    return smoothed_data


def reconstruct_square_matrix(mat, cov_size):
    # Convert the input matrix into a full matrix
    full = np.zeros((cov_size, cov_size))
    iu = np.triu_indices(cov_size)
    full[iu] = mat
    full[(iu[1], iu[0])] = mat

    return full

def generate_covariance_matrix(fname, bin_size=10, smoothing_t=100, return_all=True):
    # Inputs are:
    # file name
    # bin size (since the arrival times can be up to around 120000,
    #   this should be at least ten to make the covariance map not take too much memory)
    # smoothing_t (the time used for the exponential moving average used to determine
    #   the variable parameter)
    data_gen = read_data(fname)

    base_size = 120_000
    
    cov_size = int(np.ceil(base_size / bin_size))

    x = timeit.default_timer()

    # Define triangle matrix to save space
    # Note that the data is rebinned into a smaller size, rather than 120000, due to computational limitations
    mean_XY_term = np.zeros(int(cov_size*(cov_size+1) / 2))
    mean_X_mean_Y_term = np.zeros(int(cov_size*(cov_size+1) / 2))
    pcov_term = np.zeros(int(cov_size*(cov_size+1) / 2))
    mass_spec = np.zeros(cov_size)

    # Since <YI> = <XI>^T, only need to define one of them
    mean_XI_term = np.zeros(cov_size)

    # Define terms to calculate mean and variance of the variable parameter using Welford's algorithm
    # (counts_processed, counts_running_mean, count_running_sum_squares)
    welford_algorithm_terms = (0, 0., 0.)

    # Combine terms to make numba function call cleaner
    cov_calc_variables = (mean_XY_term, mean_XI_term, mass_spec)
    cov_calc_constants = (cov_size, bin_size, smoothing_t)

    n_cycles = 0

    try:
        # Read data outside loop since we need to know the first count to track the moving average first time around
        counts, arrival_times = next(data_gen)
        prev_count_mov_avg = counts[0]

        while True:
            prev_count_mov_avg, welford_algorithm_terms = process_batch(counts, arrival_times, prev_count_mov_avg, cov_calc_variables, cov_calc_constants, welford_algorithm_terms)
            n_cycles += counts.size
            counts, arrival_times = next(data_gen)

    except StopIteration:
        pass

    counts_processed, count_running_mean, count_running_sum_squares = welford_algorithm_terms

    mean_XY_term /= n_cycles
    mass_spec /= n_cycles
    mean_XI_term /= n_cycles

    process_X_Y_term(mass_spec, mean_X_mean_Y_term)

    cov_XY = (mean_XY_term - mean_X_mean_Y_term) * n_cycles / (n_cycles-1)

    # PARTIAL COVARIANCE CORRECTION
    cov_XI = (mean_XI_term - mass_spec * count_running_mean) * n_cycles / (n_cycles-1)
    # The same process is needed to calculate the partial covariance correction term, so reuse function
    process_X_Y_term(cov_XI, pcov_term)
    # Divide pcov term by count variance
    pcov_term /= (count_running_sum_squares / (n_cycles - 1))

    y = timeit.default_timer()
    print(f'Execution time: {np.round(y-x, 2)} s')

    # Only return what is required
    if return_all:
        return mean_XY_term, mean_X_mean_Y_term, cov_XY, pcov_term, cov_size, mass_spec, n_cycles
    else:
        return cov_XY, cov_XY - pcov_term, cov_size, mass_spec, n_cycles

def plot_results(mean_XY_term, mean_X_mean_Y_term, cov_XY, pcov_term, cov_size, mass_spec):

    plt.figure()
    plt.imshow(reconstruct_square_matrix(mean_XY_term, cov_size), origin="lower", interpolation="nearest", vmin=-0.0001, vmax=0.0001)
    plt.title('<XY>')
    plt.figure()
    plt.imshow(reconstruct_square_matrix(mean_X_mean_Y_term, cov_size), origin="lower", interpolation="nearest", vmin=-0.0001, vmax=0.0001)
    plt.title('<X><Y>')
    plt.figure()
    plt.imshow(reconstruct_square_matrix(pcov_term, cov_size), origin="lower", interpolation="nearest", vmin=-0.0001, vmax=0.0001)
    plt.title('pcov correction')
    plt.figure()
    plt.imshow(reconstruct_square_matrix(cov_XY, cov_size), origin="lower", interpolation="nearest", cmap='PuOr', vmin=-0.00001, vmax=0.00001)
    plt.title('<XY> - <X><Y>')
    plt.figure()
    plt.imshow(reconstruct_square_matrix(cov_XY - pcov_term, cov_size), origin="lower", interpolation="nearest", cmap='PuOr', vmin=-0.000001, vmax=0.000001)
    plt.title('<XY> - <X><Y> - pcov_term')
    # plt.colorbar(label="Covariance")

    plt.figure()
    plt.plot(mass_spec)
    plt.show()


def plot_counts(fname):
    with h5py.File(fname, 'r') as in_h5:
        counts_dset = in_h5['Ion counts']
        counts = counts_dset[:]

    counts = counts[:1000]

    plt.figure()
    plt.plot(counts, label='Data')

    for t in range(10, 100, 10):
        plt.plot(exponential_moving_average(counts, t), label=t)


    plt.legend()
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
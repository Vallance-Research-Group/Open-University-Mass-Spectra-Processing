import numpy as np
import matplotlib.pyplot as plt
from numba import jit
from tkinter import filedialog, Tk

def main():
    root = Tk()
    root.withdraw()

    #Choose file to open
    fname = filedialog.askopenfilename(title = "Select file",\
    filetypes = (("lst files","*.lst"),("All files","*.*")))
    
    if fname == '': return
    
    # Define mass spectrum
    mass_spec = np.zeros(120000)

    # Set up generator to read data
    data_gen = read_data(fname, min_time=1)

    # Read and process data in chunks (currently only a subset)
    try:
        for i in range(5000):
            data = next(data_gen)

            process_data(data, mass_spec)

    except StopIteration: pass

    # Plot data
    plt.figure()
    plt.plot(mass_spec)
    plt.show()


@jit(nopython=True)
def process_data(data, mass_spec):
    for _ in data:
        mass_spec[_] += 1


def read_data(fname, min_time=1, line_read_count=10_000):
    if min_time < 1: raise ValueError('Min time must be at least one.')

    with open(fname, 'r') as in_f:
        # Skip header
        for i in range(37): in_f.readline()

        while True:
            # Read line_read_count lines to process
            chunk = np.fromfile(in_f, dtype='<u4', count=line_read_count, sep='\n')

            # Quit if no more data to read
            if chunk.size == 0: break

            # Keep just the times where time is above or equal to the minimum time
            yield chunk[chunk >= min_time]

if __name__ == '__main__':
    main()
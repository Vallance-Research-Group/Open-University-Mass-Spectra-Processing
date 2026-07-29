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

    convert_file_chunking(fname)


def append_cycle_to_buffer(out_buf, cycle_data):
    cycle_data = cycle_data[cycle_data > 2500]
    n = cycle_data.size

    if n == 0:
        return

    if n > 65535:
        raise ValueError(f"Ion count too large for uint16: {n}")

    # Add uint16 ion count to the buffer
    out_buf.extend(struct.pack("<H", n))

    # Add uint32 arrival times to the buffer
    out_buf.extend(memoryview(cycle_data).cast("B"))


def convert_file_chunking(fname, line_read_count=5_000_000, flush_size = 128*1024*1024):
    with open(fname, 'r') as f:
        # Save header separately. Get its file name
        hname = os.path.join(os.path.dirname(fname), os.path.basename(fname).split('.lst')[0] + '_header.txt')
        
        with open(hname, 'w') as head_file:
            # Write header to file
            for i in range(37): head_file.write(f.readline())

        x = default_timer()
        # Define binary file name (Open University binary (.oub) to not get confused with PImMS data)
        conv_fname = os.path.join(os.path.dirname(fname), os.path.basename(fname).split('.lst')[0] + '_cut.oub')

        with open(conv_fname, 'wb') as out_f:
            pending = np.empty(0, dtype='<u4')
            out_buf = bytearray()

            while True:
                # Read line_read_count lines to process
                chunk = np.fromfile(f, dtype='<u4', count=line_read_count, sep='\n')

                # Quit if no more data to read
                if chunk.size == 0: break

                if pending.size != 0:
                    chunk = np.concatenate((pending, chunk))

                zero_positions = np.flatnonzero(chunk == 0)

                # Check for this, but this is very much not expected!
                if zero_positions.size == 0:
                    pending = chunk; continue

                # Get each acquisition cycle - between zeros
                for i in range(len(zero_positions) - 1):
                    append_cycle_to_buffer(out_buf, chunk[zero_positions[i] + 1:zero_positions[i+1]])

                    # Write the buffer at the appropriate time
                    if len(out_buf) >= flush_size:
                        out_f.write(out_buf); out_buf.clear()

                # Add the remaining chunk to pending
                pending = chunk[zero_positions[-1]:]


            # Process final bit of file
            if pending.size != 0:
                # Write last bit of file
                append_cycle_to_buffer(out_buf, pending[1:])
                out_f.write(out_buf); out_buf.clear()

        y = default_timer()

        print(f'Time elapsed: {np.round(y-x, 1)} s')


if __name__ == '__main__':
    main()
    
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThreadPool, pyqtSlot
from QThread_classes.lst_to_h5_QThread import lstConvertQRunnable
import threading

class FileGatewayManager(QObject):
    # Manages the threads to convert files, and allows overwrites of existing files to be processed
    # Also debounces if the same button is pressed multiple times
    # (input file, output file, min time, lines to read per chunk)
    request_received = pyqtSignal(str, str, int, int)
    file_converted = pyqtSignal(str, str)
    file_aborted = pyqtSignal(str, str)
    file_accepted = pyqtSignal(str, str)
    progress = pyqtSignal(str, float)

    def __init__(self):
        super().__init__()
        self.request_received.connect(self.debounce_request)
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(2)
        
        # Core data stores to track states
        self.pending_timers = {}  # {output_file: (input_file, min_time, lines_to_read, QTimer)}
        self.active_jobs = {}     # {output_file: threading.Event}

        self._closing = False


    @pyqtSlot(str, str, int, int)
    def debounce_request(self, input_file, output_file, min_time, line_read_count):
        if self._closing: return

        # Cancel pending timer if it hasn't fired yet
        if output_file in self.pending_timers:
            _, _, _, old_timer = self.pending_timers[output_file]
            old_timer.stop()
            old_timer.deleteLater()

        # Set up a timer which will fire to start the job
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.launch_worker(output_file))
        self.pending_timers[output_file] = (input_file, min_time, line_read_count, timer)

        # Kill mid-execution worker if it's already actively processing this file
        if output_file in self.active_jobs:
            self.active_jobs[output_file].set()
            
            # Do not start the timer until the callback

        else:
            # Start the timer for all other cases
            timer.start(200)


    def launch_worker(self, output_file):
        input_file, min_time, line_read_count, _ = self.pending_timers.pop(output_file, (None, None, None, None))
        if not input_file:
            return

        # Prepare thread-safe cancellation tracking event
        cancel_event = threading.Event()
        self.active_jobs[output_file] = cancel_event

        worker = lstConvertQRunnable(input_file, output_file, cancel_event, min_time, line_read_count)
        
        # Link back to the main process
        worker.signals.finished.connect(self.thread_finished)
        worker.signals.abort.connect(self.thread_aborted)
        worker.signals.start_proc.connect(self.thread_started)
        worker.signals.progress.connect(self.report_progress)

        self.thread_pool.start(worker)

    @pyqtSlot(str, str)
    def thread_started(self, input_file, output_file):
        self.file_accepted.emit(input_file, output_file)

    @pyqtSlot(str, float)
    def report_progress(self, output_file, percent_read):
        self.progress.emit(output_file, percent_read)

    @pyqtSlot(str,str)
    def thread_finished(self, input_file, output_file):
        self.active_jobs.pop(output_file, None)
        self.file_converted.emit(input_file, output_file)

        try:
            _, _, _, timer = self.pending_timers[output_file]
            timer.start(100)
            
        except KeyError:
            pass

    @pyqtSlot(str,str)
    def thread_aborted(self, input_file, output_file):
        self.active_jobs.pop(output_file, None)
        self.file_aborted.emit(input_file, output_file)

        try:
            _, _, _, timer = self.pending_timers[output_file]
            timer.start(100)

        except KeyError:
            pass

    
    def shutdown(self, timeout_ms=5000):
        if self._closing:
            return self.thread_pool.waitForDone(timeout_ms)

        self._closing = True

        # Stop processes that are still in the debounce stage
        for _, _, _, timer in self.pending_timers.values():
            timer.stop()
            timer.deleteLater()

        self.pending_timers.clear()

        # Cancel every worker that is already running
        for cancel_event in self.active_jobs.values():
            cancel_event.set()

        # Remove QRunnables that are queued but have not started
        self.thread_pool.clear()

        # Wait for the workers to finish
        stopped = self.thread_pool.waitForDone(timeout_ms)

        if stopped:
            self.active_jobs.clear()

        return stopped
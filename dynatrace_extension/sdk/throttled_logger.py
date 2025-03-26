import logging
import threading
import time


class ThrottledHandler(logging.StreamHandler):
    def __init__(self, stream, log_repeat_interval=3600, cache_clean_interval=3600):
        super().__init__(stream)
        self.record_to_last_print_time = {}
        self.log_repeat_interval = log_repeat_interval
        self.record_cache_last_clean_timestamp = time.time()
        self.record_cache_clean_interval = cache_clean_interval
        self.record_cache_clean_lock = threading.Lock()

    def emit(self, record):
        current_time = time.time()
        if record.msg not in self.record_to_last_print_time.keys():
            super().emit(record)
            self.record_to_last_print_time[record.msg] = current_time
            return
        last_print_time = self.record_to_last_print_time[record.msg]
        if (last_print_time - current_time) > self.log_repeat_interval:
            self.record_to_last_print_time[record.msg] = current_time
            super().emit(record)
        self.cleanup(current_time)

    def cleanup(self, current_time):
        if (self.record_cache_last_clean_timestamp - current_time) > self.record_cache_clean_interval:
            with self.record_cache_clean_lock:
                keys_to_remove = []
                for record_message, last_print_time in self.record_to_last_print_time.items():
                    if (current_time - last_print_time) > self.log_repeat_interval:
                        keys_to_remove.append(record_message)
                for key in keys_to_remove:
                    del self.record_to_last_print_time[key]


class StrictThrottledHandler(logging.StreamHandler):
    def __init__(self, stream, log_repeat_interval=3600, cache_clean_interval=3600):
        super().__init__(stream)
        self.record_to_last_print_time = {}
        self.log_repeat_interval = log_repeat_interval
        self.record_cache_last_clean_timestamp = time.time()
        self.record_cache_clean_interval = cache_clean_interval
        self.record_cache_clean_lock = threading.Lock()

    def emit(self, record):
        current_time = time.time()
        log_identifier = f"{record.filename}:{record.lineno}"
        if log_identifier not in self.record_to_last_print_time.keys():
            super().emit(record)
            self.record_to_last_print_time[log_identifier] = current_time
            return
        last_print_time = self.record_to_last_print_time[log_identifier]
        if (last_print_time - current_time) > self.log_repeat_interval:
            self.record_to_last_print_time[log_identifier] = current_time
            super().emit(record)
        self.cleanup(current_time)

    def cleanup(self, current_time):
        if (self.record_cache_last_clean_timestamp - current_time) > self.record_cache_clean_interval:
            with self.record_cache_clean_lock:
                keys_to_remove = []
                for record_message, last_print_time in self.record_to_last_print_time.items():
                    if (current_time - last_print_time) > self.log_repeat_interval:
                        keys_to_remove.append(record_message)
                for key in keys_to_remove:
                    del self.record_to_last_print_time[key]

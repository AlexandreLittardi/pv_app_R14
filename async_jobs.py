"""A cancellable worker; queue messages keep all Tk access on its owner thread."""
import queue
import threading

class Cancelled(Exception):pass

class Job:
    def __init__(self,work):
        self.messages=queue.Queue();self.cancelled=threading.Event()
        def report(done,total):
            if self.cancelled.is_set():raise Cancelled('Calculation cancelled.')
            self.messages.put(('progress',(done,total)))
        def run():
            try:
                result=work(report)
                if self.cancelled.is_set():raise Cancelled('Calculation cancelled.')
                self.messages.put(('done',result))
            except Exception as exc:self.messages.put(('error',exc))
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
    def cancel(self):self.cancelled.set()

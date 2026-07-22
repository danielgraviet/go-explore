from daytona import Daytona
from time import monotonic

class Timer:
    def __init__(self, description):
        self.description = description
    def __enter__(self):
        self.start = monotonic()
        return self
    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        elapsed = monotonic() - self.start
        print(f"{self.description}: {elapsed:.2f} seconds")

client = Daytona()

try:
    with Timer("Sandbox Creation"):
        sbx = client.create()
    
    with Timer("Snapshot Creation"):
        snp = sbx._experimental_create_snapshot("danny-test")
    
finally:
    sbx.delete()

"""
Tegrastats Power Sampler for Jetson Devices
Monitors power consumption and integrates energy over time.
"""

import subprocess
import threading
import time
import re
from typing import Optional, List, Tuple
from collections import deque


class TegrastatsMonitor:
    """Monitor Jetson power consumption using tegrastats."""

    def __init__(self, interval_ms: int = 100):
        """
        Initialize tegrastats monitor.

        Args:
            interval_ms: Sampling interval in milliseconds (default: 100ms)
        """
        self.interval_ms = interval_ms
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

        # Store (timestamp, power_mw) tuples
        self.samples: deque = deque(maxlen=100000)
        self.lock = threading.Lock()

    def _parse_power(self, line: str) -> Optional[float]:
        """
        Parse power consumption from tegrastats output.

        Example line:
        RAM 2156/7471MB (lfb 1419x4MB) CPU [3%@729,2%@729,2%@729,2%@729,0%@729,0%@729]
        EMC_FREQ 0%@204 GR3D_FREQ 0%@[114] VIC_FREQ 115 APE 25 PLL@36C CPU@38.5C Tboard@32C
        GPU@34C PMIC@100C AUX@36C Tdiode@35.75C VDD_IN 2594/2594 VDD_CPU_GPU_CV 307/307
        VDD_SOC 922/922

        We look for VDD_IN (total power in mW)
        """
        try:
            # Look for VDD_IN pattern: VDD_IN current/average
            match = re.search(r'VDD_IN\s+(\d+)/(\d+)', line)
            if match:
                current_power = float(match.group(1))  # mW
                return current_power

            # Alternative: POM_5V_IN on some Jetson models
            match = re.search(r'POM_5V_IN\s+(\d+)/(\d+)', line)
            if match:
                current_power = float(match.group(1))  # mW
                return current_power

        except Exception as e:
            pass

        return None

    def _reader_thread(self):
        """Background thread to read tegrastats output."""
        while self.running:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break

                line = line.decode('utf-8').strip()
                power_mw = self._parse_power(line)

                if power_mw is not None:
                    timestamp = time.time()
                    with self.lock:
                        self.samples.append((timestamp, power_mw))

            except Exception as e:
                if self.running:
                    print(f"Error reading tegrastats: {e}")
                break

    def start(self):
        """Start monitoring power consumption."""
        if self.running:
            print("Monitor already running")
            return

        try:
            # Launch tegrastats with specified interval
            self.process = subprocess.Popen(
                ['tegrastats', '--interval', str(self.interval_ms)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1
            )

            self.running = True
            self.thread = threading.Thread(target=self._reader_thread, daemon=True)
            self.thread.start()

            # Wait a bit for first samples
            time.sleep(0.5)
            print(f"Tegrastats monitor started (interval: {self.interval_ms}ms)")

        except FileNotFoundError:
            raise RuntimeError("tegrastats not found. Are you running on a Jetson device?")
        except Exception as e:
            raise RuntimeError(f"Failed to start tegrastats: {e}")

    def stop(self):
        """Stop monitoring."""
        if not self.running:
            return

        self.running = False

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

        print("Tegrastats monitor stopped")

    def clear_samples(self):
        """Clear all stored samples."""
        with self.lock:
            self.samples.clear()

    def get_samples(self, t_start: Optional[float] = None,
                    t_end: Optional[float] = None) -> List[Tuple[float, float]]:
        """
        Get power samples within time range.

        Args:
            t_start: Start timestamp (None = from beginning)
            t_end: End timestamp (None = until now)

        Returns:
            List of (timestamp, power_mw) tuples
        """
        with self.lock:
            samples = list(self.samples)

        if t_start is not None:
            samples = [(t, p) for t, p in samples if t >= t_start]

        if t_end is not None:
            samples = [(t, p) for t, p in samples if t <= t_end]

        return samples

    def measure_idle(self, duration_sec: float = 10.0) -> float:
        """
        Measure baseline idle power consumption.

        Args:
            duration_sec: Measurement duration in seconds

        Returns:
            Average idle power in mW
        """
        if not self.running:
            raise RuntimeError("Monitor not started. Call start() first.")

        print(f"Measuring idle power for {duration_sec} seconds...")
        self.clear_samples()

        t_start = time.time()
        time.sleep(duration_sec)
        t_end = time.time()

        samples = self.get_samples(t_start, t_end)

        if not samples:
            raise RuntimeError("No power samples collected. Check tegrastats output.")

        powers = [p for _, p in samples]
        avg_power = sum(powers) / len(powers)

        print(f"Idle power: {avg_power:.1f} mW (from {len(samples)} samples)")
        return avg_power

    def integrate_energy(self, t_start: float, t_end: float,
                        idle_mw: float = 0.0) -> float:
        """
        Calculate energy consumption using trapezoidal integration.

        Args:
            t_start: Start timestamp
            t_end: End timestamp
            idle_mw: Idle power to subtract (default: 0)

        Returns:
            Energy in Joules
        """
        samples = self.get_samples(t_start, t_end)

        if len(samples) < 2:
            print(f"Warning: Only {len(samples)} samples for energy calculation")
            if len(samples) == 1:
                duration = t_end - t_start
                power_w = (samples[0][1] - idle_mw) / 1000.0
                return max(0, power_w * duration)
            return 0.0

        # Trapezoidal integration: E = ∫P dt
        energy_j = 0.0

        for i in range(len(samples) - 1):
            t1, p1 = samples[i]
            t2, p2 = samples[i + 1]

            # Subtract idle power
            p1_active = max(0, p1 - idle_mw)
            p2_active = max(0, p2 - idle_mw)

            # Convert mW to W
            p1_w = p1_active / 1000.0
            p2_w = p2_active / 1000.0

            # Trapezoidal area
            dt = t2 - t1
            avg_power = (p1_w + p2_w) / 2.0
            energy_j += avg_power * dt

        return energy_j

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Example usage
if __name__ == "__main__":
    print("Testing TegrastatsMonitor...")

    try:
        with TegrastatsMonitor(interval_ms=100) as monitor:
            # Measure idle power
            idle_power = monitor.measure_idle(duration_sec=5.0)

            # Simulate some work
            print("\nSimulating workload...")
            t_start = time.time()
            time.sleep(3.0)  # Replace with actual work
            t_end = time.time()

            # Calculate energy
            energy = monitor.integrate_energy(t_start, t_end, idle_mw=idle_power)

            print(f"\nResults:")
            print(f"  Duration: {t_end - t_start:.2f} seconds")
            print(f"  Energy (above idle): {energy:.3f} Joules")
            print(f"  Average power: {energy / (t_end - t_start):.2f} Watts")

    except RuntimeError as e:
        print(f"Error: {e}")
        print("\nNote: This script must run on a Jetson device with tegrastats available.")
